"""Agent turns. Each adapter returns its raw response and an attributable reply."""

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .model import safe_relative


@dataclass
class Turn:
    reply: str
    raw: object
    source: str
    screenshot: str = ""


class Agent:
    def __init__(self, config, run_dir):
        self.config = config
        self.run_dir = Path(run_dir)

    def turn(self, case, step, prompt, workspace, deadline):
        raise NotImplementedError


class FixtureAgent(Agent):
    def turn(self, case, step, prompt, workspace, deadline):
        record = self.config["turns"].get(case["id"] + "/" + step["id"], {"reply": "{}"})
        for name, content in record.get("files", {}).items():
            target = workspace / safe_relative(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return Turn(record["reply"], record, "synthetic:fixture")


class OpenClawAgent(Agent):
    def turn(self, case, step, prompt, workspace, deadline):
        command = self.config.get("executable", "openclaw")
        if shutil.which(command) is None:
            raise RuntimeError("OpenClaw CLI not found: " + command)
        message_file = workspace / ("prompt-" + step["id"] + ".txt")
        message_file.write_text(prompt, encoding="utf-8")
        key = "kmb:" + self.config.get("session_prefix", "run") + ":" + case["id"] + ":" + step["session"]
        args = [command, "agent", "--agent", self.config.get("agent_id", "main"),
                "--session-key", key, "--message-file", str(message_file), "--json",
                "--timeout", str(max(1, int(deadline)))]
        completed = subprocess.run(args, text=True, capture_output=True, timeout=deadline, check=False)
        raw = {"argv": args[:-2] + ["--timeout", str(max(1, int(deadline)))],
               "exit_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
        if completed.returncode != 0:
            raise RuntimeError("OpenClaw turn failed: " + json.dumps(raw, ensure_ascii=False))
        try:
            envelope = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("OpenClaw did not return JSON: " + completed.stdout) from exc
        result = envelope.get("result", envelope)
        payloads = result.get("payloads", []) if isinstance(result, dict) else []
        reply = result.get("final") if isinstance(result, dict) else None
        if reply is None and payloads:
            reply = "\n".join(p["text"] for p in payloads if isinstance(p, dict) and isinstance(p.get("text"), str))
        if not isinstance(reply, str):
            raise RuntimeError("OpenClaw JSON had no reply text: " + completed.stdout)
        raw["envelope"] = envelope
        return Turn(reply, raw, "live:openclaw-cli")


class KylinBotAgent(Agent):
    """KylinBot Gateway's documented kylinbot.v1 WebSocket chat protocol."""

    def turn(self, case, step, prompt, workspace, deadline):
        try:
            import websocket
        except ImportError as exc:
            raise RuntimeError("KylinBot adapter needs websocket-client; install requirements.txt") from exc
        token = os.environ.get(self.config.get("token_env", "KYLINBOT_WS_TOKEN"))
        if not token:
            raise RuntimeError("KylinBot Gateway token environment variable is missing")
        from urllib.parse import urlparse
        url = self.config.get("url", "ws://127.0.0.1:42617/ws/chat")
        parsed = urlparse(url)
        if parsed.scheme not in ("ws", "wss") or not parsed.netloc:
            raise ValueError("KylinBot url must be ws:// or wss:// with a host")
        session_id = ":".join((self.config.get("session_prefix", "kmb"), case["id"], step["session"]))
        frames = []
        ws = websocket.create_connection(url, timeout=deadline,
                                         header=["Authorization: Bearer " + token.removeprefix("Bearer ")],
                                         subprotocols=["kylinbot.v1"])
        started = time.monotonic()
        try:
            connect = {"type": "connect", "session_id": session_id, "capabilities": ["chat"],
                       "mode": self.config.get("mode", "agentic"), "token_saving": False}
            ws.send(json.dumps(connect, ensure_ascii=False))
            while True:
                frame = json.loads(ws.recv())
                frames.append(frame)
                if frame.get("type") == "connected":
                    break
                if frame.get("type") == "error":
                    raise RuntimeError("KylinBot connect error: " + str(frame.get("message")))
                if time.monotonic() - started >= deadline:
                    raise TimeoutError("KylinBot connect timed out")
            ws.send(json.dumps({"type": "message", "content": prompt,
                                "mode": self.config.get("mode", "agentic"), "token_saving": False},
                               ensure_ascii=False))
            chunks = []
            while True:
                frame = json.loads(ws.recv())
                frames.append(frame)
                kind = frame.get("type")
                if kind == "chunk":
                    chunks.append(str(frame.get("content") or ""))
                elif kind == "chunk_reset":
                    chunks.clear()
                elif kind == "done":
                    reply = str(frame.get("full_response") or frame.get("content") or "".join(chunks))
                    return Turn(reply, {"session_id": session_id, "frames": frames,
                                        "protocol": "kylinbot.v1"}, "live:kylinbot-gateway")
                elif kind == "error":
                    raise RuntimeError("KylinBot message error: " + str(frame.get("message")))
                elif kind == "approval_request":
                    raise RuntimeError("KylinBot requested interactive approval; record the request and configure a safe test workspace")
                if time.monotonic() - started >= deadline:
                    raise TimeoutError("KylinBot turn timed out")
        finally:
            ws.close()


def make_agent(config, run_dir):
    kind = config["kind"]
    if kind == "fixture":
        return FixtureAgent(config, run_dir)
    if kind == "openclaw":
        return OpenClawAgent(config, run_dir)
    if kind == "kylinbot":
        return KylinBotAgent(config, run_dir)
    raise ValueError("unsupported agent kind: " + kind)
