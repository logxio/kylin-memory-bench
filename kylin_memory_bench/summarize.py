"""Summarize repeated full runs without modifying their raw evidence."""

import argparse
import json
import statistics
from pathlib import Path

from .model import ABILITIES, fingerprint, read_json, validate_dataset


def stats(values):
    return {"n": len(values), "mean": round(statistics.mean(values), 2),
            "sample_stddev": round(statistics.stdev(values), 2) if len(values) > 1 else None}


def summarize(dataset, inputs):
    if not inputs:
        raise ValueError("at least one result is required")
    cases = dataset["cases"]
    expected_cases = {case["id"]: case for case in cases}
    expected_steps = [(case["id"], step["id"]) for case in cases for step in case["steps"]]
    dataset_hash = fingerprint(dataset)
    baseline = None
    results = []
    seen_run_ids = set()
    for source, result in inputs:
        if result.get("schema") != "kmb.result.v1" or result.get("dataset_fingerprint") != dataset_hash:
            raise ValueError(source + ": result schema or dataset fingerprint differs")
        run_id = result.get("run_id")
        if not isinstance(run_id, str) or run_id in seen_run_ids:
            raise ValueError(source + ": missing or repeated run ID")
        seen_run_ids.add(run_id)
        agents = result.get("agents", [])
        if agents and (result.get("evidence_class") != agents[0].get("evidence_class") or
                       any(a.get("evidence_class") != agents[0].get("evidence_class") for a in agents)):
            raise ValueError(source + ": evidence class differs inside result")
        signature = tuple((a.get("name"), a.get("kind"), a.get("evidence_class"),
                           a.get("config_fingerprint")) for a in agents)
        if not signature or len({part[0] for part in signature}) != len(signature):
            raise ValueError(source + ": missing or repeated agent")
        if baseline is None:
            baseline = signature
        elif signature != baseline:
            raise ValueError(source + ": agent set, order, evidence class, or config fingerprint differs")
        for agent in agents:
            score_cases = agent.get("scores", {}).get("cases", [])
            if {item.get("id") for item in score_cases} != set(expected_cases) or len(score_cases) != len(cases):
                raise ValueError(source + ": case scores are not a full dataset run")
            if set(agent.get("evidence", {})) != set(expected_cases):
                raise ValueError(source + ": case evidence is not a full dataset run")
            if any(item.get("ability") != expected_cases[item["id"]]["ability"] for item in score_cases):
                raise ValueError(source + ": case ability differs from dataset")
            for case_id, case in expected_cases.items():
                turns = agent["evidence"][case_id].get("turns", [])
                valid_steps = {step["id"] for step in case["steps"]}
                turn_steps = [turn.get("step") for turn in turns]
                if len(turn_steps) != len(set(turn_steps)) or not set(turn_steps) <= valid_steps:
                    raise ValueError(source + ": duplicate or unknown completed step")
        results.append(result)

    output = {"schema": "kmb.repeat-summary.v1", "dataset_fingerprint": dataset_hash,
              "evidence_class": results[0]["evidence_class"], "run_count": len(results),
              "run_ids": [result["run_id"] for result in results], "agents": []}
    for index, (name, kind, evidence_class, config_hash) in enumerate(baseline):
        agent_runs = [result["agents"][index] for result in results]
        step_counts = {case_id + "/" + step_id: 0 for case_id, step_id in expected_steps}
        runs = []
        timeout_count = 0
        for result, agent in zip(results, agent_runs):
            completed = 0
            errors = []
            for case_id, step_id in expected_steps:
                evidence = agent["evidence"][case_id]
                if any(turn.get("step") == step_id for turn in evidence.get("turns", [])):
                    step_counts[case_id + "/" + step_id] += 1
                    completed += 1
            for evidence in agent["evidence"].values():
                errors.extend(evidence.get("errors", []))
            timeouts = sum(error.get("type") == "TimeoutError" for error in errors)
            timeout_count += timeouts
            runs.append({"run_id": result["run_id"], "overall": agent["scores"]["overall"],
                         "dimensions": agent["scores"]["dimensions"],
                         "completed_steps": completed, "expected_steps": len(expected_steps),
                         "incomplete_steps": len(expected_steps) - completed,
                         "error_count": len(errors), "timeout_error_count": timeouts,
                         "elapsed_seconds": result.get("elapsed_seconds")})
        dimensions = {ability: stats([agent["scores"]["dimensions"][ability] for agent in agent_runs])
                      for ability in ABILITIES}
        output["agents"].append({"name": name, "kind": kind, "evidence_class": evidence_class,
                                 "config_fingerprint": config_hash, "runs": runs,
                                 "overall": stats([run["overall"] for run in runs]),
                                 "dimensions": dimensions,
                                 "steps": {key: {"completed": count, "attempted_runs": len(results),
                                                 "completion_rate": round(count / len(results), 4)}
                                           for key, count in step_counts.items()},
                                 "completed_steps": sum(step_counts.values()),
                                 "expected_steps": len(expected_steps) * len(results),
                                 "incomplete_steps": len(expected_steps) * len(results) - sum(step_counts.values()),
                                 "timeout_error_count": timeout_count})
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description="Summarize full repeated runs with identical dataset and agent configs")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True, help="new JSON file; existing output is never overwritten")
    parser.add_argument("results", nargs="+", help="result.json files from independent runs")
    args = parser.parse_args(argv)
    output_path = Path(args.output)
    if output_path.exists():
        parser.error("output already exists; raw and previous summaries are never overwritten")
    dataset = validate_dataset(read_json(args.dataset))
    inputs = [(path, read_json(path)) for path in args.results]
    try:
        summary = summarize(dataset, inputs)
    except (KeyError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
