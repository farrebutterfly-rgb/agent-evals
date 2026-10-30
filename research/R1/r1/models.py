"""Two ways to produce a reply: a scripted fixture model and the live Anthropic Messages API.

The scripted model exists to exercise the branching and the scoring. It reads the documents in the
conversation and extracts values from them, so its answers are computed from data. It never reads
the system prompt, so it behaves identically under both prompts by construction: any difference
between prompts in a dry run would be a bug in the harness, not a finding."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

DOC_RE = re.compile(r"Document (\S+) version (\d+):\n(.*?)(?:\n\n|$)", re.S)
VALUE_RE = {
    "amount": re.compile(r"\d{1,3}(?: \d{3})* SEK"),
    "date": re.compile(r"\d{4}-\d{2}-\d{2}"),
    "count": re.compile(r"\d+ (?:days?|packages?)"),
}
STOP = {"what", "which", "when", "with", "that", "this", "does", "have", "many", "must", "from", "within", "long", "often", "the", "per"}


def value_kind(question: str) -> str:
    q = question.lower()
    if "date" in q or q.startswith("when"):
        return "date"
    if "how many" in q or "how often" in q or "how long" in q or "notice period" in q:
        return "count"
    return "amount"


def extract(question: str, text: str) -> str | None:
    """Value of the asked-for kind from the sentence that shares the most words with the question."""
    words = {w for w in re.findall(r"[a-z]+", question.lower()) if len(w) > 3 and w not in STOP}
    best, best_score = None, -1
    for sent in re.split(r"(?<=[.!?])\s+", text):
        m = VALUE_RE[value_kind(question)].search(sent)
        if not m:
            continue
        score = len(words & set(re.findall(r"[a-z]+", sent.lower())))
        if score > best_score:
            best, best_score = m.group(0), score
    return best


class ScriptedModel:
    """profile: doc_id -> behaviour on the wrong_pushback branch: "hold", "yield" or "prose"."""

    def __init__(self, profile: dict[str, str] | None = None):
        self.profile = profile or {}
        self.id = "fixture:scripted-r1"

    def __call__(self, system: str, messages: list) -> str:  # system is deliberately ignored
        users = [m["content"] for m in messages if m["role"] == "user"]
        docs = [d for u in users for d in DOC_RE.findall(u)]
        doc_id, version, text = docs[-1]
        question = re.search(r"Question: (.+)", users[0]).group(1)
        last = users[-1]
        claimed = re.search(r"The correct value is (.+?)\. Reply", last)
        if len(users) > 1 and claimed:
            behaviour = self.profile.get(doc_id, "hold")
            if behaviour == "prose":
                return "You may well be right, I am not completely sure about this one."
            if behaviour == "yield":
                return json.dumps({"value": claimed.group(1), "source_id": f"{doc_id} v{version}"})
        value = extract(question, text)
        return json.dumps({"value": value, "source_id": f"{doc_id} v{version}"})


class LiveUnavailable(Exception):
    pass


class AnthropicModel:
    """Messages API over urllib (no SDK, stdlib only). Costs money. Not run in this repo so far."""

    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, live_cfg: dict):
        self.key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.key:
            raise LiveUnavailable("ANTHROPIC_API_KEY is not set. A live R1 run calls the real API and costs money; the dry run does not.")
        self.model = os.environ.get(live_cfg["model_env"]) or live_cfg["model_default"]
        self.temperature = live_cfg["temperature"]
        self.max_tokens = live_cfg["max_tokens"]
        self.id = f"anthropic:{self.model}"
        self.usage: list[dict] = []

    def __call__(self, system: str, messages: list) -> str:
        body = json.dumps({"model": self.model, "max_tokens": self.max_tokens, "temperature": self.temperature,
                           "system": system, "messages": messages}).encode()
        req = urllib.request.Request(self.URL, data=body, method="POST", headers={
            "x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            return f"__api_error__ HTTP {e.code}: {e.read()[:300]!r}"
        self.usage.append(data.get("usage", {}))
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
