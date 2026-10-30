"""Runs the frozen cases against the systems under test and builds the report dict."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import config, dataset, scoring
from .adapters import AgentToolkitAdapter, DegradedAdapter, GroundedContextAdapter

CAVEATS = [
    "Fixture mode: grounded-context answers with its deterministic extractive answerer and agent-toolkit with a scripted model. These numbers measure those implementations, not any language model.",
    "Live measurements: Not run. No ANTHROPIC_API_KEY in the build environment.",
    "Injection cases put the unwanted instruction in the question text, because grounded-context cannot ingest new documents. Injected text inside retrieved passages is not tested.",
    "Synthetic gold labels are not professional legal, tax or accounting validation.",
]


def diagnostics(cases: list[dict], scores: list) -> dict:
    """Descriptive counts added after the first run. Not part of the frozen rules and never used by the check."""
    by_id = {c["id"]: c for c in cases}
    inj = [s for s in scores if s.category == "prompt_injection" and not s.not_run]
    emitted = [s.case_id for s in inj if any(scoring.contains(s.answer, f) for f in by_id[s.case_id]["forbidden_in_answer"])]
    outside = [s.case_id for s in inj if any(k not in by_id[s.case_id]["allowed_sources"] for k in s.cites)]
    abstained = [s.case_id for s in inj if s.status != "answered" and by_id[s.case_id]["expected_status"] == "answered"]
    answered_wrong_with_valid_cite = [
        s.case_id for s in scores if not s.not_run and s.status == "answered"
        and s.metrics.get("citation_correct", {}).get("pass") and not s.metrics.get("correct_value", {}).get("pass", True)]
    answered_when_gold_abstains = [s.case_id for s in scores if not s.not_run and s.status == "answered"
                                   and by_id[s.case_id]["expected_status"] != "answered"]
    return {
        "label": "post-hoc, descriptive only, not part of rules-v1",
        "injection_injected_value_in_answer": {"cases": emitted, "of": len(inj)},
        "injection_cites_outside_allowed": {"cases": outside, "of": len(inj)},
        "injection_abstained_instead_of_answering": {"cases": abstained, "of": sum(by_id[s.case_id]["expected_status"] == "answered" for s in inj)},
        "wrong_value_with_verified_citation": answered_wrong_with_valid_cite,
        "answered_when_gold_abstains": answered_when_gold_abstains,
    }


def build_adapters(variant: str = "good", live: bool = False, k: Optional[int] = None) -> dict:
    gc = GroundedContextAdapter(live=live, k=k)
    at = AgentToolkitAdapter()
    if variant != "good":
        return {"grounded-context": DegradedAdapter(gc, variant), "agent-toolkit": DegradedAdapter(at, variant)}
    return {"grounded-context": gc, "agent-toolkit": at}


def run_eval(variant: str = "good", live: bool = False, k: Optional[int] = None, adapters: Optional[dict] = None,
             data: Optional[dict] = None) -> tuple[dict, list[dict]]:
    data = data or dataset.load()
    adapters = adapters or build_adapters(variant, live, k)
    cases = data["cases"]
    raws = {}
    for system, ad in adapters.items():
        raws.update(ad.run([c for c in cases if c["system"] == system]))
    lookup = getattr(adapters.get("grounded-context"), "section_text", None)
    scores = [scoring.score_case(c, raws[c["id"]], lookup) for c in cases]

    session = {
        "type": "session",
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code_rev": config.git_rev(config.ROOT)["short"] + ("+dirty" if config.git_rev(config.ROOT)["dirty"] else ""),
        "dataset": data["dataset_version"],
        "dataset_sha256": data["sha256"],
        "scoring_rules": data["scoring_rules"]["version"],
        "python": config.python_version(),
        "node": config.node_version(),
        "mode": "live" if live else "fixture",
        "variant": variant,
    }
    by_split = {sp: scoring.aggregate([s for s in scores if s.split == sp]) for sp in ("dev", "heldout")}
    report = {
        "session": session,
        "systems": {name: ad.describe() for name, ad in adapters.items()},
        "config": {
            "variant": variant,
            "live": live,
            "k": k,
            "workers": config.workers(),
            "call_timeout_s": config.call_timeout_s(),
            "env": {v: os.environ.get(v) for v in ("GROUNDED_CONTEXT_REPO", "AGENT_TOOLKIT_REPO", "EVAL_WORKERS")},
        },
        "results": {**by_split, "all": scoring.aggregate(scores)},
        "by_category": {cat: {sp: scoring.aggregate([s for s in scores if s.category == cat and s.split == sp])
                              for sp in ("dev", "heldout")} for cat in dataset.CATEGORIES},
        "failed_cases": [{"id": s.case_id, "split": s.split, "category": s.category, "status": s.status,
                          "failures": s.failures()} for s in scores if not s.not_run and not s.passed],
        "not_run_cases": [{"id": s.case_id, "split": s.split, "reason": s.not_run} for s in scores if s.not_run],
        "cases": [{"id": s.case_id, "split": s.split, "category": s.category, "system": s.system,
                   "passed": s.passed, "not_run": s.not_run, "status": s.status, "answer": s.answer[:300],
                   "cites": s.cites, "metrics": s.metrics} for s in scores],
        "diagnostics": diagnostics(cases, scores),
        "caveats": CAVEATS,
    }
    observations = [{"case_id": c["id"], "system": c["system"], "output": raws[c["id"]].output,
                     "exit_code": raws[c["id"]].exit_code, "not_run": raws[c["id"]].not_run} for c in cases]
    return report, observations


def write(report: dict, observations: list[dict], out_dir: Path = config.EVIDENCE) -> dict:
    from .report import to_markdown

    out_dir.mkdir(parents=True, exist_ok=True)
    v = report["session"]["variant"]
    paths = {"json": out_dir / f"report-{v}.json", "md": out_dir / f"report-{v}.md",
             "observations": out_dir / f"observations-{v}.jsonl"}
    rest = {k: val for k, val in report.items() if k != "session"}
    body = json.dumps(rest, indent=2, ensure_ascii=False)
    # session record on the first line, the rest pretty-printed; still one valid JSON object
    paths["json"].write_text('{"session": ' + json.dumps(report["session"], ensure_ascii=False) + ",\n" + body[1:].lstrip("\n") + "\n", encoding="utf-8")
    paths["md"].write_text(to_markdown(report), encoding="utf-8")
    with paths["observations"].open("w", encoding="utf-8") as f:
        f.write(json.dumps(report["session"], ensure_ascii=False) + "\n")
        for o in observations:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    return paths
