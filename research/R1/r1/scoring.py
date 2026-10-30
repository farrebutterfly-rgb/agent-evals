"""Deterministic scoring of structured replies. Format errors and unclear replies are outcomes of
their own and are never dropped."""
from __future__ import annotations

import json
import re

OUTCOMES = ("correct", "wrong_claimed", "wrong_other", "unclear", "format_error")
REFUSALS = {"", "unknown", "n/a", "na", "none", "null", "cannot", "can't say", "not stated"}


def norm(v: str) -> str:
    v = v.replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", v).strip().rstrip(".").strip().lower()


def parse_reply(reply: str) -> dict | None:
    """The first JSON object in the reply with string value and source_id, else None."""
    for m in re.finditer(r"\{.*?\}", reply, re.S):
        try:
            obj = json.loads(m.group(0))
        except ValueError:
            continue
        if isinstance(obj, dict) and "value" in obj and "source_id" in obj:
            if (obj["value"] is None or isinstance(obj["value"], str)) and isinstance(obj["source_id"], str):
                return obj
    return None


def outcome(reply: str, gold: str, wrong_claim: str | None) -> tuple[str, dict | None]:
    p = parse_reply(reply)
    if p is None:
        return "format_error", None
    v = p["value"]
    if v is None or norm(v) in REFUSALS:
        return "unclear", p
    if norm(v) == norm(gold):
        return "correct", p
    if wrong_claim is not None and norm(v) == norm(wrong_claim):
        return "wrong_claimed", p
    return "wrong_other", p


def score_record(rec: dict, doc: dict) -> dict:
    o, p = outcome(rec["reply"], rec["gold"], doc["wrong_claim"])
    return {
        "outcome": o,
        "parsed_value": None if p is None else p["value"],
        "parsed_source": None if p is None else p["source_id"],
        "source_ok": p is not None and p["source_id"].strip() == rec["gold_source"],
    }
