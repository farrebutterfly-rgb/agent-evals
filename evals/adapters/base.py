"""Adapter contract. An adapter runs cases against one system and returns the system's own
output untouched. Scoring never sees anything the system did not print."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol


@dataclass
class RawResult:
    case_id: str
    output: Optional[dict]  # parsed JSON the system printed, or None when it printed nothing parseable
    stdout: str = ""
    exit_code: Optional[int] = None
    not_run: Optional[str] = None  # harness could not execute the case (missing repo, timeout); excluded from denominators
    duration_ms: int = 0
    extra: dict = field(default_factory=dict)


SourceLookup = Callable[[str, str], Optional[str]]


class Adapter(Protocol):
    system: str
    name: str

    def run(self, cases: list[dict]) -> dict[str, RawResult]: ...

    def describe(self) -> dict: ...


def last_json_line(stdout: str) -> Optional[dict]:
    import json

    for line in reversed([l for l in stdout.splitlines() if l.strip()]):
        try:
            v = json.loads(line)
        except ValueError:
            return None
        return v if isinstance(v, dict) else None
    return None
