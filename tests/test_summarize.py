import unittest

from kylin_memory_bench.model import ABILITIES, fingerprint, read_json, validate_dataset
from kylin_memory_bench.scoring import score_case
from kylin_memory_bench.summarize import summarize


class VariantAndRepeatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = validate_dataset(read_json("data/tasks.json"))

    def test_variants_are_distinct_cross_session_and_missing_evidence_scores_zero(self):
        cases = self.dataset["cases"]
        self.assertEqual(len(cases), 12)
        for ability in ABILITIES:
            variants = [case for case in cases if case["ability"] == ability]
            self.assertEqual(len(variants), 2)
            self.assertGreaterEqual(len({step["session"] for step in variants[1]["steps"]}), 2)
            self.assertEqual(score_case(variants[1], {"workspace": ".", "turns": [],
                                                      "files": {}, "memory": {}})["score"], 0)
            probe = " ".join(step["prompt"] for step in variants[1]["steps"] if step["id"] in ("probe", "execute"))
            for check in variants[1]["checks"]:
                if check["kind"] == "reply_equals" and isinstance(check["equals"], str):
                    self.assertNotIn(check["equals"], probe)

    def make_result(self, run_id, missing_step=False):
        cases = self.dataset["cases"]
        evidence = {case["id"]: {"turns": [{"step": step["id"]} for step in case["steps"]], "errors": []}
                    for case in cases}
        if missing_step:
            evidence["retention-02"]["turns"].pop()
            evidence["retention-02"]["errors"] = [{"step": "probe", "type": "TimeoutError"}]
        scores = {"cases": [{"id": case["id"], "ability": case["ability"], "score": 50.0}
                            for case in cases],
                  "dimensions": {ability: 50.0 for ability in ABILITIES}, "overall": 50.0}
        return {"schema": "kmb.result.v1", "run_id": run_id,
                "dataset_fingerprint": fingerprint(self.dataset), "evidence_class": "live/observed",
                "agents": [{"name": "agent", "kind": "openclaw", "evidence_class": "live/observed",
                            "config_fingerprint": "same-config", "scores": scores, "evidence": evidence}]}

    def test_repeat_summary_counts_incomplete_and_timeout(self):
        summary = summarize(self.dataset, [("first", self.make_result("a")),
                                           ("second", self.make_result("b", missing_step=True))])
        agent = summary["agents"][0]
        self.assertEqual(summary["run_count"], 2)
        self.assertEqual(agent["steps"]["retention-02/probe"],
                         {"completed": 1, "attempted_runs": 2, "completion_rate": 0.5})
        self.assertEqual(agent["incomplete_steps"], 1)
        self.assertEqual(agent["timeout_error_count"], 1)
        self.assertEqual(agent["overall"]["sample_stddev"], 0.0)

    def test_repeat_summary_rejects_changed_dataset_or_config(self):
        first = self.make_result("a")
        second = self.make_result("b")
        second["agents"][0]["config_fingerprint"] = "different"
        with self.assertRaisesRegex(ValueError, "config fingerprint"):
            summarize(self.dataset, [("first", first), ("second", second)])
        second = self.make_result("b")
        second["dataset_fingerprint"] = "different"
        with self.assertRaisesRegex(ValueError, "dataset fingerprint"):
            summarize(self.dataset, [("first", first), ("second", second)])


if __name__ == "__main__":
    unittest.main()
