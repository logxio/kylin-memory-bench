"""One entry point for fixture and live agents."""

import argparse
import json
import os
import resource
import sqlite3
import sys
import time
import uuid
from contextlib import closing
from pathlib import Path

from .adapters import make_agent
from .model import fingerprint, read_json, safe_relative, validate_dataset
from .report import radar_svg, text_report
from .scoring import SCORING_VERSION, score_run


def observe_memory_files(workspace, config):
    memory = {}
    memory_root_env = config.get("memory_root_env")
    memory_root = Path(os.environ[memory_root_env]).expanduser() if memory_root_env and os.environ.get(memory_root_env) else workspace
    for pattern in config.get("memory_globs", []):
        safe_relative(pattern)
        for path in sorted(memory_root.glob(pattern)):
            if path.is_file() and path.resolve().is_relative_to(memory_root.resolve()):
                name = str(path.relative_to(memory_root))
                memory[name] = {"source": "filesystem:" + name, "content": path.read_text(encoding="utf-8")}
    return memory


def observe_sqlite_memory(config):
    env_name = config.get("memory_sqlite_db_env")
    db_name = os.environ.get(env_name) if env_name else None
    if not db_name:
        return None
    db_uri = Path(db_name).expanduser().resolve().as_uri() + "?mode=ro"
    columns_needed = {"id", "key", "content", "category", "embedding", "created_at", "updated_at",
                      "session_id", "namespace", "importance", "superseded_by"}
    try:
        with closing(sqlite3.connect(db_uri, uri=True, timeout=2)) as connection:
            connection.execute("PRAGMA query_only = ON")
            columns = {row[1] for row in connection.execute('PRAGMA table_info("memories")')}
            missing = columns_needed - columns
            if missing:
                raise ValueError("SQLite memories table missing required columns: " + ", ".join(sorted(missing)))
            records = {}
            query = ('SELECT "id", "key", "content", "category", "created_at", "updated_at", '
                     '"session_id", "namespace", "importance", "superseded_by" FROM "memories"')
            for row in connection.execute(query):
                memory_id, key, content, category, created_at, updated_at, session_id, namespace, importance, superseded_by = row
                if not isinstance(content, str):
                    raise ValueError("SQLite memories.content is not text for id " + str(memory_id))
                records["sqlite:" + str(memory_id)] = {
                    "source": "sqlite:memories:" + str(memory_id), "id": memory_id, "key": key,
                    "content": content, "category": category, "created_at": created_at,
                    "updated_at": updated_at, "session_id": session_id, "namespace": namespace,
                    "importance": importance, "superseded_by": superseded_by,
                }
            return records
    except sqlite3.Error as exc:
        raise RuntimeError("SQLite memory read failed: " + type(exc).__name__ + ": " + str(exc)) from exc


def observe_files(workspace, case, config):
    names = {check["file"] for check in case["checks"] if "file" in check}
    files = {}
    for name in sorted(names):
        path = workspace / safe_relative(name)
        if path.is_file() and path.resolve().is_relative_to(workspace.resolve()):
            content = path.read_text(encoding="utf-8")
            files[name] = {"source": "filesystem:" + name, "content": content,
                           "sha256": fingerprint(content)}
    memory = observe_memory_files(workspace, config)
    return files, memory


