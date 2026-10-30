"""Fake adapters for tests that must not depend on the other repos. The oracle answers from the
gold labels, which is exactly what makes it useless as a measurement and useful as a harness test."""
from __future__ import annotations

from evals.adapters.base import RawResult

SECTIONS = {
    ("CTR-002", "3"): "The rent is 1 150 SEK per parking space per month excluding VAT.",
    ("POL-001", "2"): "The hotel cost limit is 1 800 SEK per night including breakfast.",
    ("MEMO-002", "2"): "The hotel cost limit is 2 200 SEK per night including breakfast.",
}


class OracleGrounded:
    system = "grounded-context"
    name = "oracle"

    def describe(self) -> dict:
        return {"system": self.system, "repo": "fake", "git": {"rev": "fake", "short": "fake", "dirty": False}, "command": "in-memory", "mode": "fixture"}

    def section_text(self, doc_id: str, section_id: str):
        return SECTIONS.get((doc_id, section_id), f"Section text containing ANSWER for {doc_id} {section_id}.")

    def run(self, cases: list[dict]) -> dict:
        out = {}
        for c in cases:
            st = c["expected_status"]
            cites = [{"doc_id": s.split("#")[0], "section_id": s.split("#")[1],
                      "quote": self.section_text(*s.split("#"))} for s in c["allowed_sources"][: (2 if st == "conflict" else 1)]]
            out[c["id"]] = RawResult(c["id"], {"status": st, "answer": (c["expected_answer"] or ["none"])[0],
                                               "citations": cites if st != "insufficient_evidence" else [], "dataset_version": "fake"})
        return out


class OracleToolkit:
    system = "agent-toolkit"
    name = "oracle"

    def describe(self) -> dict:
        return {"system": self.system, "repo": "fake", "git": {"rev": "fake", "short": "fake", "dirty": False}, "command": "in-memory", "mode": "fixture"}

    def run(self, cases: list[dict]) -> dict:
        out = {}
        for c in cases:
            completed = c["expected_run_status"] == "completed"
            final = {"status": c["expected_status"], "answer": (c["expected_answer"] or ["unknown"])[0],
                     "supplier_ids": c["expected_supplier_ids"], "evidence_ids": c["required_sources"]} if completed else None
            out[c["id"]] = RawResult(c["id"], {"id": c["id"], "run_status": c["expected_run_status"], "final": final,
                                               "tool_error_codes": c["expected_error_codes"], "fetched_ids": c["allowed_sources"],
                                               "final_rejections": c["expected_final_rejections"]})
        return out
