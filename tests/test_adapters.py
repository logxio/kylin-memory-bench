import json
import io
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from kylin_memory_bench.adapters import KylinBotAgent, OpenClawAgent


class _WebSocket:
    def __init__(self):
        self.sent = []
        self.frames = iter([
            json.dumps({"type": "connected", "session_id": "seen"}),
            json.dumps({"type": "chunk", "content": '{"answer":'}),
            json.dumps({"type": "chunk", "content": '"Cedar"}'}),
            json.dumps({"type": "done", "full_response": '{"answer":"Cedar"}'}),
        ])

    def send(self, data):
        self.sent.append(json.loads(data))

    def settimeout(self, timeout):
        self.timeout = timeout

    def recv(self):
        return next(self.frames)

    def close(self):
        pass


class AdapterContractTest(unittest.TestCase):
    def test_kylinbot_local_pairing_uses_documented_endpoints(self):
        responses = [io.BytesIO(b'{"pairing_code":"123456"}'), io.BytesIO(b'{"token":"zc_fixture"}')]
        with patch("kylin_memory_bench.adapters.urlopen", side_effect=responses) as urlopen:
            token = KylinBotAgent({"kind": "kylinbot"}, ".")._pair_local_gateway(
                "ws://127.0.0.1:42617/ws/chat", 5)
        self.assertEqual(token, "zc_fixture")
        self.assertTrue(urlopen.call_args_list[0].args[0].full_url.endswith("/admin/paircode/new"))
        self.assertTrue(urlopen.call_args_list[1].args[0].full_url.endswith("/pair"))

    def test_kylinbot_uses_gateway_session_and_final_frame(self):
        ws = _WebSocket()
        fake_module = types.SimpleNamespace(create_connection=lambda *a, **k: ws)
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(sys.modules, {"websocket": fake_module}), \
             patch.dict(os.environ, {"KYLINBOT_WS_TOKEN": "zc_test_fixture"}):
            adapter = KylinBotAgent({"kind": "kylinbot", "session_prefix": "trial"}, folder)
            turn = adapter.turn({"id": "retention-01"}, {"id": "probe", "session": "b"},
                                "Recall the code", Path(folder), 3)
        self.assertEqual(turn.reply, '{"answer":"Cedar"}')
        self.assertEqual(ws.sent[0]["session_id"], "trial:retention-01:b")
        self.assertEqual(ws.sent[1]["type"], "message")
        self.assertEqual(turn.source, "live:kylinbot-gateway")
        self.assertGreater(ws.timeout, 0)

    def test_openclaw_uses_explicit_session_key_and_json(self):
        output = types.SimpleNamespace(returncode=0, stdout=json.dumps({"result": {
            "payloads": [{"text": '{"answer":"Cedar"}'}]}}), stderr="")
        with tempfile.TemporaryDirectory() as folder, \
             patch("kylin_memory_bench.adapters.shutil.which", return_value="/usr/bin/openclaw"), \
             patch("kylin_memory_bench.adapters.subprocess.run", return_value=output) as run:
            adapter = OpenClawAgent({"kind": "openclaw", "agent_id": "kmb-test",
                                     "session_prefix": "trial"}, folder)
            turn = adapter.turn({"id": "retention-01"}, {"id": "probe", "session": "b"},
                                "Recall the code", Path(folder), 3)
            args = run.call_args.args[0]
        self.assertEqual(turn.reply, '{"answer":"Cedar"}')
        self.assertEqual(args[args.index("--session-key") + 1], "kmb:trial:retention-01:b")
        self.assertIn("--json", args)
        self.assertEqual(args[args.index("--timeout") + 1], "1")
        self.assertEqual(run.call_args.kwargs["timeout"], 3)

    def test_openclaw_cli_timeout_leaves_reporting_margin(self):
        output = types.SimpleNamespace(returncode=0, stdout='{"result":{"final":"{}"}}', stderr="")
        with tempfile.TemporaryDirectory() as folder, \
             patch("kylin_memory_bench.adapters.shutil.which", return_value="/usr/bin/openclaw"), \
             patch("kylin_memory_bench.adapters.subprocess.run", return_value=output) as run:
            OpenClawAgent({"kind": "openclaw"}, folder).turn(
                {"id": "retention-01"}, {"id": "probe", "session": "b"},
                "Recall the code", Path(folder), 130)
        args = run.call_args.args[0]
        self.assertEqual(args[args.index("--timeout") + 1], "125")
        self.assertEqual(run.call_args.kwargs["timeout"], 130)

    def test_kylinbot_rejects_done_after_absolute_deadline(self):
        class SlowWebSocket(_WebSocket):
            def recv(self):
                time.sleep(0.01)
                return super().recv()

        ws = SlowWebSocket()
        fake_module = types.SimpleNamespace(create_connection=lambda *a, **k: ws)
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(sys.modules, {"websocket": fake_module}), \
             patch.dict(os.environ, {"KYLINBOT_WS_TOKEN": "zc_test_fixture"}):
            adapter = KylinBotAgent({"kind": "kylinbot"}, folder)
            with self.assertRaisesRegex(TimeoutError, "KylinBot connecting timed out"):
                adapter.turn({"id": "retention-01"}, {"id": "probe", "session": "b"},
                             "Recall the code", Path(folder), 0.005)


if __name__ == "__main__":
    unittest.main()
