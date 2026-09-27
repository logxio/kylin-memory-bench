"""Agent turns. Each adapter returns its raw response and an attributable reply."""

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

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
        # Leave time for the CLI to report its own timeout before the outer
        # process deadline. The outer limit still covers startup and cleanup.
        cli_timeout = max(1, int(deadline) - 5)
        args = [command, "agent", "--agent", self.config.get("agent_id", "main"),
                "--session-key", key, "--message-file", str(message_file), "--json",
                "--timeout", str(cli_timeout)]
        completed = subprocess.run(args, text=True, capture_output=True, timeout=deadline, check=False)
        raw = {"argv": args,
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

    def _pair_local_gateway(self, url, deadline):
        parsed = urlparse(url)
        if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise RuntimeError("KylinBot remote Gateway needs a token environment variable")
        origin = ("https" if parsed.scheme == "wss" else "http") + "://" + parsed.netloc
        timeout = max(1, min(float(deadline), 15.0))

        def post(path, headers=None):
            req = Request(origin + path, data=b"", headers=headers or {}, method="POST")
            with urlopen(req, timeout=timeout) as response:
                return json.load(response)

        try:
            code = str(post("/admin/paircode/new")["pairing_code"])
            token = str(post("/pair", {"X-Pairing-Code": code})["token"])
        except (OSError, KeyError, ValueError) as exc:
            raise RuntimeError("KylinBot Gateway local pairing failed; check Gateway status or set the token environment variable") from exc
        if not token.startswith("zc"):
            raise RuntimeError("KylinBot Gateway returned an unexpected token format")
        return token

    def turn(self, case, step, prompt, workspace, deadline):
        try:
            import websocket
        except ImportError as exc:
            raise RuntimeError("KylinBot adapter needs websocket-client; install requirements.txt") from exc
        url = self.config.get("url", "ws://127.0.0.1:42617/ws/chat")
        parsed = urlparse(url)
        if parsed.scheme not in ("ws", "wss") or not parsed.netloc:
            raise ValueError("KylinBot url must be ws:// or wss:// with a host")
        started = time.monotonic()

        def remaining(phase):
            left = deadline - (time.monotonic() - started)
            if left <= 0:
                raise TimeoutError("KylinBot " + phase + " timed out")
            return left

        token = os.environ.get(self.config.get("token_env", "KYLINBOT_WS_TOKEN")) or getattr(self, "_token", None)
        if not token:
            token = self._pair_local_gateway(url, remaining("pairing"))
            self._token = token
        session_id = ":".join((self.config.get("session_prefix", "kmb"), case["id"], step["session"]))
        frames = []
        ws = websocket.create_connection(url, timeout=remaining("connecting"),
                                         header=["Authorization: Bearer " + token.removeprefix("Bearer ")],
                                         subprotocols=["kylinbot.v1"])
        try:
            connect = {"type": "connect", "session_id": session_id, "capabilities": ["chat"],
                       "mode": self.config.get("mode", "agentic"), "token_saving": False}
            ws.settimeout(remaining("connecting"))
            ws.send(json.dumps(connect, ensure_ascii=False))
            while True:
                ws.settimeout(remaining("connecting"))
                frame = json.loads(ws.recv())
                remaining("connecting")
                frames.append(frame)
                if frame.get("type") == "connected":
                    break
                if frame.get("type") == "error":
                    raise RuntimeError("KylinBot connect error: " + str(frame.get("message")))
            ws.settimeout(remaining("sending"))
            ws.send(json.dumps({"type": "message", "content": prompt,
                                "mode": self.config.get("mode", "agentic"), "token_saving": False},
                               ensure_ascii=False))
            chunks = []
            while True:
                ws.settimeout(remaining("turn"))
                frame = json.loads(ws.recv())
                remaining("turn")
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
