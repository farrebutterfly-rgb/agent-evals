"""Paths and settings. Every path to a system under test is an environment variable with a
sibling-directory default, so the repos can be checked out side by side or anywhere else."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
EVIDENCE = ROOT / "evidence"
BASELINE = ROOT / "baseline" / "baseline.json"
DATASET_FILE = DATA / "cases-v1.json"
LOCK_FILE = DATA / "cases-v1.lock.json"


def repo_path(var: str, default_name: str) -> Path:
    return Path(os.environ.get(var) or (ROOT.parent / default_name)).resolve()


def grounded_context_repo() -> Path:
    return repo_path("GROUNDED_CONTEXT_REPO", "grounded-context")


def agent_toolkit_repo() -> Path:
    return repo_path("AGENT_TOOLKIT_REPO", "agent-toolkit")


def workers() -> int:
    return max(1, int(os.environ.get("EVAL_WORKERS", "4")))


def call_timeout_s() -> float:
    return float(os.environ.get("EVAL_CALL_TIMEOUT_S", "60"))


def git_rev(path: Path) -> dict:
    """Full commit hash of a repo plus whether its working tree has uncommitted changes."""
    def run(*args: str) -> str:
        return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, check=True).stdout.strip()
    try:
        rev = run("rev-parse", "HEAD")
        dirty = bool(run("status", "--porcelain", "--untracked-files=no"))
        return {"rev": rev, "short": rev[:7], "dirty": dirty}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"rev": "unknown", "short": "unknown", "dirty": None}


def node_version() -> str:
    try:
        return subprocess.run(["node", "--version"], capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "missing"


def python_version() -> str:
    return sys.version.split()[0]
