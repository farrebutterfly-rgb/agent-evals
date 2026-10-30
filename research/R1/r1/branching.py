"""One first answer, three separate continuations. Every branch starts from the same stored first
reply, so no branch can see another branch's follow-up."""
from __future__ import annotations

from typing import Callable

Message = dict  # {"role": "user" | "assistant", "content": str}
Generate = Callable[[str, list], str]  # (system prompt, messages) -> reply text


def first_turn(cfg: dict, doc: dict) -> list[Message]:
    v1 = doc["v1"]
    text = cfg["first_turn"].format(doc_id=doc["doc_id"], version=v1["version"], text=v1["text"], question=doc["question"])
    return [{"role": "user", "content": text}]


def followup(cfg: dict, branch: str, doc: dict) -> str:
    t = cfg["followups"][branch]
    if branch == "wrong_pushback":
        return t.format(wrong_claim=doc["wrong_claim"])
    if branch == "legitimate_update":
        v2 = doc["v2"]
        return t.format(doc_id=doc["doc_id"], version=v2["version"], text=v2["text"])
    return t


def gold_for(branch: str, doc: dict) -> tuple[str, str]:
    v = doc["v2"] if branch == "legitimate_update" else doc["v1"]
    return v["gold"], v["source_id"]


def run_document(generate: Generate, system: str, cfg: dict, doc: dict) -> list[dict]:
    """Returns one record per generation: the first answer, then each branch built on that same answer."""
    prefix = first_turn(cfg, doc)
    a0 = generate(system, list(prefix))
    records = [{"branch": "initial", "messages": prefix, "reply": a0, "gold": doc["v1"]["gold"], "gold_source": doc["v1"]["source_id"]}]
    for branch in cfg["branches"]:
        msgs = [*prefix, {"role": "assistant", "content": a0}, {"role": "user", "content": followup(cfg, branch, doc)}]
        gold, src = gold_for(branch, doc)
        records.append({"branch": branch, "messages": msgs, "reply": generate(system, [dict(m) for m in msgs]),
                        "gold": gold, "gold_source": src})
    return records
