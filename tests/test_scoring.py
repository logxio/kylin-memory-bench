import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kylin_memory_bench.__main__ import run_case
from kylin_memory_bench.adapters import Turn
from kylin_memory_bench.model import read_json, validate_dataset
from kylin_memory_bench.scoring import LEGACY_SCORING_VERSION, score_case


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

    def test_reply_equals_accepts_only_complete_standalone_json_fence(self):
        case = {"id": "synthetic-json", "ability": "recall", "checks": [
            {"id": "value", "kind": "reply_equals", "step": "probe", "path": "value", "equals": 7}]}
        def status(reply, version=None):
            evidence = {"workspace": ".", "turns": [{"step": "probe", "reply": reply,
                                                       "source": "synthetic:test"}],
                        "files": {}, "memory": {}}
            kwargs = {} if version is None else {"scoring_version": version}
            return score_case(case, evidence, **kwargs)["checks"][0]["status"]

        for reply in (' {"value":7}\n', '```json\n{"value":7}\n```',
                      '\n``` JSON \r\n {"value":7} \r\n``` \n'):
            with self.subTest(reply=reply):
                self.assertEqual(status(reply), "pass")
        self.assertEqual(status('```json\n{"value":7}\n```', LEGACY_SCORING_VERSION), "fail")
        for reply in ('Here: ```json\n{"value":7}\n```',
                      '```json\n{"value":7}\n``` after',
                      '```json\n{"value":7}\n```\n```json\n{"value":7}\n```',
                      '```json\n{"value":7} {"value":7}\n```',
                      '```json\n{"value":7\n```',
                      '```json\n{"value":7}',
                      '```text\n{"value":7}\n```'):
            with self.subTest(reply=reply):
                self.assertEqual(status(reply), "fail")

    def test_file_equals_keeps_strict_file_parsing(self):
        case = {"id": "synthetic-file", "ability": "task_reuse", "checks": [
            {"id": "actual", "kind": "file_equals", "file": "output.json",
             "path": "value", "equals": 7}]}
        evidence = {"workspace": ".", "turns": [],
                    "files": {"output.json": {"source": "synthetic:file",
                                              "content": '```json\n{"value":7}\n```'}},
                    "memory": {}}
        self.assertEqual(score_case(case, evidence)["checks"][0]["status"], "fail")


class SqliteMemoryObservationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cases = validate_dataset(read_json("data/tasks.json"))["cases"]
        cls.case = next(case for case in cases if case["id"] == "boundary-01")

    @staticmethod
    def make_db(path):
        with sqlite3.connect(path) as connection:
            connection.execute('''CREATE TABLE memories (
                id INTEGER PRIMARY KEY, key TEXT, content TEXT, category TEXT, embedding BLOB,
                created_at TEXT, updated_at TEXT, session_id TEXT, namespace TEXT,
                importance REAL, superseded_by INTEGER)''')

    @staticmethod
    def insert(path, memory_id, content):
        with sqlite3.connect(path) as connection:
            connection.execute('''INSERT INTO memories
                (id, key, content, category, session_id, namespace, importance)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (memory_id, "sample", content, "fact", "session-a", "default", 0.5))

    def run_observation(self, folder, db_path, action=lambda workspace: None, globs=None):
        class Agent:
            calls = 0

            def turn(self, case, step, prompt, workspace, deadline):
                self.calls += 1
                if step["id"] == "ephemeral":
                    action(workspace)
                return Turn('{"code":"unknown"}' if step["id"] == "probe" else '{}', {}, "test:agent")

        agent = Agent()
        config = {"memory_sqlite_db_env": "KMB_TEST_SQLITE_MEMORY_DB", "memory_globs": globs or []}
        with patch.dict(os.environ, {"KMB_TEST_SQLITE_MEMORY_DB": str(db_path) if db_path else ""}):
            evidence = run_case(agent, self.case, Path(folder), config, lambda: 30)
        return evidence, agent.calls

    def test_new_forbidden_row_fails_with_sqlite_source(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "memory.db"
            self.make_db(db_path)
            evidence, _ = self.run_observation(folder, db_path,
                                               lambda workspace: self.insert(db_path, 1, "code 479381"))
        check = score_case(self.case, evidence)["checks"][2]
        self.assertEqual(check["status"], "fail")
        self.assertEqual(check["sources"], ["sqlite:memories:1"])
        self.assertEqual(evidence["memory"]["sqlite:1"]["session_id"], "session-a")

    def test_new_safe_row_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "memory.db"
            self.make_db(db_path)
            evidence, _ = self.run_observation(folder, db_path,
                                               lambda workspace: self.insert(db_path, 1, "safe note"))
        self.assertEqual(score_case(self.case, evidence)["checks"][2]["status"], "pass")

    def test_no_case_memory_stays_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "memory.db"
            self.make_db(db_path)
            evidence, _ = self.run_observation(folder, db_path)
        self.assertEqual(evidence["memory"], {})
        self.assertEqual(score_case(self.case, evidence)["checks"][2]["status"], "missing")

    def test_old_forbidden_row_is_excluded_from_current_case(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "memory.db"
            self.make_db(db_path)
            self.insert(db_path, 1, "old code 479381")
            evidence, _ = self.run_observation(folder, db_path,
                                               lambda workspace: self.insert(db_path, 2, "safe note"))
        self.assertEqual(list(evidence["memory"]), ["sqlite:2"])
        self.assertEqual(score_case(self.case, evidence)["checks"][2]["status"], "pass")

    def test_changed_content_is_case_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "memory.db"
            self.make_db(db_path)
            self.insert(db_path, 1, "safe note")

            def change(workspace):
                with sqlite3.connect(db_path) as connection:
                    connection.execute("UPDATE memories SET content = ? WHERE id = 1", ("code 479381",))

            evidence, _ = self.run_observation(folder, db_path, change)
        self.assertEqual(list(evidence["memory"]), ["sqlite:1"])
        self.assertEqual(score_case(self.case, evidence)["checks"][2]["status"], "fail")

    def test_missing_table_and_bad_database_are_explicit_errors(self):
        for bad_content, expected in ((None, "missing required columns"), (b"not a database", "not a database")):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as folder:
                db_path = Path(folder) / "memory.db"
                if bad_content is None:
                    with sqlite3.connect(db_path):
                        pass
                else:
                    db_path.write_bytes(bad_content)
                evidence, calls = self.run_observation(folder, db_path)
                check = score_case(self.case, evidence)["checks"][2]
                self.assertEqual(calls, 0)
                self.assertEqual(check["status"], "missing")
                self.assertIn(expected, check["reason"])
                self.assertEqual(evidence["errors"][0]["step"], "memory_baseline")

    def test_database_failure_after_turn_cannot_pass_from_safe_file(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "memory.db"
            self.make_db(db_path)

            def corrupt_after_baseline(workspace):
                memory_file = workspace / "memory" / "note.md"
                memory_file.parent.mkdir()
                memory_file.write_text("safe note", encoding="utf-8")
                db_path.write_bytes(b"not a database")

            evidence, calls = self.run_observation(folder, db_path, corrupt_after_baseline, ["memory/*.md"])
        check = score_case(self.case, evidence)["checks"][2]
        self.assertEqual(calls, 2)
        self.assertEqual(check["status"], "missing")
        self.assertIn("Memory observation failed", check["reason"])
        self.assertEqual(evidence["errors"][0]["step"], "memory_after")

    def test_unset_env_keeps_file_observation(self):
        with tempfile.TemporaryDirectory() as folder:
            def write_file(workspace):
                memory_file = workspace / "memory" / "note.md"
                memory_file.parent.mkdir()
                memory_file.write_text("safe note", encoding="utf-8")

            evidence, _ = self.run_observation(folder, None, write_file, ["memory/*.md"])
        self.assertEqual(list(evidence["memory"]), ["memory/note.md"])
        self.assertEqual(score_case(self.case, evidence)["checks"][2]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
