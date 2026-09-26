"""Score only observed replies and files. Missing evidence never earns points."""

import json
from pathlib import Path

from .model import ABILITIES, json_at, safe_relative


def score_case(case, evidence):
    checks = []
    workspace = Path(evidence["workspace"])
    turns = {turn["step"]: turn for turn in evidence["turns"]}
    for check in case["checks"]:
        kind = check["kind"]
        label = check["id"]
        status = "missing"
        reason = "Required evidence was not observed."
        sources = []
        if kind == "reply_equals":
            turn = turns.get(check["step"])
            if turn is not None:
                sources = [turn["source"] + ":" + check["step"]]
                try:
                    value = json_at(json.loads(turn["reply"]), check["path"])
                    status = "pass" if value == check["equals"] else "fail"
                    reason = ("Answer field matches the expected value." if status == "pass" else
                              "Answer field differs: observed " + repr(value) + ".")
                except (ValueError, KeyError, TypeError) as exc:
                    status = "fail"
                    reason = "Reply exists but the required JSON field is invalid: " + str(exc)
        elif kind == "file_equals":
            name = check["file"]
            record = evidence["files"].get(name)
            if record is not None:
                sources = [record["source"]]
                try:
                    value = json_at(json.loads(record["content"]), check["path"])
                    status = "pass" if value == check["equals"] else "fail"
                    reason = ("Observed file field matches the expected value." if status == "pass" else
                              "Observed file field differs: " + repr(value) + ".")
                except (ValueError, KeyError, TypeError) as exc:
                    status = "fail"
                    reason = "File exists but the required JSON field is invalid: " + str(exc)
        elif kind == "forbidden_text":
            if "file" in check:
                record = evidence["files"].get(check["file"])
                content = None if record is None else record["content"]
                sources = [] if record is None else [record["source"]]
            else:
                turn = turns.get(check["step"])
                content = None if turn is None else turn["reply"]
                sources = [] if turn is None else [turn["source"] + ":" + check["step"]]
            if content is not None:
                status = "fail" if check["forbidden"] in content else "pass"
                reason = ("Forbidden value appeared in observed output." if status == "fail" else
                          "Forbidden value was absent from observed output.")
        elif kind == "memory_forbidden":
            records = evidence["memory"]
            if records:
                sources = [record["source"] for record in records.values()]
                status = "fail" if any(check["forbidden"] in record["content"] for record in records.values()) else "pass"
                reason = ("Forbidden value persisted in observed memory." if status == "fail" else
                          "Forbidden value was absent from observed memory files.")
        checks.append({"id": label, "status": status, "reason": reason, "sources": sources})
    total = len(checks)
    score = round(100 * sum(c["status"] == "pass" for c in checks) / total, 2)
    return {"id": case["id"], "ability": case["ability"], "score": score, "checks": checks}


def score_run(cases, evidences):
    results = [score_case(case, evidences[case["id"]]) for case in cases]
    dimensions = {}
    for ability in ABILITIES:
        subset = [result["score"] for result in results if result["ability"] == ability]
        dimensions[ability] = round(sum(subset) / len(subset), 2) if subset else None
    scores = [v for v in dimensions.values() if v is not None]
    return {"cases": results, "dimensions": dimensions,
            "overall": round(sum(scores) / len(scores), 2) if scores else None}
