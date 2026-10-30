"""Runs the real systems through their CLIs. Skipped, with the reason printed, when a repo is missing."""
import json
import os
import subprocess
import sys
import unittest

from evals import config
from evals.adapters import AgentToolkitAdapter, GroundedContextAdapter
from evals.regression import OK, REGRESSION, compare
from evals.runner import run_eval

MISSING = GroundedContextAdapter().available() or AgentToolkitAdapter().available()


@unittest.skipIf(MISSING, f"systems under test not available: {MISSING}")
class RealSystemsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = json.loads(config.BASELINE.read_text(encoding="utf-8"))

    def test_unmodified_systems_match_the_stored_baseline(self):
        r, _ = run_eval("good")
        self.assertEqual(r["results"]["all"]["not_run"], 0, r["not_run_cases"])
        code, msgs = compare(r, self.baseline)
        self.assertEqual(code, OK, msgs)

    def test_degraded_wrappers_fail_the_check(self):
        for variant in ("drop_citations", "always_answer"):
            with self.subTest(variant=variant):
                r, _ = run_eval(variant)
                self.assertEqual(compare(r, self.baseline)[0], REGRESSION)

    def test_p1_runner_reports_the_injected_error_codes(self):
        cases = [c for c in json.loads(config.DATASET_FILE.read_text(encoding="utf-8"))["cases"] if c["id"] in ("T04", "T06")]
        res = AgentToolkitAdapter().run(cases)
        self.assertIn("TIMEOUT", res["T04"].output["tool_error_codes"])
        self.assertIn("NOT_FOUND", res["T06"].output["tool_error_codes"])


class LiveGuardTest(unittest.TestCase):
    def test_live_without_key_exits_2_with_a_message(self):
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        p = subprocess.run([sys.executable, "-m", "evals", "run", "--live"], cwd=config.ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn("ANTHROPIC_API_KEY is not set", p.stderr)


if __name__ == "__main__":
    unittest.main()
