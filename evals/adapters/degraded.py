"""Deliberately degraded implementations. Each wraps a real adapter and breaks the system's own
output the way a plausible bug would. The regression check must catch every one of them."""
from __future__ import annotations

import copy

from .base import RawResult


def _drop_citations(system: str, out: dict) -> dict:
    if system == "grounded-context":
        out["citations"] = []
    elif out.get("final"):
        out["final"]["evidence_ids"] = []
    return out


def _always_answer(system: str, out: dict) -> dict:
    """Never abstain: whatever the system concluded, report it as answered."""
    if system == "grounded-context":
        out["status"] = "answered"
    elif out.get("final"):
        out["final"]["status"] = "answered"
    return out


VARIANTS = {
    "drop_citations": ("returns the answer but drops every citation / evidence id", _drop_citations),
    "always_answer": ("turns every abstention or conflict into status answered", _always_answer),
}


class DegradedAdapter:
    def __init__(self, inner, variant: str):
        if variant not in VARIANTS:
            raise ValueError(f"unknown variant {variant}; known: {', '.join(VARIANTS)}")
        self.inner = inner
        self.variant = variant
        self.system = inner.system
        self.name = f"{inner.name}+{variant}"

    def describe(self) -> dict:
        return {**self.inner.describe(), "degraded": {"variant": self.variant, "what": VARIANTS[self.variant][0]}}

    def run(self, cases: list[dict]) -> dict[str, RawResult]:
        fn = VARIANTS[self.variant][1]
        res = self.inner.run(cases)
        for r in res.values():
            if r.output is not None:
                r.output = fn(self.system, copy.deepcopy(r.output))
        return res

    def __getattr__(self, item):  # section_text and friends pass through
        return getattr(self.inner, item)
