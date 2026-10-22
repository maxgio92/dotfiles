import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "bin/standup-post"
SEND = "mcp__plugin_slack_slack__slack_send_message"
SCANNER = ("python3 $HOME/.claude/hooks/communication-rules/scanner.py "
           "claude-code PreToolUse")
# Records argv and cwd, writes FAKE_SENT to the send record as the post hook
# would, then prints the scripted output and exit status.
FAKE_CLAUDE = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_ARGV"], "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd()}) + "\\n")
if os.environ.get("FAKE_SENT"):
    with open("sent", "w") as f:
        f.write(os.environ["FAKE_SENT"] + "\\n")
sys.stdout.write(os.environ.get("FAKE_OUTPUT", ""))
sys.exit(int(os.environ.get("FAKE_STATUS", "0")))
"""
# Friday 2026-10-16 11:31 in Rome.
FRIDAY = "2026-10-16T09:31:00Z"
TODAY = "2026-10-16"
# 11:00 Rome on 2026-10-16, and the following midnight in Rome.
OLDEST = 1792141200
LATEST = 1792188000
SENT_TODAY = f"{TODAY} {OLDEST + 60}.000100"
CHANNEL = "C0TEST00001"
GATE_ARGS = (TODAY, str(OLDEST), str(LATEST), CHANNEL)
STANDUP_ENV = f"""STANDUP_CHANNEL={CHANNEL}
STANDUP_SUBTEAM=S0TEST00001
STANDUP_SELF=U0TEST00001
STANDUP_TEAM='Test Team'
"""


class StandupPost(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / "home"
        (self.home / ".claude/skills/standup-update/scripts").mkdir(parents=True)
        settings = {"hooks": {"PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "gate"}]},
            {"matcher": "", "hooks": [{"type": "command", "command": SCANNER}]},
        ]}}
        (self.home / ".claude/settings.json").write_text(json.dumps(settings))
        self.standup_env = self.home / ".config/standup-post.env"
        self.standup_env.parent.mkdir(parents=True)
        self.standup_env.write_text(STANDUP_ENV)
        self.rules = self.home / ".claude/hooks/communication-rules"
        self.rules.mkdir(parents=True)
        for name in ("scanner.py", "policy.json", "rules.md"):
            (self.rules / name).write_text("")
        shims = root / "shims"
        shims.mkdir()
        (shims / "claude").write_text(FAKE_CLAUDE)
        (shims / "claude").chmod(0o755)
        self.argv_file = root / "argv.jsonl"
        self.state = self.home / ".local/state/standup-post/last-posted"
        self.sent = self.home / ".local/state/standup-post/sent"
        self.env = {
            "HOME": str(self.home),
            "PATH": f"{shims}{os.pathsep}{os.environ['PATH']}",
            "FAKE_ARGV": str(self.argv_file),
            "STANDUP_POST_NOW": FRIDAY,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args, output="", status=0, now=FRIDAY, sent=""):
        env = {**self.env, "FAKE_OUTPUT": output, "FAKE_STATUS": str(status),
               "STANDUP_POST_NOW": now, "FAKE_SENT": sent}
        return subprocess.run([str(SCRIPT), *args], env=env, capture_output=True,
                              text=True, timeout=30)

    def calls(self):
        if not self.argv_file.exists():
            return []
        return [json.loads(line) for line in self.argv_file.read_text().splitlines()]

    def flag(self, argv, name):
        return argv[argv.index(name) + 1]

    def allowed_tools(self, argv):
        return argv[argv.index("--allowedTools") + 1:]

    def test_posted_writes_state(self):
        result = self.run_script(output="drafting\nPOSTED https://x.slack.com/archives/C/p1\n\n",
                                 sent=SENT_TODAY)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state.read_text().strip(), TODAY)
        self.assertIn("https://x.slack.com/archives/C/p1", result.stderr)

    def test_posted_without_send_fails(self):
        for name, sent in {"no record": "", "yesterday's record": "2026-10-15 1.2"}.items():
            with self.subTest(name):
                result = self.run_script(output="POSTED https://x.slack.com/archives/C/p1\n",
                                         sent=sent)
                self.assertEqual(result.returncode, 1)
                self.assertIn("no send landed", result.stderr)
                self.assertFalse(self.state.exists())

    def test_send_then_failure_writes_state(self):
        cases = {
            "error": ("ERROR: read-back failed\n", 0),
            "timeout": ("", 124),
            "claude failed": ("POSTED https://x.slack.com/archives/C/p1\n", 1),
        }
        for name, (output, status) in cases.items():
            with self.subTest(name):
                result = self.run_script(output=output, status=status, sent=SENT_TODAY)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(self.state.read_text().strip(), TODAY)
                calls = len(self.calls())
                again = self.run_script(output="POSTED https://x.slack.com/archives/C/p2\n")
                self.assertEqual(again.returncode, 0, again.stderr)
                self.assertIn("already posted today", again.stderr)
                self.assertEqual(len(self.calls()), calls)
                self.state.unlink()
                self.sent.unlink()

    def test_send_record_without_state_skips_claude(self):
        self.sent.parent.mkdir(parents=True)
        self.sent.write_text(SENT_TODAY + "\n")
        result = self.run_script(output="POSTED https://x.slack.com/archives/C/p1\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already posted today", result.stderr)
        self.assertEqual(self.state.read_text().strip(), TODAY)
        self.assertEqual(self.calls(), [])

    def test_second_run_skips_claude(self):
        self.run_script(output="POSTED https://x.slack.com/archives/C/p1\n", sent=SENT_TODAY)
        result = self.run_script(output="POSTED https://x.slack.com/archives/C/p2\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already posted today", result.stderr)
        self.assertEqual(len(self.calls()), 1)

    def test_skip_writes_no_state(self):
        result = self.run_script(output="SKIP: no standup today\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.state.exists())

    def test_failures_exit_one(self):
        cases = {
            "error": ("ERROR: thread not found\n", 0),
            "garbage": ("here is your draft\n", 0),
            "posted without link": ("POSTED\n", 0),
            "draft when posting": ("DRAFT\n", 0),
            "claude failed": ("POSTED https://x.slack.com/archives/C/p1\n", 1),
        }
        for name, (output, status) in cases.items():
            with self.subTest(name):
                result = self.run_script(output=output, status=status)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(self.state.exists())

    def test_dry_run(self):
        result = self.run_script("--dry-run", output="```\nMoved:\n```\nDRAFT\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Moved:", result.stdout)
        argv = self.calls()[0]["argv"]
        self.assertNotIn(SEND, self.allowed_tools(argv))
        self.assertIn("DRY RUN", self.flag(argv, "-p"))
        self.assertFalse(self.state.exists())

    def test_dry_run_rejects_post(self):
        result = self.run_script("--dry-run", output="POSTED https://x.slack.com/archives/C/p1\n")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.state.exists())

    def test_command(self):
        self.run_script(output="SKIP: already replied\n")
        call = self.calls()[0]
        argv = call["argv"]
        tools = self.allowed_tools(argv)
        self.assertIn(SEND, tools)
        for tool in tools:
            self.assertNotIn(tool.split("(")[0], {"Write", "Edit", "NotebookEdit"})
            self.assertNotEqual(tool, "Bash")
            self.assertNotEqual(tool, "Bash(*)")
        self.assertEqual(self.flag(argv, "--permission-mode"), "dontAsk")
        self.assertEqual(self.flag(argv, "--setting-sources"), "project,local")
        self.assertIn("--no-session-persistence", argv)
        self.assertIn("[standup-update]", self.flag(argv, "-p"))
        # Outside $HOME, so ~/.claude/settings.json never loads as project settings.
        self.assertEqual(call["cwd"], str(self.home / ".local/state/standup-post"))
        settings = json.loads(self.flag(argv, "--settings"))
        self.assertEqual(settings["enabledPlugins"], {"slack@claude-plugins-official": True})
        pre = settings["hooks"]["PreToolUse"]
        self.assertEqual([h["command"] for e in pre[:-1] for h in e["hooks"]], [SCANNER])
        self.assertEqual(pre[-1]["matcher"], SEND)
        gate_args = " ".join(GATE_ARGS)
        self.assertEqual(pre[-1]["hooks"][0]["command"],
                         f"{SCRIPT} --send-gate pre {gate_args}")
        post = settings["hooks"]["PostToolUse"]
        self.assertEqual(post, [{"matcher": SEND, "hooks": [
            {"type": "command", "command": f"{SCRIPT} --send-gate post {gate_args}"}]}])
        self.assertNotIn("Read", tools)
        # A prefix rule cannot restrict file arguments: jq reads any file and
        # date -f echoes each unparsable line back in its error.
        for tool in tools:
            self.assertFalse(tool.startswith(("Bash(jq", "Bash(date")), tool)
        self.assertIn("Read(~/.claude/projects/**)", tools)
        prompt = self.flag(argv, "-p")
        # 11:00 Rome on 2026-10-16 is 09:00 UTC.
        self.assertIn("oldest 1792141200", prompt)
        # The read is bounded to 11:00-12:00 Rome so the newest-first page holds the post.
        self.assertIn("latest 1792144800", prompt)
        self.assertIn("window starting 2026-10-15T00:00:00", prompt)
        self.assertIn('--updated ">=2026-09-16"', prompt)
        self.assertIn(f"channel_id {CHANNEL}", prompt)
        self.assertIn("S0TEST00001", prompt)
        self.assertIn("from user U0TEST00001", prompt)
        self.assertIn("The team is Test Team.", prompt)
        self.assertIn("No work GitHub organisation is configured, so no repository counts as work: report Linear only and leave out all GitHub activity.", prompt)

    def test_work_org_reaches_prompt(self):
        (self.home / ".config/work-context.env").write_text(
            "WORK_GITHUB_ORG=example-org\nSTANDUP_CHANNEL=C0OTHER\n")
        self.run_script(output="SKIP: x\n")
        prompt = self.flag(self.calls()[0]["argv"], "-p")
        self.assertIn("The work GitHub organisation is example-org.", prompt)
        self.assertNotIn("No work GitHub organisation", prompt)
        self.assertIn(f"channel_id {CHANNEL}", prompt)

    def test_monday_window_starts_friday(self):
        self.run_script(output="SKIP: x\n", now="2026-10-19T15:31:00Z")
        prompt = self.flag(self.calls()[0]["argv"], "-p")
        self.assertIn("window starting 2026-10-16T00:00:00", prompt)

    def test_missing_scanner_hook_fails_closed(self):
        (self.home / ".claude/settings.json").write_text("{}")
        result = self.run_script(output="POSTED https://x.slack.com/archives/C/p1\n")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.calls(), [])

    def test_missing_scanner_file_fails_closed(self):
        for name in ("scanner.py", "policy.json", "rules.md"):
            with self.subTest(name):
                (self.rules / name).unlink()
                result = self.run_script(output="POSTED https://x.slack.com/archives/C/p1\n")
                self.assertEqual(result.returncode, 1)
                self.assertIn(name, result.stderr)
                self.assertEqual(self.calls(), [])
                (self.rules / name).write_text("")

    def test_bad_standup_env_fails_closed(self):
        cases = {
            "missing file": (None, "missing"),
            "missing key": (STANDUP_ENV.replace("STANDUP_SELF=U0TEST00001\n", ""),
                            "does not set STANDUP_SELF"),
            "bad channel": (STANDUP_ENV.replace(CHANNEL, "c0test00001"),
                            "not a Slack channel ID"),
            "bad team": (STANDUP_ENV.replace("'Test Team'", "'Team $(x)'"),
                         "STANDUP_TEAM"),
        }
        for name, (content, message) in cases.items():
            with self.subTest(name):
                if content is None:
                    self.standup_env.unlink()
                else:
                    self.standup_env.write_text(content)
                result = self.run_script(output="POSTED https://x.slack.com/archives/C/p1\n")
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
                self.assertEqual(self.calls(), [])
                self.standup_env.write_text(STANDUP_ENV)

    def test_send_gate_ignores_standup_env(self):
        # A shell error in a sourced file exits with a status other than 2,
        # which would let the send through, so the gate must not read the file.
        good = {"channel_id": CHANNEL, "thread_ts": f"{OLDEST}.1"}
        cases = {
            "missing file": None,
            "unquoted space": STANDUP_ENV.replace("'Test Team'", "Test Team"),
            "unbound variable": STANDUP_ENV.replace(CHANNEL, "$NOPE"),
            "unreadable file": STANDUP_ENV,
        }
        for name, content in cases.items():
            with self.subTest(name):
                if content is None:
                    self.standup_env.unlink()
                else:
                    self.standup_env.write_text(content)
                if name == "unreadable file":
                    self.standup_env.chmod(0)
                self.assertEqual(self.gate("pre", **good).returncode, 0)
                wrong = self.gate("pre", **{**good, "channel_id": "C0OTHER"})
                self.assertEqual(wrong.returncode, 2)
                if self.standup_env.exists():
                    self.standup_env.chmod(0o600)
                self.standup_env.write_text(STANDUP_ENV)

    def gate(self, phase, *args, **tool_input):
        payload = {"tool_name": SEND, "tool_input": tool_input}
        return subprocess.run([str(SCRIPT), "--send-gate", phase, *(args or GATE_ARGS)],
                              env=self.env, input=json.dumps(payload),
                              capture_output=True, text=True, timeout=30)

    def test_send_gate(self):
        good = {"channel_id": CHANNEL, "thread_ts": "1792141200.000100", "message": "Moved:"}
        cases = {
            "wrong channel": {**good, "channel_id": "C0OTHER"},
            "missing thread_ts": {k: v for k, v in good.items() if k != "thread_ts"},
            "empty thread_ts": {**good, "thread_ts": ""},
            "non-numeric thread_ts": {**good, "thread_ts": "abc"},
            "yesterday's thread": {**good, "thread_ts": f"{OLDEST - 86400}.000100"},
            "before 11:00": {**good, "thread_ts": f"{OLDEST - 1}.000100"},
            "tomorrow's thread": {**good, "thread_ts": f"{LATEST}.000100"},
        }
        for name, tool_input in cases.items():
            with self.subTest(name):
                self.assertEqual(self.gate("pre", **tool_input).returncode, 2)
        with self.subTest("missing bounds"):
            self.assertEqual(self.gate("pre", TODAY, **good).returncode, 2)
        with self.subTest("missing channel"):
            self.assertEqual(self.gate("pre", *GATE_ARGS[:3], **good).returncode, 2)
        with self.subTest("bad channel"):
            self.assertEqual(self.gate("pre", *GATE_ARGS[:3], "c0test", **good).returncode, 2)
        bad_json = subprocess.run([str(SCRIPT), "--send-gate", "pre", *GATE_ARGS],
                                  env=self.env, input="not json", capture_output=True,
                                  text=True, timeout=30)
        self.assertEqual(bad_json.returncode, 2)
        self.assertEqual(self.gate("pre", **good).returncode, 0, "first send")
        self.assertEqual(self.gate("post", **good).returncode, 0)
        second = self.gate("pre", **good)
        self.assertEqual(second.returncode, 2)
        self.assertIn("already posted", second.stderr)
        self.assertEqual(self.sent.read_text(), f"{TODAY} 1792141200.000100\n")

    def test_send_gate_denies_bare_pr_numbers(self):
        good = {"channel_id": CHANNEL, "thread_ts": f"{OLDEST}.1"}
        url = "https://github.com/acme/{}/pull/{}"
        cases = [
            ("385710", "root-caused the stereo 385710 halt",
             f"root-caused the {url.format('stereo', 385710)} halt"),
            ("pull 385710", "root-caused the stereo pull 385710 halt",
             f"root-caused the stereo {url.format('stereo', 385710)} halt"),
            ("mono#70016", "rebased mono#70016 today",
             f"rebased {url.format('mono', 70016)} today"),
            ("#39", "• merged #39", f"• merged {url.format('dotfiles', 39)}"),
            ("PR 70016", "opened PR 70016, waiting on review",
             f"opened {url.format('mono', 70016)} waiting on review"),
            ("PR 70016", "PR 70016: ready", f"{url.format('mono', 70016)}: ready"),
            ("#39", "merged #39: done", f"merged {url.format('dotfiles', 39)}: done"),
        ]
        for ref, bare, cited in cases:
            with self.subTest(ref):
                denied = self.gate("pre", **good, message=bare)
                self.assertEqual(denied.returncode, 2)
                self.assertIn(ref, denied.stderr)
                self.assertIn("https://github.com/<owner>/<repo>/pull/<n>", denied.stderr)
                self.assertEqual(self.gate("pre", **good, message=cited).returncode, 0)
        for text in ("filed FUL-917", "blocked on ECO-5500", "filed ECO-12345", "triaged 48 feedback items",
                     "reviewed 120 files", "over 1500 tests", "issue 4567", "70% merge-rate", "standup at 17:31", "planned for October 2026"):
            with self.subTest(text):
                self.assertEqual(self.gate("pre", **good, message=text).returncode, 0)

    def test_send_record_is_per_day(self):
        good = {"channel_id": CHANNEL, "thread_ts": f"{OLDEST + 60}.1"}
        self.gate("post", "2026-10-15", **good)
        self.assertEqual(self.gate("pre", **good).returncode, 0)
        self.run_script(output="SKIP: x\n")
        self.gate("post", **good)
        self.assertEqual(self.gate("pre", **good).returncode, 2)


if __name__ == "__main__":
    unittest.main()
