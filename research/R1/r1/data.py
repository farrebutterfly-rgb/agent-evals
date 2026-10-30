"""Frozen inputs: documents (sha256-checked), the two system prompts verbatim, and the run config."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

R1 = Path(__file__).resolve().parent.parent


class FrozenInputError(Exception):
    pass


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_config() -> dict:
    return json.loads((R1 / "config.json").read_text(encoding="utf-8"))


def load_documents(path: Path | None = None, lock: Path | None = None) -> dict:
    path = path or R1 / "data" / "documents.json"
    lock = lock or R1 / "data" / "documents.lock.json"
    want = json.loads(lock.read_text(encoding="utf-8"))["sha256"]
    got = sha256(path)
    if got != want:
        raise FrozenInputError(f"{path.name} sha256 {got[:12]} differs from the frozen {want[:12]}; gold and split are locked")
    d = json.loads(path.read_text(encoding="utf-8"))
    d["sha256"] = got
    return d


def load_prompts(cfg: dict) -> dict[str, dict]:
    out = {}
    for name, rel in cfg["prompts"].items():
        p = R1 / rel
        out[name] = {"text": p.read_text(encoding="utf-8"), "sha256": sha256(p), "file": rel}
    return out
