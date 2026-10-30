"""Loads the frozen dataset and refuses to continue if it no longer matches its recorded sha256."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import config

CATEGORIES = ("known_support", "missing_or_conflict", "prompt_injection", "tool_failure")
SPLITS = ("dev", "heldout")


class DatasetError(Exception):
    pass


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path = config.DATASET_FILE, lock: Path = config.LOCK_FILE) -> dict:
    expected = json.loads(lock.read_text(encoding="utf-8"))["sha256"]
    actual = sha256_of(path)
    if actual != expected:
        raise DatasetError(
            f"{path.name} sha256 {actual[:12]} does not match the frozen value {expected[:12]} in {lock.name}. "
            "Gold labels are frozen; a change needs a new dataset version, not an edit."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    data["sha256"] = actual
    validate(data)
    return data


def validate(data: dict) -> None:
    cases = data["cases"]
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise DatasetError("duplicate case ids")
    heldout = set(data["splits"]["heldout"])
    for c in cases:
        if c["category"] not in CATEGORIES:
            raise DatasetError(f"{c['id']}: unknown category {c['category']}")
        if c["split"] not in SPLITS or (c["split"] == "heldout") != (c["id"] in heldout):
            raise DatasetError(f"{c['id']}: split does not match the held-out list")
        if c["expected_status"] == "answered" and not c.get("expected_answer"):
            raise DatasetError(f"{c['id']}: answered case without expected_answer")
        if c["expected_status"] not in c["acceptable_statuses"]:
            raise DatasetError(f"{c['id']}: expected_status not in acceptable_statuses")