def run_case(agent, case, root, config, remaining):
    workspace = root / case["id"]
    workspace.mkdir(parents=True)
    turns = []
    errors = []
    try:
        sqlite_before = observe_sqlite_memory(config)
        files_before = observe_memory_files(workspace, config) if sqlite_before is not None else None
    except (OSError, ValueError, RuntimeError) as exc:
        message = "Memory baseline failed: " + str(exc)
        return {"workspace": str(workspace), "turns": turns, "files": {}, "memory": {},
                "errors": [{"step": "memory_baseline", "type": type(exc).__name__, "message": message}],
                "memory_error": message}
    for step in case["steps"]:
        seconds_left = remaining()
        if seconds_left <= 0:
            errors.append({"step": step["id"], "type": "TimeoutError",
                           "message": "whole-run deadline reached"})
            break
        prompt = step["prompt"].replace("{workspace}", str(workspace))
        turn_started = time.monotonic()
        try:
            turn = agent.turn(case, step, prompt, workspace,
                              min(seconds_left, config.get("turn_timeout_seconds", 20)))
            turns.append({"step": step["id"], "session": step["session"],
                          "prompt": prompt, "reply": turn.reply, "raw": turn.raw,
                          "source": turn.source, "screenshot": turn.screenshot,
                          "duration_seconds": round(time.monotonic() - turn_started, 3)})
        except Exception as exc:
            error_type = ("TimeoutError" if isinstance(exc, TimeoutError) or
                          type(exc).__name__ in ("TimeoutExpired", "WebSocketTimeoutException")
                          else type(exc).__name__)
            errors.append({"step": step["id"], "type": error_type, "message": str(exc),
                           "duration_seconds": round(time.monotonic() - turn_started, 3)})
            break
    files, memory = observe_files(workspace, case, config)
    if sqlite_before is not None:
        try:
            sqlite_after = observe_sqlite_memory(config)
            if sqlite_after is None:
                raise ValueError("SQLite memory database environment variable became unset during the case")
            memory = {name: record for name, record in memory.items()
                      if name not in files_before or files_before[name]["content"] != record["content"]}
            memory.update({name: record for name, record in sqlite_after.items()
                           if name not in sqlite_before or sqlite_before[name]["content"] != record["content"]})
        except (OSError, ValueError, RuntimeError) as exc:
            message = "Memory observation failed: " + str(exc)
            errors.append({"step": "memory_after", "type": type(exc).__name__, "message": message})
            return {"workspace": str(workspace), "turns": turns, "files": files, "memory": {},
                    "errors": errors, "memory_error": message}
    return {"workspace": str(workspace), "turns": turns, "files": files,
            "memory": memory, "errors": errors}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Score long-term memory from actual agent evidence")
    parser.add_argument("--dataset", default="data/tasks.json")
    parser.add_argument("--agent", action="append", required=True, help="agent config JSON; repeat for comparison")
    parser.add_argument("--output", required=True, help="new output directory")
    parser.add_argument("--case", help="run one case for a small smoke test")
    parser.add_argument("--max-seconds", type=int, default=240)
    args = parser.parse_args(argv)
    if not 1 <= args.max_seconds <= 3600:
        parser.error("--max-seconds must be between 1 and 3600 (use at most 240 on a local machine)")
    if sys.platform.startswith("linux"):
        limit = 4 * 1024 ** 3
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        resource.setrlimit(resource.RLIMIT_AS, (min(soft, limit) if soft > 0 else limit,
                                               min(hard, limit) if hard > 0 else limit))
    started = time.monotonic()
    output = Path(args.output)
    if output.exists():
        parser.error("output directory already exists; choose a new path to preserve raw evidence")
    dataset = validate_dataset(read_json(args.dataset))
    cases = [case for case in dataset["cases"] if args.case is None or case["id"] == args.case]
    if not cases:
        parser.error("case not found: " + str(args.case))
    configs = [read_json(path) for path in args.agent]
    if len({config["name"] for config in configs}) != len(configs):
        parser.error("agent names must be unique")
    if any(config["kind"] == "fixture" for config in configs) and not all(config["kind"] == "fixture" for config in configs):
        parser.error("fixture and live agent configurations cannot be mixed in one report")
    output.mkdir(parents=True)
    run_id = uuid.uuid4().hex[:12]
    def remaining():
        return args.max_seconds - (time.monotonic() - started)
    agents = []
    for config in configs:
        name = config["name"]
        root = output / name
        root.mkdir()
        runtime_config = dict(config)
        runtime_config["session_prefix"] = str(config.get("session_prefix", "kmb")) + ":" + run_id
        adapter = make_agent(runtime_config, root)
        evidences = {case["id"]: run_case(adapter, case, root, runtime_config, remaining) for case in cases}
        evidence_class = "synthetic/fixture" if config["kind"] == "fixture" else "live/observed"
        scores = score_run(cases, evidences)
        agents.append({"name": name, "kind": config["kind"], "evidence_class": evidence_class,
                       "config_fingerprint": fingerprint(config), "scores": scores,
                       "evidence": evidences})
    result = {"schema": "kmb.result.v1", "scoring_version": SCORING_VERSION,
              "run_id": run_id, "dataset_fingerprint": fingerprint(dataset),
              "evidence_class": "synthetic/fixture" if all(a["kind"] == "fixture" for a in agents) else "live/observed",
              "elapsed_seconds": round(time.monotonic() - started, 3), "agents": agents}
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output / "report.txt").write_text(text_report(result), encoding="utf-8")
    (output / "radar.svg").write_text(radar_svg(result), encoding="utf-8")
    print("Evidence: " + str(output / "result.json"))
    print("Report:   " + str(output / "report.txt"))
    print("Radar:    " + str(output / "radar.svg"))
    print("Elapsed seconds: %.3f" % (time.monotonic() - started))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
