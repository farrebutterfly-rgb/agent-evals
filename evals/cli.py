"""python3 -m evals <command>

  doctor                  check Python, Node and the two repos; install their node_modules if missing
  run [--variant V] [--live] [--k N]   run all 50 cases, write evidence/report-<V>.{json,md}
  check [--variant V]     compare evidence/report-<V>.json with baseline/baseline.json (exit 1 on regression)
  eval                    run the good variant, write the report, then check it (one command)
  baseline                store evidence/report-good.json as the baseline
  demo                    good run passes the check, each degraded variant fails it
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from . import config, dataset
from .adapters import VARIANTS
from .regression import INCOMPARABLE, OK, REGRESSION, baseline_from, check_files


def _summary(report: dict) -> str:
    from .report import frac

    r = report["results"]
    lines = [f"  {'':25} {'dev':>14} {'held-out':>14}"]
    for m in ("case_pass", "schema_valid", "correct_value", "citation_correct", "correct_abstention", "instruction_not_followed", "failure_handled"):
        lines.append(f"  {m:25} {frac(r['dev'].get(m)):>14} {frac(r['heldout'].get(m)):>14}")
    lines.append(f"  not run: {r['all']['not_run']}   failed: {', '.join(f['id'] for f in report['failed_cases']) or 'none'}")
    return "\n".join(lines)


def cmd_run(variant: str, live: bool, k: int | None, quiet: bool = False) -> dict:
    from .runner import run_eval, write

    if live and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set. --live makes grounded-context call the real API, which costs money. "
              "Fixture mode (the default) does not. Live measurements stay 'Not run'.", file=sys.stderr)
        raise SystemExit(2)
    report, obs = run_eval(variant=variant, live=live, k=k)
    paths = write(report, obs)
    if not quiet:
        s = report["session"]
        print(f"agent-evals  variant={variant}  mode={s['mode']}  rev={s['code_rev']}  dataset={s['dataset']} sha256={s['dataset_sha256'][:12]}")
        for name, d in report["systems"].items():
            print(f"  {name:17} rev {d['git']['short']}{' (dirty)' if d['git']['dirty'] else ''}  {d['mode']}")
        print(_summary(report))
        print(f"  report: {paths['json'].relative_to(config.ROOT)}  {paths['md'].relative_to(config.ROOT)}")
    return report


def cmd_check(variant: str) -> int:
    code, msgs = check_files(config.EVIDENCE / f"report-{variant}.json", config.BASELINE)
    for m in msgs:
        print(f"  {m}")
    print({OK: "  check: no regression against baseline", REGRESSION: "  check: FAILED, regression against baseline",
           INCOMPARABLE: "  check: not comparable"}[code])
    return code


def cmd_doctor() -> int:
    ok = True
    print(f"python {config.python_version()}  (need 3.10+)")
    if sys.version_info < (3, 10):
        ok = False
    node = config.node_version()
    print(f"node   {node}  (need 22+)")
    if not node.startswith("v") or int(node[1:].split(".")[0]) < 22:
        ok = False
    for var, path in (("GROUNDED_CONTEXT_REPO", config.grounded_context_repo()), ("AGENT_TOOLKIT_REPO", config.agent_toolkit_repo())):
        if not (path / "package.json").exists():
            print(f"{var}={path}: NOT FOUND. Clone it there or set {var}.")
            ok = False
            continue
        g = config.git_rev(path)
        if not (path / "node_modules").exists():
            print(f"{var}={path}: installing its pinned dependencies (npm ci)")
            subprocess.run(["npm", "ci", "--silent"], cwd=path, check=False)
        print(f"{var}={path}  rev {g['short']}{' (dirty)' if g['dirty'] else ''}  node_modules {'ok' if (path / 'node_modules').exists() else 'MISSING'}")
    try:
        d = dataset.load()
        print(f"dataset {d['dataset_version']} sha256 {d['sha256'][:12]} matches lock, {len(d['cases'])} cases")
    except dataset.DatasetError as e:
        print(f"dataset: {e}")
        ok = False
    return 0 if ok else 1


def cmd_demo() -> int:
    print("== 1. the unmodified systems, checked against the stored baseline")
    cmd_run("good", False, None)
    good = cmd_check("good")
    results = {"good": good}
    for i, v in enumerate(VARIANTS, start=2):
        print(f"\n== {i}. degraded wrapper `{v}`: {VARIANTS[v][0]}")
        cmd_run(v, False, None)
        results[v] = cmd_check(v)
    print("\n== summary")
    expected = {"good": OK, **{v: REGRESSION for v in VARIANTS}}
    for v, code in results.items():
        print(f"  {v:15} check exit {code}  ({'as expected' if code == expected[v] else 'UNEXPECTED'})")
    return 0 if results == expected else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m evals", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--variant", default="good", choices=["good", *VARIANTS])
    r.add_argument("--live", action="store_true")
    r.add_argument("--k", type=int)
    c = sub.add_parser("check")
    c.add_argument("--variant", default="good", choices=["good", *VARIANTS])
    e = sub.add_parser("eval")
    e.add_argument("--live", action="store_true")
    sub.add_parser("baseline")
    sub.add_parser("demo")
    sub.add_parser("doctor")
    a = p.parse_args(argv)
    try:
        if a.cmd == "run":
            cmd_run(a.variant, a.live, a.k)
            return 0
        if a.cmd == "check":
            return cmd_check(a.variant)
        if a.cmd == "eval":
            rep = cmd_run("good", a.live, None)
            return cmd_check("good") if rep["session"]["mode"] == "fixture" else 0
        if a.cmd == "baseline":
            rep = json.loads((config.EVIDENCE / "report-good.json").read_text(encoding="utf-8"))
            if rep["session"]["variant"] != "good":
                print("refusing: baseline must come from the good variant", file=sys.stderr)
                return 2
            config.BASELINE.parent.mkdir(parents=True, exist_ok=True)
            config.BASELINE.write_text(json.dumps(baseline_from(rep), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"baseline written: {config.BASELINE.relative_to(config.ROOT)}")
            return 0
        if a.cmd == "demo":
            return cmd_demo()
        if a.cmd == "doctor":
            return cmd_doctor()
    except dataset.DatasetError as e:
        print(f"dataset error: {e}", file=sys.stderr)
        return 2
    return 2
