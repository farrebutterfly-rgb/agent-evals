import copy
import unittest

from evals import dataset
from evals.adapters import DegradedAdapter
from evals.regression import INCOMPARABLE, OK, REGRESSION, baseline_from, compare
from evals.runner import run_eval

from .helpers import OracleGrounded, OracleToolkit


def oracle(variant=None):
    a = {"grounded-context": OracleGrounded(), "agent-toolkit": OracleToolkit()}
    return {k: DegradedAdapter(v, variant) for k, v in a.items()} if variant else a


class RegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = dataset.load()
        cls.good, _ = run_eval(adapters=oracle(), data=cls.data)
        cls.base = baseline_from(cls.good)

    def test_oracle_passes_every_case(self):
        self.assertEqual(self.good["results"]["all"]["case_pass"], {"passed": 50, "of": 50}, self.good["failed_cases"])

    def test_same_results_are_not_a_regression(self):
        self.assertEqual(compare(self.good, self.base)[0], OK)

    def test_dropped_citations_are_detected(self):
        bad, _ = run_eval(adapters=oracle("drop_citations"), data=self.data)
        code, msgs = compare(bad, self.base)
        self.assertEqual(code, REGRESSION)
        self.assertTrue(any("citation_correct" in m for m in msgs))

    def test_always_answer_is_detected(self):
        bad, _ = run_eval(adapters=oracle("always_answer"), data=self.data)
        code, msgs = compare(bad, self.base)
        self.assertEqual(code, REGRESSION)
        self.assertTrue(any("correct_abstention" in m for m in msgs))

    def test_case_that_stops_running_is_a_regression(self):
        r = copy.deepcopy(self.good)
        r["cases"][0]["not_run"] = "timeout"
        self.assertEqual(compare(r, self.base)[0], REGRESSION)

    def test_other_dataset_is_not_comparable(self):
        r = copy.deepcopy(self.good)
        r["session"]["dataset_sha256"] = "0" * 64
        self.assertEqual(compare(r, self.base)[0], INCOMPARABLE)


if __name__ == "__main__":
    unittest.main()
