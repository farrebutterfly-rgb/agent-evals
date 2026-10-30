"""Markdown rendering of a report dict. Every number is shown as numerator/denominator."""
from __future__ import annotations

import json

from .scoring import METRICS


def frac(x: dict | None) -> str:
    if not x:
        return "n/a"
    pct = f" ({100 * x['passed'] / x['of']:.0f}%)" if x["of"] else ""
    return f"{x['passed']}/{x['of']}{pct}"


def to_markdown(r: dict) -> str:
    s = r["session"]
    L = [f"<!-- session: {json.dumps(s, ensure_ascii=False)} -->",
         f"# agent-evals report: variant `{s['variant']}`", "",
         f"Generated {s['ts']} by agent-evals `{s['code_rev']}`. Dataset `{s['dataset']}` (sha256 `{s['dataset_sha256'][:16]}...`), scoring rules `{s['scoring_rules']}`. "
         f"Mode **{s['mode']}**. Python {s['python']}, Node {s['node']}.", ""]
    L += ["> " + c for c in r["caveats"]]
    L += ["", "## Systems under test", "", "| System | Revision | Dirty | Mode | How it is called |", "| --- | --- | --- | --- | --- |"]
    for name, d in r["systems"].items():
        g = d["git"]
        extra = f" **degraded: {d['degraded']['variant']}** ({d['degraded']['what']})" if "degraded" in d else ""
        L.append(f"| {name} | `{g['rev']}` | {g['dirty']} | {d['mode']}{extra} | `{d['command']}` |")
    L += ["", "## Results, development and held-out reported separately", "",
          "| Metric | Dev | Held-out | All |", "| --- | --- | --- | --- |"]
    res = r["results"]
    for m in ("case_pass", *METRICS):
        L.append(f"| {m} | {frac(res['dev'].get(m))} | {frac(res['heldout'].get(m))} | {frac(res['all'].get(m))} |")
    L.append(f"| executed / not run | {res['dev']['executed']} / {res['dev']['not_run']} | {res['heldout']['executed']} / {res['heldout']['not_run']} | {res['all']['executed']} / {res['all']['not_run']} |")
    L += ["", "## Case pass by category", "", "| Category | Dev | Held-out |", "| --- | --- | --- |"]
    for cat, d in r["by_category"].items():
        L.append(f"| {cat} | {frac(d['dev'].get('case_pass'))} | {frac(d['heldout'].get('case_pass'))} |")
    L += ["", f"## Failed cases ({len(r['failed_cases'])})", ""]
    if not r["failed_cases"]:
        L.append("None.")
    for f in r["failed_cases"]:
        L.append(f"- **{f['id']}** ({f['split']}, {f['category']}, returned `{f['status']}`): " + "; ".join(f["failures"]).replace("|", "/"))
    L += ["", f"## Not run ({len(r['not_run_cases'])})", ""]
    L.append("None." if not r["not_run_cases"] else "\n".join(f"- {n['id']} ({n['split']}): {n['reason']}" for n in r["not_run_cases"]))
    d = r.get("diagnostics")
    if d:
        L += ["", "## Diagnostics (post-hoc, descriptive, not used by the regression check)", ""]
        for k, v in d.items():
            if k == "label":
                continue
            if isinstance(v, dict):
                L.append(f"- {k}: {len(v['cases'])}/{v['of']} {v['cases'] or ''}")
            else:
                L.append(f"- {k}: {v or 'none'}")
    L += ["", "## Config", "", "```json", json.dumps(r["config"], indent=2), "```", ""]
    return "\n".join(L)
