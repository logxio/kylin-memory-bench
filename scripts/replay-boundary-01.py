#!/usr/bin/env python3
"""Rescore the public boundary-01 excerpt with the repository scorer."""

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kylin_memory_bench.scoring import score_case  # noqa: E402


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    sample_path = ROOT / "examples/live-openkylin-20260927-v022-boundary-01-replay.json"
    sample = read_json(sample_path)
    dataset = read_json(ROOT / "data/tasks.json")
    provenance = read_json(ROOT / "examples/live-openkylin-20260927-v022-provenance.json")
    case = next(item for item in dataset["cases"] if item["id"] == sample["case_id"])
    run = provenance["runs"][0]
    assert sample["case_id"] == "boundary-01"
    assert sample["run_id"] == run["run_id"]
    assert sample["source_result_sha256"] == run["raw_result_sha256"]
    assert sample["dataset_fingerprint"] == provenance["dataset_fingerprint"]
    assert sample["scoring_version"] == provenance["scoring_version"]

    for agent, published in zip(sample["agents"], run["agents"], strict=True):
        assert agent["name"] == published["name"]
        # score_case requires workspace and files even though these checks do not use them.
        evidence = {"workspace": ".", "files": {}, **agent["evidence"]}
        result = score_case(case, evidence, sample["scoring_version"])
        expected = next(item for item in published["scores"]["cases"] if item["id"] == "boundary-01")
        assert result == expected, f"Published result differs for {agent['name']}"
        statuses = " ".join(f"{check['id']}={check['status']}" for check in result["checks"])
        print(f"{agent['name']}: {statuses} score={result['score']:.2f}")

    print(f"sample sha256: {hashlib.sha256(sample_path.read_bytes()).hexdigest()}")
    print(f"source result.json sha256: {sample['source_result_sha256']}")


if __name__ == "__main__":
    main()
