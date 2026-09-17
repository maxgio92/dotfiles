import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin/agent-work"
loader = importlib.machinery.SourceFileLoader("agent_work", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class Workflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-work-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.command("git", "init", "-q", str(self.repo))
        self.command("git", "-C", str(self.repo), "-c", "user.name=Test",
                     "-c", "user.email=test@example.invalid", "commit", "-qm", "initial", "--allow-empty")
        self.server = "agent-work-test-" + uuid.uuid4().hex
        self.addCleanup(lambda: subprocess.run(["tmux", "-L", self.server, "kill-server"],
                                               capture_output=True))
        self.command("tmux", "-L", self.server, "-f", "/dev/null", "new-session", "-d",
                     "-s", "test", "-x", "200", "-y", "80", "-c", str(self.repo), "sleep 120")
        identity = self.command("tmux", "-L", self.server, "display-message", "-p",
                                "#{socket_path},#{pid},0").strip()
        self.env = {**os.environ, "TMUX": identity, "TMUX_PANE": "%0",
                    "PYTHONDONTWRITEBYTECODE": "1"}
        self.state = self.root / "registry/state.json"
        self.invoke("init", "--repo", str(self.repo), "--coordinator", "%0")
        self.prompt = self.root / "prompt.md"
        self.prompt.write_text("Report task state. Do not change the repository.")

    def command(self, *args, **kwargs):
        return subprocess.run(args, check=True, text=True, capture_output=True,
                              timeout=15, **kwargs).stdout

    def invoke(self, *args, success=True):
        result = subprocess.run([str(SCRIPT), "--state", str(self.state), *args],
                                env=self.env, text=True, capture_output=True, timeout=15)
        if not success:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            return result.stderr
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def spawn(self, key="first"):
        command = [sys.executable, "-u", "-c",
                   "import sys; print('READY'); "
                   "exec(\"for line in sys.stdin:\\n print('ACK ' + line.strip(), flush=True)\")"]
        task = self.invoke("spawn", key, "--agent", "fake", "--command-json", json.dumps(command),
                           "--base", "HEAD", "--prompt-file", str(self.prompt))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            check = self.invoke("check")["tasks"][key]
            if "READY" in check.get("output", ""):
                return task
            time.sleep(0.02)
        self.fail("worker did not start")

    def test_spawn_isolates_worktrees_in_same_window(self):
        one, two = self.spawn(), self.spawn("second")
        self.assertNotEqual(one["pane"], two["pane"])
        self.assertNotEqual(one["worktree"], two["worktree"])
        self.assertNotEqual(one["branch"], two["branch"])
        self.assertEqual(one["window"], two["window"])
        self.assertNotEqual(one["pane"], "%0")
        self.assertTrue(Path(one["worktree"]).is_dir())
        self.assertIn("already registered", self.invoke("spawn", "first", "--agent", "fake",
            "--base", "HEAD", "--prompt-file", str(self.prompt), success=False))

    def test_missing_worker_is_not_complete(self):
        task = self.spawn()
        self.command("tmux", "kill-pane", "-t", task["pane"], env=self.env)
        result = self.invoke("check")["tasks"]["first"]
        self.assertEqual(result["health"], "unavailable")
        self.assertNotEqual(result["stage"], "complete")

    def test_guarded_steering_and_identity(self):
        task = self.spawn()
        check = self.invoke("check")["tasks"]["first"]
        message = self.root / "message.txt"
        message.write_text("Use the existing API; $(do-not-execute)")
        base_args = ("steer", "first", "--message-file", str(message), "--screen-sha256")
        self.assertIn("pane changed", self.invoke(*base_args, "wrong", success=False))
        result = self.invoke(*base_args, check["screen_sha256"])
        self.assertTrue(result["sent"])
        self.assertFalse(result["acknowledged"])
        self.command("tmux", "set-option", "-p", "-t", task["pane"],
                     "@agent_work_token", "replaced", env=self.env)
        self.assertIn("token changed", self.invoke(*base_args, check["screen_sha256"], success=False))

    def test_adopt_requires_separate_worktree(self):
        pane = self.command("tmux", "split-window", "-d", "-P", "-F", "#{pane_id}",
                            "-t", "%0", "-c", str(self.repo), "sleep 120", env=self.env).strip()
        self.assertIn("already used", self.invoke("adopt", "shared", "--pane", pane,
                                                 "--agent", "fake", success=False))
        worktree = self.root / "adopted"
        self.command("git", "-C", str(self.repo), "worktree", "add", "-b", "adopted", str(worktree))
        pane = self.command("tmux", "split-window", "-d", "-P", "-F", "#{pane_id}",
                            "-t", "%0", "-c", str(worktree), "sleep 120", env=self.env).strip()
        task = self.invoke("adopt", "adopted", "--pane", pane, "--agent", "fake")
        self.assertEqual(task["worktree"], str(worktree))
        record = self.invoke("record", "adopted", "--stage", "review", "--ticket", "TASK-1",
                             "--pending", "Review draft", "--evidence", "Tests passed")
        self.assertEqual(record["ticket"], "TASK-1")
        self.assertIn("checked_at", record)

    def test_launch_failure_keeps_record(self):
        self.command("git", "-C", str(self.repo), "branch", "work/registry/failed")
        self.invoke("spawn", "failed", "--agent", "fake", "--command-json", '["sleep"]',
                    "--base", "HEAD", "--prompt-file", str(self.prompt), success=False)
        task = self.invoke("check")["tasks"]["failed"]
        self.assertEqual(task["stage"], "launch-failed")
        self.assertTrue(Path(task["prompt"]).exists())

    def test_task_id_cannot_escape_registry(self):
        self.assertIn("task ID", self.invoke("spawn", "../outside", "--agent", "fake",
            "--base", "HEAD", "--prompt-file", str(self.prompt), success=False))

    def test_control_bytes_are_not_sent(self):
        self.spawn()
        check = self.invoke("check")["tasks"]["first"]
        message = self.root / "message.txt"
        message.write_text("\x03cancel")
        error = self.invoke("steer", "first", "--message-file", str(message),
                            "--screen-sha256", check["screen_sha256"], success=False)
        self.assertIn("without escapes", error)

    def test_adopted_shell_cannot_receive_agent_prompt(self):
        worktree = self.root / "shell-tree"
        self.command("git", "-C", str(self.repo), "worktree", "add", "-b", "shell-tree", str(worktree))
        pane = self.command("tmux", "split-window", "-d", "-P", "-F", "#{pane_id}",
                            "-t", "%0", "-c", str(worktree), "sh", env=self.env).strip()
        self.invoke("adopt", "shell", "--pane", pane, "--agent", "fake")
        check = self.invoke("check")["tasks"]["shell"]
        message = self.root / "message.txt"
        message.write_text("echo should-not-run")
        error = self.invoke("steer", "shell", "--message-file", str(message),
                            "--screen-sha256", check["screen_sha256"], success=False)
        self.assertIn("pane is a shell", error)


class Install(unittest.TestCase):
    def test_portable_links_and_repeat_install(self):
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, "HOME": home}
            for _ in range(2):
                subprocess.run(["bash", str(ROOT / "assistants/orchestration-install.sh")],
                               env=env, check=True, capture_output=True)
            for folder in (".claude/commands", ".codex/prompts", ".pi/agent/prompts"):
                for name in ("orchestrate", "spawn-work", "check-work", "steer-work"):
                    self.assertTrue((Path(home) / folder / (name + ".md")).is_file())
            for folder in (".claude/skills", ".agents/skills", ".pi/agent/skills"):
                self.assertTrue((Path(home) / folder / "orchestrating-work/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
