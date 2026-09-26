"""Recompute stored runs from evidence without invoking either agent."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from .model import fingerprint, read_json, validate_dataset
from .scoring import (LEGACY_SCORING_VERSION, SCORING_VERSION,
                      parse_reply_json, score_run)
from .summarize import summarize


def score_signature(scores):
    return (scores["dimensions"], scores["overall"],
            [(case["id"], case["ability"], case["score"],
              [(check["id"], check["status"]) for check in case["checks"]])
             for case in scores["cases"]])


def rescore_result(dataset, original, source_sha256):
    if original.get("schema") != "kmb.result.v1" or original.get("dataset_fingerprint") != fingerprint(dataset):
        raise ValueError("source result schema or dataset fingerprint differs")
    source_version = original.get("scoring_version", LEGACY_SCORING_VERSION)
    if source_version != LEGACY_SCORING_VERSION:
        raise ValueError("source must use the v0.2.0 strict scoring version")
    cases = dataset["cases"]
    rescored = copy.deepcopy(original)
    rescored["scoring_version"] = SCORING_VERSION
    rescored["rescored_from"] = {"source_sha256": source_sha256,
                                  "scoring_version": source_version}
    audit = {"schema": "kmb.rescore-audit.v1", "run_id": original["run_id"],
             "source_result_sha256": source_sha256,
             "dataset_fingerprint": original["dataset_fingerprint"],
             "source_scoring_version": source_version,
             "scoring_version": SCORING_VERSION, "agents": []}
    for old_agent, new_agent in zip(original["agents"], rescored["agents"]):
        old_scores = old_agent["scores"]
        strict_scores = score_run(cases, old_agent["evidence"], source_version)
        if score_signature(old_scores) != score_signature(strict_scores):
            raise ValueError(original["run_id"] + ": stored strict scores differ from raw evidence")
        new_scores = score_run(cases, old_agent["evidence"], SCORING_VERSION)
        new_agent["scores"] = new_scores
        agent_audit = {"name": old_agent["name"], "kind": old_agent["kind"],
                       "config_fingerprint": old_agent["config_fingerprint"],
                       "old_overall": old_scores["overall"], "new_overall": new_scores["overall"],
                       "old_dimensions": old_scores["dimensions"],
                       "new_dimensions": new_scores["dimensions"],
                       "accepted_json_fence_steps": [], "cases": [], "changes": []}
        for case in cases:
            evidence = old_agent["evidence"][case["id"]]
            turns = {turn["step"]: turn for turn in evidence["turns"]}
            for step in {check["step"] for check in case["checks"] if check["kind"] == "reply_equals"}:
                if step in turns:
                    try:
                        _, fenced = parse_reply_json(turns[step]["reply"], SCORING_VERSION)
                    except (ValueError, TypeError):
                        continue
                    if fenced:
                        agent_audit["accepted_json_fence_steps"].append({"case_id": case["id"], "step": step})
        for case, old_case, new_case in zip(cases, old_scores["cases"], new_scores["cases"]):
            case_checks = []
            for contract, old_check, new_check in zip(case["checks"], old_case["checks"], new_case["checks"]):
                item = {"id": contract["id"], "kind": contract["kind"],
                        "old_status": old_check["status"], "new_status": new_check["status"]}
                case_checks.append(item)
                if old_check["status"] != new_check["status"]:
                    if contract["kind"] != "reply_equals":
                        raise ValueError(original["run_id"] + ": a non-reply check changed")
                    agent_audit["changes"].append({"case_id": case["id"], "check_id": contract["id"],
                                                   "old_status": old_check["status"],
                                                   "new_status": new_check["status"],
                                                   "old_case_score": old_case["score"],
                                                   "new_case_score": new_case["score"],
                                                   "reason": "Standalone JSON code fence parsed as complete JSON; field compared with the unchanged expected value."})
            agent_audit["cases"].append({"id": case["id"], "ability": case["ability"],
                                         "old_score": old_case["score"],
                                         "new_score": new_case["score"], "checks": case_checks})
        agent_audit["audited_checks"] = sum(len(case["checks"]) for case in agent_audit["cases"])
        audit["agents"].append(agent_audit)
    return rescored, audit


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rescore stored v0.2.0 results without running agents")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True, help="new directory; existing output is never overwritten")
    parser.add_argument("results", nargs="+", help="original result.json files")
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        parser.error("output already exists; source evidence and earlier rescoring are never overwritten")
    dataset = validate_dataset(read_json(args.dataset))
    processed = []
    for name in args.results:
        data = Path(name).read_bytes()
        source_sha256 = hashlib.sha256(data).hexdigest()
        rescored, audit = rescore_result(dataset, json.loads(data), source_sha256)
        processed.append((rescored, audit))
    summary = summarize(dataset, [(item[0]["run_id"], item[0]) for item in processed])
    output.mkdir(parents=True)
    for rescored, audit in processed:
        run_dir = output / rescored["run_id"]
        run_dir.mkdir()
        payload = (json.dumps(rescored, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
        (run_dir / "result.json").write_bytes(payload)
        audit["rescored_result_sha256"] = hashlib.sha256(payload).hexdigest()
    (output / "audit.json").write_text(json.dumps({"schema": "kmb.rescore-audit-set.v1",
                                                   "runs": [item[1] for item in processed]},
                                                  ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                                           encoding="utf-8")
    (output / "repeat-summary.json").write_text(json.dumps(summary, ensure_ascii=False,
                                                             indent=2, sort_keys=True) + "\n",
                                                encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
