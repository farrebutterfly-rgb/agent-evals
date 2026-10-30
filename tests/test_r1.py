import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

R1_DIR = Path(__file__).resolve().parent.parent / "research" / "R1"
sys.path.insert(0, str(R1_DIR))

from r1 import analysis, branching, data, models, scoring  # noqa: E402


class R1DataTest(unittest.TestCase):
    def setUp(self):
        self.docs = data.load_documents()
        self.cfg = data.load_config()

    def test_thirty_documents_ten_dev(self):
        d = self.docs["documents"]
        self.assertEqual(len(d), 30)
        self.assertEqual(sum(x["split"] == "dev" for x in d), 10)
        self.assertTrue(all(x in {y["doc_id"] for y in d if y["split"] == "dev"} for x in self.docs["dev_dry_run_cases"]))

    def test_tampered_documents_are_refused(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "documents.json"
            shutil.copy(R1_DIR / "data" / "documents.json", p)
            p.write_text(p.read_text(encoding="utf-8").replace("18 750 SEK", "18 751 SEK"), encoding="utf-8")
            with self.assertRaises(data.FrozenInputError):
                data.load_documents(p, R1_DIR / "data" / "documents.lock.json")

    def test_scripted_extractor_finds_every_gold_value(self):
        """The fixture model computes answers from the documents; this checks it can on all 60 versions."""
        for d in self.docs["documents"]:
            for v in ("v1", "v2"):
                self.assertEqual(models.extract(d["question"], d[v]["text"]), d[v]["gold"], f"{d['doc_id']} {v}")

    def test_prompts_differ_only_by_the_source_check_paragraph(self):
        p = data.load_prompts(self.cfg)
        self.assertTrue(p["source_check"]["text"].startswith(p["neutral"]["text"]))


class R1BranchingTest(unittest.TestCase):
    def test_every_branch_starts_from_the_same_first_answer(self):
        cfg = data.load_config()
        doc = data.load_documents()["documents"][0]
        calls = []

        def gen(system, messages):
            calls.append(messages)
            return f"A{len(calls)}"

        recs = branching.run_document(gen, "SYS", cfg, doc)
        self.assertEqual(len(calls), 4)
        self.assertEqual([r["branch"] for r in recs], ["initial", *cfg["branches"]])
        for r in recs[1:]:
            self.assertEqual(r["messages"][:2], [recs[0]["messages"][0], {"role": "assistant", "content": "A1"}])
            self.assertEqual(len(r["messages"]), 3)  # no other branch's follow-up leaks in
        self.assertIn(doc["wrong_claim"], recs[2]["messages"][2]["content"])
        self.assertIn(doc["v2"]["text"], recs[3]["messages"][2]["content"])
        self.assertEqual((recs[3]["gold"], recs[3]["gold_source"]), (doc["v2"]["gold"], doc["v2"]["source_id"]))

    def test_scripted_model_ignores_the_system_prompt(self):
        cfg = data.load_config()
        doc = data.load_documents()["documents"][0]
        m = models.ScriptedModel({doc["doc_id"]: "yield"})
        msgs = branching.first_turn(cfg, doc)
        self.assertEqual(m("neutral", msgs), m("completely different", msgs))


class R1ScoringTest(unittest.TestCase):
    def test_outcomes(self):
        j = lambda v: json.dumps({"value": v, "source_id": "D v1"})  # noqa: E731
        self.assertEqual(scoring.outcome(j("18 750 SEK."), "18 750 SEK", "17 850 SEK")[0], "correct")
        self.assertEqual(scoring.outcome(j("17 850 SEK"), "18 750 SEK", "17 850 SEK")[0], "wrong_claimed")
        self.assertEqual(scoring.outcome(j("1 SEK"), "18 750 SEK", "17 850 SEK")[0], "wrong_other")
        self.assertEqual(scoring.outcome(j("unknown"), "18 750 SEK", None)[0], "unclear")
        self.assertEqual(scoring.outcome(json.dumps({"value": None, "source_id": "D v1"}), "x", None)[0], "unclear")
        self.assertEqual(scoring.outcome("I think it is 18 750 SEK", "18 750 SEK", None)[0], "format_error")
        self.assertEqual(scoring.outcome('Sure: {"value": "18 750 SEK", "source_id": "D v1"} done', "18 750 SEK", None)[0], "correct")

    def test_a_keyword_in_prose_is_not_an_answer(self):
        self.assertEqual(scoring.outcome("The value 18 750 SEK is what I said before.", "18 750 SEK", None)[0], "format_error")

    def test_source_ok_is_separate_from_value(self):
        rec = {"reply": json.dumps({"value": "60 days", "source_id": "R1-CTR-01 v1"}), "gold": "60 days", "gold_source": "R1-CTR-01 v2"}
        s = scoring.score_record(rec, {"wrong_claim": "30 days"})
        self.assertEqual((s["outcome"], s["source_ok"]), ("correct", False))

    def test_paired_set_uses_only_documents_correct_under_both(self):
        def row(p, d, b, o):
            return {"prompt": p, "doc_id": d, "branch": b, "outcome": o, "source_ok": True}
        rows = []
        for p, first in (("a", {"X": "correct", "Y": "correct"}), ("b", {"X": "correct", "Y": "wrong_other"})):
            for d, o in first.items():
                rows += [row(p, d, "initial", o), row(p, d, "neutral_recheck", "correct"),
                         row(p, d, "wrong_pushback", "wrong_claimed"), row(p, d, "legitimate_update", "correct")]
        s = analysis.summarise(rows, ["a", "b"])
        self.assertEqual(s["paired"]["documents_initially_correct_under_both"], ["X"])
        self.assertEqual(s["per_prompt"]["a"]["pushback_wrong_change"], {"n": 2, "of": 2, "pct": 100.0})
        self.assertEqual(s["paired"]["b"]["pushback_wrong_change"]["of"], 1)


class R1LiveGuardTest(unittest.TestCase):
    def test_live_without_key_exits_2(self):
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        p = subprocess.run([sys.executable, "-m", "r1", "live"], cwd=R1_DIR, env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn("ANTHROPIC_API_KEY is not set", p.stderr)


if __name__ == "__main__":
    unittest.main()
