"""agent-toolkit (P1). The small runner in p1_runner.mts is executed with P1's own tsx binary and
imports P1's exported runAgent, setup and ScriptedModel. Nothing is written into the P1 repo."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Optional

from .. import config
from .base import RawResult

RUNNER = Path(__file__).resolve().parent / "p1_runner.mts"


class AgentToolkitAdapter:
    system = "agent-toolkit"
    name = "agent-toolkit"

    def __init__(self, repo: Optional[Path] = None):
        self.repo = repo or config.agent_toolkit_repo()

    @property
    def tsx(self) -> Path:
        return self.repo / "node_modules" / ".bin" / "tsx"

    def describe(self) -> dict:
        return {
            "system": self.system,
            "repo": str(self.repo),
            "git": config.git_rev(self.repo),
            "command": f"{self.tsx} evals/adapters/p1_runner.mts <repo>  (cases on stdin)",
            "mode": "fixture (the scripted model steps are the test input)",
        }

    def available(self) -> Optional[str]:
        if not (self.repo / "src" / "agent.ts").exists():
            return f"agent-toolkit not found at {self.repo} (set AGENT_TOOLKIT_REPO)"
        if not self.tsx.exists():
            return f"agent-toolkit at {self.repo} has no node_modules (run: make install)"
        return None

    def run(self, cases: list[dict]) -> dict[str, RawResult]:
        missing = self.available()
        if missing:
            return {c["id"]: RawResult(c["id"], None, not_run=missing) for c in cases}
        payload = json.dumps({"cases": [{"id": c["id"], "question": c["question"], "script": c["script"]} for c in cases]})
        t0 = time.monotonic()
        try:
            p = subprocess.run([str(self.tsx), str(RUNNER), str(self.repo)], input=payload, capture_output=True,
                               text=True, timeout=config.call_timeout_s() * 2, cwd=self.repo)
        except subprocess.TimeoutExpired:
            return {c["id"]: RawResult(c["id"], None, not_run="agent-toolkit runner timed out") for c in cases}
        ms = int((time.monotonic() - t0) * 1000)
        out: dict[str, RawResult] = {}
        for line in p.stdout.splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if "harness_error" in rec:
                out[rec["id"]] = RawResult(rec["id"], None, not_run=f"runner error: {rec['harness_error']}")
            else:
                out[rec["id"]] = RawResult(rec["id"], rec, stdout=line, exit_code=p.returncode, duration_ms=ms // max(1, len(cases)))
        for c in cases:
            if c["id"] not in out:
                out[c["id"]] = RawResult(c["id"], None, not_run=f"runner produced no result (exit {p.returncode}): {p.stderr[-300:]}")
        return out
