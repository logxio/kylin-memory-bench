"""Dataset and evidence contracts shared by every adapter and the scorer."""

import hashlib
import json
from pathlib import Path


ABILITIES = ("retention", "recall", "update", "discrimination", "boundary", "task_reuse")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read_json(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_dataset(data):
    if data.get("schema") != "kmb.tasks.v1":
        raise ValueError("dataset schema must be kmb.tasks.v1")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("dataset must contain cases")
    case_ids = set()
    for case in cases:
        case_id = case["id"]
        if case_id in case_ids:
            raise ValueError("duplicate case id: " + case_id)
        case_ids.add(case_id)
        if case["ability"] not in ABILITIES:
            raise ValueError("unknown ability: " + case["ability"])
        steps = case["steps"]
        step_ids = [step["id"] for step in steps]
        if len(step_ids) != len(set(step_ids)) or len(set(s["session"] for s in steps)) < 2:
            raise ValueError(case_id + " needs unique steps across at least two sessions")
        for check in case["checks"]:
            if check["kind"] not in ("reply_equals", "file_equals", "forbidden_text", "memory_forbidden"):
                raise ValueError("unknown check kind: " + check["kind"])
            if check["kind"] == "reply_equals" and check["step"] not in step_ids:
                raise ValueError("check references absent step")
            if check["kind"] in ("file_equals", "forbidden_text") and "file" in check:
                safe_relative(check["file"])
    return data


def safe_relative(value):
    path = Path(value)
    if path.is_absolute() or not value or ".." in path.parts or value.startswith("."):
        raise ValueError("file path must be relative to the case workspace: " + value)
    return path


def json_at(value, key):
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(key)
        value = value[part]
    return value
