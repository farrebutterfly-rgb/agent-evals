"""python3 -m r1 <command>   (run from research/R1)

  dry-run    3 development documents, scripted model, both prompts: 24 generations, no cost
  live       real model on the documents named by --docs (default: the 3 dry-run documents); needs ANTHROPIC_API_KEY
  estimate   generations and an input-token estimate for a full run, before spending anything
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import uuid
from datetime import datetime, timezone

from . import analysis, branching, data, models, scoring

# Dry-run behaviour on the pushback branch, fixed before the dry run. Chosen to exercise every
# scoring path (kept, adopted claim, format error). Identical for both prompts.
DRY_RUN_PROFILE = {"R1-INV-01": "hold", "R1-DLV-03": "yield", "R1-CTR-01": "prose"}


def code_rev() -> str:
    try:
        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=data.R1, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no", "--", "."], cwd=data.R1, capture_output=True, text=True).stdout.strip()
        return rev + ("+dirty" if dirty else "")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "uncommitted"


def run(mode: str, doc_ids: list[str], model) -> dict:
    cfg = data.load_config()
    docs = data.load_documents()
    prompts = data.load_prompts(cfg)
    by_id = {d["doc_id"]: d for d in docs["documents"]}
    unknown = [d for d in doc_ids if d not in by_id]
    if unknown:
        raise SystemExit(f"unknown documents: {unknown}")
    run_id = uuid.uuid4().hex[:8]
    session = {"type": "session", "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "run_id": run_id,
               "code_rev": code_rev(), "protocol": cfg["protocol_version"], "dataset": docs["dataset_version"],
               "dataset_sha256": docs["sha256"], "prompts": {k: v["sha256"] for k, v in prompts.items()},
               "model_id": model.id, "params": cfg["live"] if mode == "live" else {"scripted_profile": DRY_RUN_PROFILE},
               "python": sys.version.split()[0], "machine": platform.machine(), "platform": platform.platform(), "mode": mode,
               "documents": doc_ids}
    raw, rows = [], []
    for pname, p in prompts.items():
        for did in doc_ids:
            doc = by_id[did]
            for rec in branching.run_document(model, p["text"], cfg, doc):
                s = scoring.score_record(rec, doc)
                raw.append({"prompt": pname, "doc_id": did, **rec, **s})
                rows.append({"run_id": run_id, "mode": mode, "model_id": model.id, "prompt": pname, "doc_id": did,
                             "split": doc["split"], "branch": rec["branch"], "gold": rec["gold"], "gold_source": rec["gold_source"],
                             "reply": rec["reply"], **s})
    summary = analysis.summarise(rows, list(prompts))
    out = data.R1 / "results" / mode
    out.mkdir(parents=True, exist_ok=True)
    with (out / "raw.jsonl").open("w", encoding="utf-8") as f:
        f.write(json.dumps(session, ensure_ascii=False) + "\n")
        for r in raw:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out / "results.csv").write_text(analysis.to_csv(rows), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps({"session": session, **summary}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    title = ("Fixture dry run, scripted model: tests the code, not a model" if mode == "dry-run"
             else f"Live run, {model.id}")
    (out / "chart.svg").write_text(analysis.to_svg(rows, list(prompts), title), encoding="utf-8")
    return {"session": session, "summary": summary, "rows": rows, "out": out}


def print_result(res: dict) -> None:
    s = res["session"]
    print(f"R1 {s['mode']}  run={s['run_id']}  rev={s['code_rev']}  model={s['model_id']}  dataset={s['dataset']} sha256={s['dataset_sha256'][:12]}")
    print(f"  documents: {', '.join(s['documents'])}   generations: {len(res['rows'])}")
    for p, m in res["summary"]["per_prompt"].items():
        f = lambda k: f"{m[k]['n']}/{m[k]['of']}"  # noqa: E731
        print(f"  {p:13} initial correct {f('initial_correct')}  pushback: wrong change {f('pushback_wrong_change')}, kept {f('pushback_kept_correct')}, "
              f"format/unclear {f('pushback_format_or_unclear')}  neutral kept {f('neutral_kept_correct')}  update ok {f('update_correct_with_v2_source_all')}")
    print(f"  paired set (initially correct under both prompts): {len(res['summary']['paired']['documents_initially_correct_under_both'])}")
    print(f"  written: {res['out'].relative_to(data.R1)}/raw.jsonl results.csv summary.json chart.svg")
    if s["mode"] == "dry-run":
        print("  The scripted model ignores the system prompt, so both prompts must score the same. These are not model results.")


def estimate() -> None:
    cfg = data.load_config()
    docs = data.load_documents()["documents"]
    prompts = data.load_prompts(cfg)
    chars = 0
    gens = 0
    for p in prompts.values():
        for d in docs:
            first = branching.first_turn(cfg, d)[0]["content"]
            a0 = 80  # a short JSON reply
            chars += len(p["text"]) + len(first)
            for b in cfg["branches"]:
                chars += len(p["text"]) + len(first) + a0 + len(branching.followup(cfg, b, d))
            gens += 1 + len(cfg["branches"])
    print(f"full run: {gens} generations (limit {cfg['budget']['max_generations_full_run']})")
    print(f"input tokens, ESTIMATED as chars/4: about {chars // 4}; output capped at {cfg['live']['max_tokens']} per generation")
    print("Look up the current price for the chosen model before running. No price is assumed here.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m r1", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("dry-run")
    lv = sub.add_parser("live")
    lv.add_argument("--docs", nargs="*")
    sub.add_parser("estimate")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "dry-run":
            ids = data.load_documents()["dev_dry_run_cases"]
            print_result(run("dry-run", ids, models.ScriptedModel(DRY_RUN_PROFILE)))
            return 0
        if a.cmd == "live":
            cfg = data.load_config()
            try:
                model = models.AnthropicModel(cfg["live"])
            except models.LiveUnavailable as e:
                print(str(e), file=sys.stderr)
                return 2
            ids = a.docs or data.load_documents()["dev_dry_run_cases"]
            print_result(run("live", ids, model))
            return 0
        if a.cmd == "estimate":
            estimate()
            return 0
    except data.FrozenInputError as e:
        print(f"frozen input error: {e}", file=sys.stderr)
        return 2
    return 2
