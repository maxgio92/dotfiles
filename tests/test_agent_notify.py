import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "bin/agent-notify"
loader = importlib.machinery.SourceFileLoader("agent_notify", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class Events(unittest.TestCase):
    def test_hook_context(self):
        # Fields: https://code.claude.com/docs/en/hooks#notification
        payload = {"notification_type": "permission_prompt", "cwd": "/srv/project"}
        with patch.dict(os.environ, {"TMUX_PANE": "%42"}), patch.object(
            module.subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, "session/window/%42\n")) as run:
            event = module.make_event(payload)
        self.assertEqual(event["project"], "project")
        self.assertEqual(event["context"], "session/window/%42")
        self.assertIn("%42", run.call_args.args[0])

    def test_ignore_other_events(self):
        for kind in ("auth_success", None, [], {}):
            self.assertIsNone(module.make_event({"notification_type": kind}))

    def test_reject_payloads(self):
        for raw in (b"[]\n", b"{\n", b"x" * (module.LIMIT + 1)):
            with self.subTest(raw=raw[:10]), self.assertRaises(ValueError):
                module.read_json(io.BytesIO(raw))

    def test_reject_invalid_fields(self):
        for fields in ({"version": True}, {"type": []}, {"host": []}):
            event = {"version": 1, "type": "idle_prompt", **fields}
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                module.notify(event)

    def test_text_stays_an_argument(self):
        with patch.object(module.subprocess, "run") as run:
            module.notify({"version": 1, "type": "idle_prompt",
                           "host": "<b>host</b>", "project": "$(touch /tmp/nope)"})
        args = run.call_args.args[0]
        self.assertIn("--", args)
        self.assertIn("&lt;b&gt;host&lt;/b&gt;", args[-1])
        self.assertIn("$(touch /tmp/nope)", args[-1])
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_offline_sender_exits_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [str(SCRIPT), "send", "--socket", directory + "/missing"],
                input='{"notification_type":"idle_prompt","cwd":"/srv/app"}',
                text=True, capture_output=True, timeout=5,
                env={**os.environ, "TMUX_PANE": ""},
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn("agent-notify:", result.stderr)

    def test_socket_delivery_after_bad_event(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint = root / "notify.sock"
            output = root / "received.json"
            notifier = root / "notify-send"
            notifier.write_text(
                "#!/usr/bin/env python3\nimport json, os, sys\n"
                "from pathlib import Path\n"
                "Path(os.environ['NOTIFY_TEST_OUTPUT']).write_text(json.dumps(sys.argv[1:]))\n"
            )
            notifier.chmod(0o700)
            env = {**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"],
                   "NOTIFY_TEST_OUTPUT": str(output), "TMUX_PANE": ""}
            server = subprocess.Popen(
                [str(SCRIPT), "serve", "--socket", str(endpoint)],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                deadline = time.monotonic() + 5
                while not endpoint.exists() and server.poll() is None:
                    if time.monotonic() > deadline:
                        self.fail("receiver did not start")
                    time.sleep(0.01)
                self.assertIsNone(server.poll())
                self.assertEqual(endpoint.stat().st_mode & 0o777, 0o600)
                with socket.socket(socket.AF_UNIX) as client:
                    client.settimeout(3)
                    client.connect(str(endpoint))
                    client.sendall(b"[]\n")
                    self.assertEqual(client.recv(3), b"")
                result = subprocess.run(
                    [str(SCRIPT), "send", "--socket", str(endpoint)],
                    input='{"notification_type":"permission_prompt","cwd":"/srv/example"}',
                    text=True, capture_output=True, timeout=5, env=env,
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stderr, "")
                args = json.loads(output.read_text())
                self.assertEqual(args[-2], "Claude needs approval")
                self.assertIn("example", args[-1])
            finally:
                server.send_signal(signal.SIGINT)
                server.communicate(timeout=5)
            self.assertFalse(endpoint.exists())

    def test_refuse_existing_path(self):
        with tempfile.TemporaryDirectory() as directory:
            endpoint = Path(directory) / "notify.sock"
            endpoint.write_text("keep")
            with self.assertRaises(OSError):
                module.serve(endpoint)
            self.assertEqual(endpoint.read_text(), "keep")

    def test_refuse_public_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory).chmod(0o755)
            with self.assertRaises(ValueError):
                module.serve(Path(directory) / "notify.sock")


if __name__ == "__main__":
    unittest.main()
