import collections
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from evals import config, dataset


class DatasetTest(unittest.TestCase):
    def setUp(self):
        self.d = dataset.load()

    def test_fifty_cases_in_the_planned_mix(self):
        cats = collections.Counter(c["category"] for c in self.d["cases"])
        self.assertEqual(cats, {"known_support": 20, "missing_or_conflict": 10, "prompt_injection": 10, "tool_failure": 10})

    def test_ten_held_out_stratified(self):
        ho = [c for c in self.d["cases"] if c["split"] == "heldout"]
        self.assertEqual(len(ho), 10)
        self.assertEqual(collections.Counter(c["category"] for c in ho),
                         {"known_support": 4, "missing_or_conflict": 2, "prompt_injection": 2, "tool_failure": 2})

    def test_tampered_file_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "cases.json"
            shutil.copy(config.DATASET_FILE, p)
            p.write_text(p.read_text(encoding="utf-8").replace('"10 500 SEK"', '"10 501 SEK"'), encoding="utf-8")
            with self.assertRaises(dataset.DatasetError):
                dataset.load(p, config.LOCK_FILE)


@unittest.skipUnless((config.grounded_context_repo() / "data" / "docs").exists(), "grounded-context repo not found")
class GoldAgainstSourcesTest(unittest.TestCase):
    """Label check: every gold value must occur in at least one of its allowed sections (current version)."""

    def section(self, doc_id: str, sec: str) -> str:
        files = sorted((config.grounded_context_repo() / "data" / "docs").glob(f"{doc_id}.v*.md"),
                       key=lambda f: int(re.search(r"\.v(\d+)\.md$", f.name).group(1)))
        text = files[-1].read_text(encoding="utf-8")
        m = re.search(rf"^## {re.escape(sec)} .*?\n(.*?)(?=^## |\Z)", text, re.S | re.M)
        return m.group(1) if m else ""

    def test_gold_values_are_in_allowed_sections(self):
        for c in dataset.load()["cases"]:
            if c["system"] != "grounded-context" or c["expected_status"] != "answered":
                continue
            texts = [self.section(*s.split("#")) for s in c["allowed_sources"]]
            self.assertTrue(any(a in t for a in c["expected_answer"] for t in texts), c["id"])

    def test_conflict_sources_exist(self):
        for c in dataset.load()["cases"]:
            if c["expected_status"] == "conflict":
                self.assertTrue(all(self.section(*s.split("#")) for s in c["allowed_sources"]), c["id"])


if __name__ == "__main__":
    unittest.main()
