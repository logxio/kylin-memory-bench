import unittest

from kylin_memory_bench.model import read_json, validate_dataset
from kylin_memory_bench.scoring import score_case


class ScoringContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {c["id"]: c for c in validate_dataset(read_json("data/tasks.json"))["cases"]}

    def test_missing_observation_never_passes(self):
        case = self.cases["retention-01"]
        result = score_case(case, {"workspace": ".", "turns": [], "files": {}, "memory": {}})
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["checks"][0]["status"], "missing")

    def test_obsolete_contact_is_penalized(self):
        case = self.cases["update-01"]
        evidence = {"workspace": ".", "turns": [{"step": "probe", "reply": '{"contact":"许蓝"}',
                                                     "source": "test:observed"}], "files": {}, "memory": {}}
        result = score_case(case, evidence)
        self.assertEqual(result["score"], 0)
        self.assertTrue(all(c["status"] == "fail" for c in result["checks"]))

    def test_forbidden_persistence_is_separate_from_reply(self):
        case = self.cases["boundary-01"]
        evidence = {"workspace": ".", "turns": [{"step": "probe", "reply": '{"code":"unknown"}',
                                                     "source": "test:observed"}], "files": {},
                    "memory": {"notes": {"source": "test:memory", "content": "479381"}}}
        result = score_case(case, evidence)
        self.assertEqual([c["status"] for c in result["checks"]], ["pass", "pass", "fail"])

    def test_claimed_file_success_does_not_override_wrong_file(self):
        case = self.cases["task-reuse-01"]
        evidence = {"workspace": ".", "turns": [{"step": "execute", "reply": '{"written":true}',
                                                     "source": "test:observed"}],
                    "files": {"output/export.json": {"source": "test:file",
                                                     "content": '{"delimiter":",","columns":["item","cost"]}'}},
                    "memory": {}}
        result = score_case(case, evidence)
        self.assertEqual(result["score"], 66.67)
        self.assertEqual(result["checks"][1]["status"], "fail")

    def test_same_evidence_same_score(self):
        case = self.cases["recall-01"]
        evidence = {"workspace": ".", "turns": [{"step": "probe", "reply": '{"owner":"林溪","format":"PDF"}',
                                                     "source": "test:observed"}], "files": {}, "memory": {}}
        self.assertEqual(score_case(case, evidence), score_case(case, evidence))


if __name__ == "__main__":
    unittest.main()
