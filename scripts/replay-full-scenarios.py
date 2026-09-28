#!/usr/bin/env python3
"""Rescore the published three-run live excerpt without invoking agents."""

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kylin_memory_bench.model import fingerprint, validate_dataset  # noqa: E402
from kylin_memory_bench.report import text_report  # noqa: E402
from kylin_memory_bench.rescore import score_signature  # noqa: E402
from kylin_memory_bench.scoring import score_run  # noqa: E402
from kylin_memory_bench.summarize import summarize  # noqa: E402


SAMPLE = ROOT / "examples/live-openkylin-20260927-v022-full-replay.json"
SAMPLE_SHA = ROOT / "examples/live-openkylin-20260927-v022-full-replay.sha256"
PROVENANCE = ROOT / "examples/live-openkylin-20260927-v022-provenance.json"
SUMMARY = ROOT / "examples/live-openkylin-20260927-v022-repeat-summary.json"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def published_reason(reason):
    """Match the existing public report's value-free reason wording."""
    generic = {
        "Answer field differs:": "Answer field differs from the expected value.",
        "Observed file field differs:": "Observed file field differs from the expected value.",
        "Reply exists but the required JSON field is invalid:":
            "Reply exists but the required JSON field is invalid.",
    }
    for prefix, replacement in generic.items():
        if reason.startswith(prefix):
            return replacement
    return reason


def check_published_scores(actual, published, label):
    require(score_signature(actual) == score_signature(published),
            label + ": statuses or scores differ from public provenance")
    for case, expected_case in zip(actual["cases"], published["cases"], strict=True):
        for check, expected in zip(case["checks"], expected_case["checks"], strict=True):
            require(published_reason(check["reason"]) == expected["reason"] and
                    sorted(check["sources"]) == sorted(expected["sources"]),
                    label + "/" + case["id"] + "/" + check["id"] +
                    ": reason or source differs from public provenance")


def main():
    sample_hash = hashlib.sha256(SAMPLE.read_bytes()).hexdigest()
    expected_hash = SAMPLE_SHA.read_text(encoding="utf-8").split()[0]
    require(sample_hash == expected_hash, "public sample hash differs from checksum file")
    dataset = validate_dataset(read_json(ROOT / "data/tasks.json"))
    bundle = read_json(SAMPLE)
    provenance = read_json(PROVENANCE)
    published_summary = read_json(SUMMARY)
    require(bundle["schema"] == "kmb.offline-full-replay.v1", "unknown replay schema")
    require(bundle["evidence_class"] == provenance["evidence_class"] == "live/observed",
            "evidence class differs")
    require(bundle["dataset_fingerprint"] == provenance["dataset_fingerprint"] == fingerprint(dataset),
            "dataset fingerprint differs")
    require(bundle["scoring_version"] == provenance["scoring_version"],
            "scoring version differs")
    require(len(bundle["runs"]) == len(provenance["runs"]) == 3, "expected three runs")

    results = []
    for number, (run, published_run) in enumerate(zip(bundle["runs"], provenance["runs"], strict=True), 1):
        require(run["run_id"] == published_run["run_id"] and
                run["source_result_sha256"] == published_run["raw_result_sha256"],
                f"batch {number}: run ID or declared source hash differs")
        require(len(run["agents"]) == len(published_run["agents"]) == 2,
                f"batch {number}: expected two agents")
        result = {"schema": "kmb.result.v1", "run_id": run["run_id"],
                  "elapsed_seconds": run["elapsed_seconds"],
                  "dataset_fingerprint": bundle["dataset_fingerprint"],
                  "scoring_version": bundle["scoring_version"],
                  "evidence_class": bundle["evidence_class"], "agents": []}
        report_agents = []
        for agent, published_agent in zip(run["agents"], published_run["agents"], strict=True):
            require(all(agent[key] == published_agent[key] for key in
                        ("name", "kind", "evidence_class", "config_fingerprint")),
                    f"batch {number}: agent identity or configuration differs")
            evidence = {case_id: {"workspace": ".", **record}
                        for case_id, record in agent["evidence"].items()}
            scores = score_run(dataset["cases"], evidence, bundle["scoring_version"])
            check_published_scores(scores, published_agent["scores"],
                                   f"batch {number}/{agent['name']}")
            result["agents"].append({**agent, "scores": scores})
            report_agents.append({"name": agent["name"],
                                  "evidence_class": agent["evidence_class"],
                                  "scores": published_agent["scores"]})
        report = ROOT / f"examples/live-openkylin-20260927-v022-full-{number}-report.txt"
        rendered = text_report({"evidence_class": bundle["evidence_class"],
                                "dataset_fingerprint": bundle["dataset_fingerprint"],
                                "agents": report_agents})
        require(rendered.strip() == report.read_text(encoding="utf-8").strip(),
                f"batch {number}: public report differs from provenance")
        results.append((run["run_id"], result))

    summary = summarize(dataset, results)
    require(summary == published_summary, "three-run summary differs from public summary")

    for number, (source, result) in enumerate(results, 1):
        print(f"Batch {number} / {source}")
        for agent in result["agents"]:
            scores = agent["scores"]
            print(f"  {agent['name']}: overall={scores['overall']:.2f}")
            for ability, value in scores["dimensions"].items():
                print(f"    {ability}={value:.2f}")
            for case in scores["cases"]:
                print(f"    {case['id']}={case['score']:.2f}")
                for check in case["checks"]:
                    print(f"      {check['id']}={check['status']}: {check['reason']}")
        print("  declared source result.json sha256:", bundle["runs"][number - 1]["source_result_sha256"])
    print("Three-run summary")
    for agent in summary["agents"]:
        overall = agent["overall"]
        print(f"  {agent['name']}: mean={overall['mean']:.2f} "
              f"sample_stddev={overall['sample_stddev']:.2f} "
              f"steps={agent['completed_steps']}/{agent['expected_steps']} "
              f"timeouts={agent['timeout_error_count']}")
        for ability, values in agent["dimensions"].items():
            print(f"    {ability}: mean={values['mean']:.2f} "
                  f"sample_stddev={values['sample_stddev']:.2f}")
    evaluated_cases = sum(len(agent["scores"]["cases"]) for _, result in results
                          for agent in result["agents"])
    evaluated_checks = sum(len(case["checks"]) for _, result in results
                           for agent in result["agents"] for case in agent["scores"]["cases"])
    print("public sample sha256:", sample_hash)
    print(f"Recomputed {evaluated_checks} checks across {evaluated_cases} agent-case evaluations; "
          "public provenance, reports and summary agree.")


if __name__ == "__main__":
    main()
