"""Compares a report with the stored baseline. Exit codes: 0 no regression, 1 regression, 2 not comparable."""
from __future__ import annotations

import json
from pathlib import Path

from .scoring import METRICS

OK, REGRESSION, INCOMPARABLE = 0, 1, 2


def baseline_from(report: dict) -> dict:
    return {
        "note": "Stored from a fixture run of the unmodified systems. `make baseline` rewrites it; only do that on purpose and commit the diff.",
        "created_from": report["session"],
        "systems": {k: v["git"] for k, v in report["systems"].items()},
        "results": {sp: report["results"][sp] for sp in ("dev", "heldout")},
        "case_pass": {c["id"]: c["passed"] for c in report["cases"]},
        "case_run": {c["id"]: c["not_run"] is None for c in report["cases"]},
    }


def compare(report: dict, baseline: dict) -> tuple[int, list[str]]:
    msgs: list[str] = []
    if report["session"]["dataset_sha256"] != baseline["created_from"]["dataset_sha256"]:
        return INCOMPARABLE, ["dataset sha256 differs from the baseline; results are not comparable"]
    if report["session"]["scoring_rules"] != baseline["created_from"]["scoring_rules"]:
        return INCOMPARABLE, ["scoring rules version differs from the baseline"]
    for name, g in baseline["systems"].items():
        now = report["systems"].get(name, {}).get("git", {})
        if now.get("rev") != g.get("rev"):
            msgs.append(f"note: {name} revision {str(now.get('rev'))[:7]} differs from baseline {str(g.get('rev'))[:7]}")
    regressed = False
    for sp in ("dev", "heldout"):
        for m in ("case_pass", *METRICS):
            b, c = baseline["results"][sp].get(m), report["results"][sp].get(m)
            if b and (not c or c["passed"] < b["passed"]):
                regressed = True
                msgs.append(f"REGRESSION {sp} {m}: {c['passed'] if c else 0}/{c['of'] if c else 0} now, {b['passed']}/{b['of']} in baseline")
    now_pass = {c["id"]: c for c in report["cases"]}
    for cid, was in baseline["case_pass"].items():
        c = now_pass.get(cid)
        if c is None or c["not_run"]:
            if baseline["case_run"].get(cid):
                regressed = True
                msgs.append(f"REGRESSION {cid}: ran in baseline, not run now ({c['not_run'] if c else 'missing'})")
        elif was and not c["passed"]:
            regressed = True
            fails = [f"{k}: {v['reason']}" for k, v in c["metrics"].items() if not v["pass"]]
            msgs.append(f"REGRESSION {cid} passed in baseline, fails now: " + "; ".join(fails))
        elif not was and c["passed"]:
            msgs.append(f"improved {cid}: failed in baseline, passes now")
    return (REGRESSION if regressed else OK), msgs


def check_files(report_path: Path, baseline_path: Path) -> tuple[int, list[str]]:
    if not baseline_path.exists():
        return INCOMPARABLE, [f"no baseline at {baseline_path}; create one with `make baseline`"]
    return compare(json.loads(report_path.read_text(encoding="utf-8")), json.loads(baseline_path.read_text(encoding="utf-8")))
