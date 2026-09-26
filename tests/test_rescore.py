import unittest

from kylin_memory_bench.model import fingerprint
from kylin_memory_bench.rescore import rescore_result
from kylin_memory_bench.scoring import LEGACY_SCORING_VERSION, SCORING_VERSION, score_run


class OfflineRescoreTest(unittest.TestCase):
    def test_stored_evidence_is_rescored_without_changing_original(self):
        case = {"id": "synthetic-case", "ability": "recall", "steps": [
            {"id": "teach", "session": "a"}, {"id": "probe", "session": "b"}],
            "checks": [{"id": "value", "kind": "reply_equals", "step": "probe",
                        "path": "value", "equals": 7}]}
        dataset = {"schema": "kmb.tasks.v1", "cases": [case]}
        evidence = {"synthetic-case": {"workspace": ".", "turns": [
            {"step": "probe", "reply": '```json\n{"value":7}\n```', "source": "synthetic:test"}],
            "files": {}, "memory": {}, "errors": []}}
        old_scores = score_run([case], evidence, LEGACY_SCORING_VERSION)
        original = {"schema": "kmb.result.v1", "run_id": "synthetic-run",
                    "dataset_fingerprint": fingerprint(dataset), "evidence_class": "synthetic/fixture",
                    "agents": [{"name": "Synthetic", "kind": "fixture",
                                "evidence_class": "synthetic/fixture",
                                "config_fingerprint": "synthetic-config",
                                "scores": old_scores, "evidence": evidence}]}
        rescored, audit = rescore_result(dataset, original, "synthetic-source-sha")
        self.assertEqual(original["agents"][0]["scores"]["overall"], 0)
        self.assertEqual(rescored["agents"][0]["scores"]["overall"], 100)
        self.assertEqual(rescored["scoring_version"], SCORING_VERSION)
        self.assertEqual(rescored["agents"][0]["evidence"], evidence)
        self.assertEqual(audit["agents"][0]["changes"][0]["old_status"], "fail")
        self.assertEqual(audit["agents"][0]["changes"][0]["new_status"], "pass")


if __name__ == "__main__":
    unittest.main()
