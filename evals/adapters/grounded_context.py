"""grounded-context (P2), reached only through its public CLI:

    npm run --silent answer -- --json "<question>"
    npm run --silent source -- <doc_id> <section_id>
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from .. import config
from .base import RawResult, last_json_line


class GroundedContextAdapter:
    system = "grounded-context"
    name = "grounded-context"

    def __init__(self, repo: Optional[Path] = None, live: bool = False, k: Optional[int] = None):
        self.repo = repo or config.grounded_context_repo()
        self.live = live
        self.k = k
        self._sections: dict[tuple[str, str], Optional[str]] = {}
        self._lock = threading.Lock()

    def describe(self) -> dict:
        return {
            "system": self.system,
            "repo": str(self.repo),
            "git": config.git_rev(self.repo),
            "command": "npm run --silent answer -- --json" + (" --live" if self.live else "") + (f" --k {self.k}" if self.k else "") + ' "<question>"',
            "mode": "live" if self.live else "fixture",
            "k": self.k or "system default",
        }

    def available(self) -> Optional[str]:
        if not (self.repo / "package.json").exists():
            return f"grounded-context not found at {self.repo} (set GROUNDED_CONTEXT_REPO)"
        if not (self.repo / "node_modules").exists():
            return f"grounded-context at {self.repo} has no node_modules (run: make install)"
        return None

    def _npm(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["npm", "run", "--silent", *args], cwd=self.repo, capture_output=True, text=True,
                              timeout=config.call_timeout_s(), env={**os.environ, "NO_COLOR": "1"})

    def run_one(self, case: dict) -> RawResult:
        args = ["answer", "--", "--json"]
        if self.live:
            args.append("--live")
        if self.k:
            args += ["--k", str(self.k)]
        args.append(case["question"])
        t0 = time.monotonic()
        try:
            p = self._npm(*args)
        except subprocess.TimeoutExpired:
            return RawResult(case["id"], None, not_run=f"timeout after {config.call_timeout_s():.0f} s")
        except FileNotFoundError as e:
            return RawResult(case["id"], None, not_run=f"cannot start npm: {e}")
        ms = int((time.monotonic() - t0) * 1000)
        return RawResult(case["id"], last_json_line(p.stdout), stdout=p.stdout[-2000:], exit_code=p.returncode,
                         duration_ms=ms, extra={"stderr": p.stderr[-500:]} if p.returncode else {})

    def run(self, cases: list[dict]) -> dict[str, RawResult]:
        missing = self.available()
        if missing:
            return {c["id"]: RawResult(c["id"], None, not_run=missing) for c in cases}
        with ThreadPoolExecutor(max_workers=config.workers()) as ex:
            return {r.case_id: r for r in ex.map(self.run_one, cases)}

    def section_text(self, doc_id: str, section_id: str) -> Optional[str]:
        """Current text of a section, printed by grounded-context's own `source` CLI. None if it does not exist."""
        key = (doc_id, section_id)
        with self._lock:
            if key in self._sections:
                return self._sections[key]
        try:
            p = self._npm("source", "--", doc_id, section_id)
            # line 1: file and version, line 2: "§<id> <heading>", the rest: the stored text
            text = "\n".join(p.stdout.splitlines()[2:]) if p.returncode == 0 else None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            text = None
        with self._lock:
            self._sections[key] = text
        return text
