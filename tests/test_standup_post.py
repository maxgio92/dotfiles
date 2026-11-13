import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "bin/standup-post"
# The em dash the fake scanner blocks, built from its code point so no
# source line carries one.
EM_DASH = chr(0x2014)
# Records argv and cwd, then prints the scripted output and exit status. A
# redraft prompt prints FAKE_REDRAFT_OUTPUT instead when it is set.
FAKE_CLAUDE = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_ARGV"], "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd()}) + chr(10))
out = os.environ.get("FAKE_OUTPUT", "")
if "rejected for these reasons" in sys.argv[2] and "FAKE_REDRAFT_OUTPUT" in os.environ:
    out = os.environ["FAKE_REDRAFT_OUTPUT"]
sys.stdout.write(out)
sys.exit(int(os.environ.get("FAKE_STATUS", "0")))
"""
# Stands in for the agent-slack wrapper: records argv, then prints the
# scripted channel history, thread or send result with its exit status.
FAKE_SLACK = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_SLACK_ARGV"], "a") as f:
    f.write(json.dumps(args) + chr(10))
if args[:2] == ["message", "list"]:
    key = "FAKE_THREAD" if "--thread-ts" in args else "FAKE_HISTORY"
elif args[:2] == ["message", "send"]:
    key = "FAKE_SEND"
else:
    sys.exit(99)
sys.stdout.write(os.environ.get(key, ""))
sys.exit(int(os.environ.get(key + "_STATUS", "0")))
"""
# Records argv and stdin of each agent-notify call.
FAKE_NOTIFY = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_NOTIFY"], "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "stdin": sys.stdin.read()}) + chr(10))
"""
# Stands in for the Communication Rules scanner: scan-text blocks an em dash.
FAKE_SCANNER = """import sys
if sys.argv[-1] == "block-message":
    print("Blocked. No em dashes.")
elif chr(0x2014) in sys.stdin.read():
    print("block")
    sys.exit(1)
else:
    print("pass")
"""
# Friday 2026-10-16 11:31 in Rome.
FRIDAY = "2026-10-16T09:31:00Z"
TODAY = "2026-10-16"
# 11:00 Rome on 2026-10-16, 12:00 Rome, and the following midnight in Rome.
OLDEST = 1792141200
WINDOW_END = 1792144800
LATEST = 1792188000
THREAD_TS = f"{OLDEST + 60}.000100"
SENT_TODAY = f"{TODAY} {THREAD_TS}"
DRAFT_TEXT = "Moved:\n• merged https://github.com/acme/mono/pull/70016\n\nToday:\n• review"
DRAFT_OUTPUT = f"drafting\n```\n{DRAFT_TEXT}\n```\nSources: s1\nIMAGE_REQUESTS none\nDRAFT\n"
IMAGE_TEXT = DRAFT_TEXT.replace(
    "Today:\n", "Today:\n• image requests: DELI-4882 bump go, DELI-4787 add jq\n")
IMAGE_OUTPUT = DRAFT_OUTPUT.replace(DRAFT_TEXT, IMAGE_TEXT).replace(
    "IMAGE_REQUESTS none", "IMAGE_REQUESTS DELI-4882 DELI-4787")
PERMALINK = "https://x.slack.com/archives/C/p1"
CHANNEL = "C0TEST00001"
SUBTEAM = "S0TEST00001"
SELF = "U0TEST00001"
STANDUP_ENV = f"""STANDUP_CHANNEL={CHANNEL}
STANDUP_SUBTEAM={SUBTEAM}
STANDUP_SELF={SELF}
STANDUP_TEAM='Test Team'
"""


def root(ts=THREAD_TS, subteam=SUBTEAM, author=None):
    # The shape agent-slack message list prints: the raw mention stays
    # <!subteam^S...>, and the author carries user_id or bot_id.
    return {"ts": ts, "thread_ts": ts, "author": author or {"bot_id": "B0TEST00001"},
            "content": f"Good Morning <!subteam^{subteam}> Please post your daily update in thread."}


def history(*messages):
    return json.dumps({"channel_id": CHANNEL, "messages": list(messages or [root()])})


def thread(*replies, ts=THREAD_TS):
    return json.dumps({"messages": [root(ts)] + list(replies)})


SELF_REPLY = {"ts": f"{OLDEST + 600}.000100", "thread_ts": THREAD_TS,
              "author": {"user_id": SELF}, "content": "Moved: x"}
SENT = json.dumps({"ok": True, "channel_id": CHANNEL, "ts": f"{OLDEST + 700}.000200",
                   "thread_ts": THREAD_TS, "permalink": PERMALINK})


class StandupPost(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root_dir = Path(self.tmp.name)
        self.home = root_dir / "home"
        (self.home / ".claude/skills/standup-update/scripts").mkdir(parents=True)
        self.standup_env = self.home / ".config/standup-post.env"
        self.standup_env.parent.mkdir(parents=True)
        self.standup_env.write_text(STANDUP_ENV)
        self.rules = self.home / ".claude/hooks/communication-rules"
        self.rules.mkdir(parents=True)
        for name in ("policy.json", "rules.md"):
            (self.rules / name).write_text("")
        (self.rules / "scanner.py").write_text(FAKE_SCANNER)
        shims = root_dir / "shims"
        shims.mkdir()
        for name, body in (("claude", FAKE_CLAUDE), ("agent-slack", FAKE_SLACK),
                           ("agent-notify", FAKE_NOTIFY)):
            (shims / name).write_text(body)
            (shims / name).chmod(0o755)
        self.argv_file = root_dir / "argv.jsonl"
        self.slack_file = root_dir / "slack.jsonl"
        self.notify_file = root_dir / "notify.jsonl"
        state_dir = self.home / ".local/state/standup-post"
        self.state = state_dir / "last-posted"
        self.posted_at = state_dir / "posted-at"
        self.sent = state_dir / "sent"
        self.draft = state_dir / "draft"
        self.pending = state_dir / "pending"
        self.env = {
            "HOME": str(self.home),
            "PATH": f"{shims}{os.pathsep}{os.environ['PATH']}",
            "FAKE_ARGV": str(self.argv_file),
            "FAKE_SLACK_ARGV": str(self.slack_file),
            "FAKE_NOTIFY": str(self.notify_file),
            "STANDUP_POST_NOW": FRIDAY,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args, output="", status=0, now=FRIDAY, redraft=None,
                   hist=None, thr=None, send=SENT, hist_status=0, thr_status=0,
                   send_status=0):
        env = {**self.env, "FAKE_OUTPUT": output, "FAKE_STATUS": str(status),
               "STANDUP_POST_NOW": now,
               "FAKE_HISTORY": history() if hist is None else hist,
               "FAKE_HISTORY_STATUS": str(hist_status),
               "FAKE_THREAD": thread() if thr is None else thr,
               "FAKE_THREAD_STATUS": str(thr_status),
               "FAKE_SEND": send, "FAKE_SEND_STATUS": str(send_status)}
        if redraft is not None:
            env["FAKE_REDRAFT_OUTPUT"] = redraft
        return subprocess.run([str(SCRIPT), *args], env=env, capture_output=True,
                              text=True, timeout=30)

    def calls(self, path=None):
        path = path or self.argv_file
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines()]

    def slack_calls(self):
        return self.calls(self.slack_file)

    def sends(self):
        return [c for c in self.slack_calls() if c[:2] == ["message", "send"]]

    def save_pending(self, text=DRAFT_TEXT, thread_ts=THREAD_TS, day=TODAY):
        self.draft.parent.mkdir(parents=True, exist_ok=True)
        self.draft.write_text(text + "\n")
        self.pending.write_text(f"{day} {thread_ts}\n")

    def reset_state(self):
        for path in (self.state, self.posted_at, self.sent, self.draft, self.pending,
                     self.argv_file, self.slack_file):
            path.unlink(missing_ok=True)

    def flag(self, argv, name):
        return argv[argv.index(name) + 1]

    def allowed_tools(self, argv):
        return argv[argv.index("--allowedTools") + 1:]

    def approve(self, **kwargs):
        self.save_pending()
        return self.run_script("--approve", **kwargs)

    def test_draft_saves_and_notifies(self):
        result = self.run_script(output=DRAFT_OUTPUT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.draft.read_text(), DRAFT_TEXT + "\n")
        self.assertEqual(self.draft.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.pending.read_text(), f"{TODAY} {THREAD_TS}\n")
        self.assertIn("standup-post --show, then standup-post --approve", result.stderr)
        self.assertEqual(self.slack_calls(), [
            ["message", "list", CHANNEL, "--oldest", str(OLDEST), "--latest", str(WINDOW_END),
             "--limit", "200"],
            ["message", "list", CHANNEL, "--thread-ts", THREAD_TS],
        ])
        notes = self.calls(self.notify_file)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["argv"], ["send"])
        self.assertEqual(json.loads(notes[0]["stdin"])["notification_type"], "permission_prompt")
        self.assertFalse(self.state.exists())

    def test_second_draft_skips_claude(self):
        self.run_script(output=DRAFT_OUTPUT)
        result = self.run_script(output=DRAFT_OUTPUT.replace("review", "other"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("waiting", result.stderr)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.draft.read_text(), DRAFT_TEXT + "\n")

    def test_stale_pending_redrafts(self):
        self.save_pending(text="old", day="2026-10-15")
        result = self.run_script(output=DRAFT_OUTPUT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.draft.read_text(), DRAFT_TEXT + "\n")

    def test_thread_selection(self):
        later = f"{OLDEST + 120}.000100"
        cases = {
            "earliest of two": (history(root(later), root()), THREAD_TS),
            "skips a person's message": (history(root(author={"user_id": "U0OTHER"}), root(later)), later),
            "skips a longer subteam ID": (history(root(subteam=SUBTEAM + "1"), root(later)), later),
            "skips a thread reply": (history({**root(), "thread_ts": f"{OLDEST}.1"}, root(later)), later),
        }
        for name, (hist, want) in cases.items():
            with self.subTest(name):
                self.reset_state()
                result = self.run_script(output=DRAFT_OUTPUT, hist=hist, thr=thread(ts=want))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.pending.read_text(), f"{TODAY} {want}\n")

    def test_no_standup_thread_skips_claude(self):
        for name, hist in {"no bot post": history(root(author={"user_id": "U0OTHER"})),
                           # agent-slack prunes the empty messages array.
                           "no messages": json.dumps({"channel_id": CHANNEL}),
                           "empty payload": "{}"}.items():
            with self.subTest(name):
                result = self.run_script(output=DRAFT_OUTPUT, hist=hist)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("no standup today", result.stderr)
                self.assertEqual(self.calls(), [])
                self.assertFalse(self.pending.exists())

    def test_bad_slack_reads_fail_before_claude(self):
        cases = {
            "history read fails": {"hist_status": 1},
            "history not json": {"hist": "not json"},
            "history without messages": {"hist": json.dumps({"error": "x"})},
            "thread outside window": {"hist": history(root(f"{OLDEST - 1}.000100"))},
            "thread read fails": {"thr_status": 1},
            "thread without its root": {"thr": thread(ts=f"{OLDEST + 5}.1")},
            "thread not json": {"thr": "not json"},
        }
        for name, kwargs in cases.items():
            with self.subTest(name):
                self.reset_state()
                result = self.run_script(output=DRAFT_OUTPUT, **kwargs)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(self.calls(), [])
                self.assertFalse(self.pending.exists())

    def test_draft_skips_when_user_already_replied(self):
        result = self.run_script(output=DRAFT_OUTPUT, thr=thread(SELF_REPLY))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already replied", result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.pending.exists())

    def test_bad_draft_output_fails(self):
        cases = {
            "no fence": f"{DRAFT_TEXT}\nDRAFT\n",
            "unclosed fence": f"```\n{DRAFT_TEXT}\nDRAFT\n",
            "empty fence": "```\n\n```\nIMAGE_REQUESTS none\nDRAFT\n",
        }
        for name, output in cases.items():
            with self.subTest(name):
                result = self.run_script(output=output)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(self.pending.exists())
                self.assertEqual(self.calls(self.notify_file), [])

    def test_denied_draft_redrafts_once(self):
        cases = {
            "bare pull request": (DRAFT_TEXT.replace("https://github.com/acme/mono/pull/70016", "mono#70016"),
                                  "mono#70016"),
            "em dash": (DRAFT_TEXT.replace("review", f"review {EM_DASH} docs"), "No em dashes."),
        }
        for name, (text, reason) in cases.items():
            with self.subTest(name):
                self.argv_file.unlink(missing_ok=True)
                result = self.run_script(output=DRAFT_OUTPUT.replace(DRAFT_TEXT, text))
                self.assertEqual(result.returncode, 1)
                self.assertIn("still rejected", result.stderr)
                self.assertFalse(self.pending.exists())
                self.assertFalse(self.draft.exists())
                self.assertEqual(self.calls(self.notify_file), [])
                calls = self.calls()
                self.assertEqual(len(calls), 2)
                self.assertIn(reason, self.flag(calls[1]["argv"], "-p"))

    def test_draft_leading_with_image_requests_saves(self):
        result = self.run_script(output=IMAGE_OUTPUT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.draft.read_text(), IMAGE_TEXT + "\n")
        self.assertEqual(len(self.calls()), 1)

    def test_draft_prompt_asks_for_image_requests(self):
        self.run_script(output="SKIP: x\n")
        prompt = self.flag(self.calls()[0]["argv"], "-p")
        self.assertIn('mcp__linear__list_issues with assignee "me" and team "Delivery"', prompt)
        self.assertIn("neither completed nor canceled", prompt)
        self.assertIn("IMAGE_REQUESTS none", prompt)
        self.assertIn("• image requests:", prompt)
        self.assertIn("then the IMAGE_REQUESTS line from step a, then exactly one final line", prompt)

    def test_missing_image_requests_redrafts_once(self):
        no_bullet = IMAGE_OUTPUT.replace(IMAGE_TEXT, DRAFT_TEXT)
        cases = {
            "no bullet": (no_bullet, "Today must start with • image requests: listing DELI-4882 DELI-4787"),
            "bullet not first": (IMAGE_OUTPUT.replace(
                "Today:\n", "Today:\n• review first\n"), "listing DELI-4882 DELI-4787"),
            "missing key": (IMAGE_OUTPUT.replace("DELI-4787 add jq", "DELI-47870 add jq"),
                            "listing DELI-4882 DELI-4787"),
            "suffixed key": (IMAGE_OUTPUT.replace("DELI-4787 add jq", "DELI-4787-x add jq"),
                             "listing DELI-4882 DELI-4787"),
            "no line": (DRAFT_OUTPUT.replace("IMAGE_REQUESTS none\n", ""),
                        "It has no IMAGE_REQUESTS line"),
            "bad key": (IMAGE_OUTPUT.replace("DELI-4882 DELI-4787\n", "DELI-4882 $(x)\n"),
                        "not a list of issue keys"),
            "line inside the fence": (DRAFT_OUTPUT.replace(
                "• review\n```", "• review\nIMAGE_REQUESTS none\n```"),
                "Print IMAGE_REQUESTS outside the fenced block"),
        }
        for name, (output, reason) in cases.items():
            with self.subTest(name):
                self.argv_file.unlink(missing_ok=True)
                result = self.run_script(output=output)
                self.assertEqual(result.returncode, 1)
                self.assertIn("still rejected", result.stderr)
                self.assertFalse(self.pending.exists())
                self.assertFalse(self.draft.exists())
                calls = self.calls()
                self.assertEqual(len(calls), 2)
                self.assertIn(reason, self.flag(calls[1]["argv"], "-p"))
        with self.subTest("redraft drops the earlier keys"):
            self.argv_file.unlink(missing_ok=True)
            result = self.run_script(output=no_bullet, redraft=DRAFT_OUTPUT)
            self.assertEqual(result.returncode, 1)
            self.assertIn("listing DELI-4882 DELI-4787", result.stderr)
            self.assertFalse(self.pending.exists())
            self.assertFalse(self.draft.exists())
            self.assertEqual(len(self.calls()), 2)
        with self.subTest("redraft fixes it"):
            self.argv_file.unlink(missing_ok=True)
            result = self.run_script(output=no_bullet, redraft=IMAGE_OUTPUT)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.draft.read_text(), IMAGE_TEXT + "\n")
            self.assertEqual(len(self.calls()), 2)

    def test_broken_scanner_denies_draft(self):
        (self.rules / "scanner.py").write_text("")
        result = self.run_script(output=DRAFT_OUTPUT)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.pending.exists())
        self.assertIn("scanner blocked it", self.flag(self.calls()[1]["argv"], "-p"))

    def test_show(self):
        missing = self.run_script("--show")
        self.assertEqual(missing.returncode, 1)
        self.save_pending()
        result = self.run_script("--show")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(THREAD_TS, result.stdout)
        self.assertIn(DRAFT_TEXT, result.stdout)
        self.save_pending(day="2026-10-15")
        self.assertEqual(self.run_script("--show").returncode, 1)
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.slack_calls(), [])

    def test_discard(self):
        self.save_pending()
        result = self.run_script("--discard")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.pending.exists())
        self.assertFalse(self.draft.exists())
        self.assertEqual(self.run_script("--approve").returncode, 1)
        self.assertEqual(self.slack_calls(), [])

    def test_approve_without_draft_fails(self):
        for name, day in {"none": None, "yesterday's": "2026-10-15"}.items():
            with self.subTest(name):
                if day:
                    self.save_pending(day=day)
                result = self.run_script("--approve")
                self.assertEqual(result.returncode, 1)
                self.assertIn("no draft waiting", result.stderr)
                self.assertEqual(self.slack_calls(), [])

    def test_approve_posts_once_and_writes_state(self):
        result = self.approve()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [], "approve never runs claude")
        self.assertEqual(self.slack_calls(), [
            ["message", "list", CHANNEL, "--thread-ts", THREAD_TS],
            ["message", "send", CHANNEL, DRAFT_TEXT, "--thread-ts", THREAD_TS],
        ])
        self.assertIn(f"posted {PERMALINK}", result.stderr)
        self.assertEqual(self.sent.read_text(), SENT_TODAY + "\n")
        self.assertEqual(self.state.read_text().strip(), TODAY)
        self.assertEqual(self.posted_at.read_text().strip(), "2026-10-16T09:31:00")
        self.assertFalse(self.pending.exists())
        self.assertFalse(self.draft.exists())
        again = self.approve()
        self.assertEqual(again.returncode, 1)
        self.assertIn("already posted today", again.stderr)
        self.assertEqual(len(self.sends()), 1)

    def test_approve_without_permalink_reports_ts(self):
        result = self.approve(send=json.dumps({"ok": True, "ts": "1.2"}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("posted ts 1.2", result.stderr)
        self.assertIn("~/.config/agent-slack/workspace", result.stderr)
        self.assertEqual(self.state.read_text().strip(), TODAY)

    def test_send_without_ts_still_records_the_send(self):
        result = self.approve(send="garbage")
        self.assertEqual(result.returncode, 1)
        self.assertIn("printed no ts", result.stderr)
        self.assertEqual(self.sent.read_text(), SENT_TODAY + "\n")
        again = self.approve()
        self.assertEqual(again.returncode, 1)
        self.assertIn("already posted today", again.stderr)
        self.assertEqual(len(self.sends()), 1)

    def test_failed_send_is_never_retried_blind(self):
        for name, status in {"error": 1, "timeout": 124}.items():
            with self.subTest(name):
                self.reset_state()
                result = self.approve(send="", send_status=status)
                self.assertEqual(result.returncode, 1)
                self.assertIn("check the thread before any resend", result.stderr)
                self.assertEqual(len(self.sends()), 1)
                self.assertFalse(self.sent.exists())
                self.assertFalse(self.state.exists())
                self.assertTrue(self.pending.exists())
                # The send landed after all, so the next --approve finds the reply.
                again = self.run_script("--approve", thr=thread(SELF_REPLY))
                self.assertEqual(again.returncode, 0, again.stderr)
                self.assertIn("already replied", again.stderr)
                self.assertEqual(len(self.sends()), 1)
                self.assertFalse(self.pending.exists())

    def test_approve_skips_when_user_already_replied(self):
        # A reply posted by hand after the draft drops the draft instead of posting twice.
        result = self.approve(thr=thread(SELF_REPLY))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already replied", result.stderr)
        self.assertEqual(self.sends(), [])
        self.assertFalse(self.pending.exists())
        self.assertFalse(self.draft.exists())
        self.assertFalse(self.state.exists())

    def test_approve_reply_from_someone_else_still_posts(self):
        other = {**SELF_REPLY, "author": {"user_id": "U0OTHER"}}
        result = self.approve(thr=thread(other))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.sends()), 1)

    def test_approve_bad_thread_read_never_sends(self):
        cases = {
            "read fails": {"thr_status": 1},
            "root missing": {"thr": json.dumps({"messages": []})},
            "not json": {"thr": "not json"},
        }
        for name, kwargs in cases.items():
            with self.subTest(name):
                self.reset_state()
                result = self.approve(**kwargs)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(self.sends(), [])
                self.assertTrue(self.pending.exists())

    def test_approve_refuses_thread_outside_window(self):
        for ts in (f"{OLDEST - 1}.000100", f"{LATEST}.000100", "abc"):
            with self.subTest(ts):
                self.save_pending(thread_ts=ts)
                result = self.run_script("--approve")
                self.assertEqual(result.returncode, 1)
                self.assertIn("standup hours", result.stderr)
                self.assertEqual(self.slack_calls(), [])

    def test_approve_rescreens_the_saved_draft(self):
        cases = {
            "em dash": (DRAFT_TEXT.replace("review", f"review {EM_DASH} docs"), "No em dashes."),
            "bare pull request": (DRAFT_TEXT + " mono#70016", "mono#70016"),
            "control characters": ("Moved:\n• a\x1b[8mb", "control characters"),
            "empty": ("  ", "empty"),
        }
        for name, (text, reason) in cases.items():
            with self.subTest(name):
                self.save_pending(text=text)
                result = self.run_script("--approve")
                self.assertEqual(result.returncode, 1)
                self.assertIn(reason, result.stderr)
                self.assertEqual(self.slack_calls(), [])
                self.assertTrue(self.pending.exists())

    def test_approve_keeps_draft_text_literal(self):
        text = "Moved:\n• $(touch pwned) `id` $HOME \\n done"
        self.save_pending(text=text)
        result = self.run_script("--approve")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.sends()[0][3], text)
        self.assertFalse((self.home / ".local/state/standup-post/pwned").exists())

    def test_markdown_pr_links_pass(self):
        for text in ("• merged [acme/app#70016](https://github.com/acme/app/pull/70016) today",
                     "• [acme/app#39](https://github.com/acme/app/pull/39) (owners), then [acme/app#40](https://github.com/acme/app/pull/40)"):
            with self.subTest(text):
                self.reset_state()
                self.save_pending(text=text)
                result = self.run_script("--approve")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(self.sends()), 1)

    def test_markdown_link_text_does_not_hide_a_bare_number(self):
        self.save_pending(text="• merged [acme/app#70016](https://github.com/acme/app/pull/70016) and #41")
        result = self.run_script("--approve")
        self.assertEqual(result.returncode, 1)
        self.assertIn("#41", result.stderr)

    def test_bare_pr_numbers_block_the_post(self):
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
                self.reset_state()
                self.save_pending(text=bare)
                denied = self.run_script("--approve")
                self.assertEqual(denied.returncode, 1)
                self.assertIn(ref, denied.stderr)
                self.assertIn("[owner/repo#<n>](https://github.com/<owner>/<repo>/pull/<n>)", denied.stderr)
                self.assertEqual(self.sends(), [])
                self.save_pending(text=cited)
                self.assertEqual(self.run_script("--approve").returncode, 0)
                self.assertEqual(len(self.sends()), 1)
        for text in ("filed FUL-917", "blocked on ECO-5500", "filed ECO-12345", "triaged 48 feedback items",
                     "reviewed 120 files", "over 1500 tests", "issue 4567", "70% merge-rate", "standup at 17:31", "planned for October 2026"):
            with self.subTest(text):
                self.reset_state()
                self.save_pending(text=text)
                result = self.run_script("--approve")
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_draft_with_control_characters_is_refused(self):
        fenced = "```\nMoved:\n• fine\x1b[8m hidden\n```\nIMAGE_REQUESTS none\n"
        result = self.run_script(output=fenced + "DRAFT\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("control characters", result.stderr)
        self.assertFalse(self.pending.exists())
        self.assertFalse(self.draft.exists())

    def test_show_refuses_control_characters(self):
        self.save_pending(text="Moved:\n• a\x1b[8mb")
        result = self.run_script("--show")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("\x1b", result.stdout)
        self.assertIn("--discard", result.stderr)

    def test_send_record_without_state_skips_everything(self):
        self.sent.parent.mkdir(parents=True)
        self.sent.write_text(SENT_TODAY + "\n")
        result = self.run_script(output=DRAFT_OUTPUT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already posted today", result.stderr)
        self.assertEqual(self.state.read_text().strip(), TODAY)
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.slack_calls(), [])
        self.assertFalse(self.pending.exists())

    def test_send_record_is_per_day(self):
        self.sent.parent.mkdir(parents=True)
        self.sent.write_text(f"2026-10-15 {OLDEST - 86400}.1\n")
        result = self.approve()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.sends()), 1)
        self.assertEqual(self.sent.read_text(), SENT_TODAY + "\n")

    def test_skip_writes_no_state(self):
        result = self.run_script(output="SKIP: nothing to report\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.pending.exists())
        self.assertEqual(self.calls(self.notify_file), [])

    def test_failures_exit_one(self):
        cases = {
            "error": ("ERROR: no evidence\n", 0),
            "garbage": ("here is your draft\n", 0),
            "post when drafting": (f"POSTED {PERMALINK}\n", 0),
            "claude failed": (DRAFT_OUTPUT, 1),
        }
        for name, (output, status) in cases.items():
            with self.subTest(name):
                result = self.run_script(output=output, status=status)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(self.state.exists())
                self.assertFalse(self.pending.exists())
                self.assertEqual(self.sends(), [])

    def test_dry_run(self):
        result = self.run_script("--dry-run", output="```\nMoved:\n```\nDRAFT\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Moved:", result.stdout)
        self.assertIn(f"thread {THREAD_TS}", result.stdout)
        argv = self.calls()[0]["argv"]
        self.assertIn("DRAFT ONLY", self.flag(argv, "-p"))
        self.assertFalse(self.state.exists())
        self.assertFalse(self.pending.exists())
        self.assertFalse(self.draft.exists())
        self.assertEqual(self.calls(self.notify_file), [])
        self.assertEqual(self.sends(), [])

    def test_dry_run_rejects_post(self):
        result = self.run_script("--dry-run", output=f"POSTED {PERMALINK}\n")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.state.exists())

    def test_command(self):
        self.run_script(output="SKIP: x\n")
        call = self.calls()[0]
        argv = call["argv"]
        tools = self.allowed_tools(argv)
        for tool in tools:
            self.assertNotIn(tool.split("(")[0], {"Write", "Edit", "NotebookEdit"})
            self.assertNotEqual(tool, "Bash")
            self.assertNotEqual(tool, "Bash(*)")
            # The script reads and posts, so drafting gets no Slack access.
            self.assertNotIn("slack", tool.lower())
        self.assertEqual(self.flag(argv, "--permission-mode"), "dontAsk")
        self.assertEqual(self.flag(argv, "--setting-sources"), "project,local")
        self.assertNotIn("--settings", argv)
        self.assertIn("--no-session-persistence", argv)
        self.assertIn("[standup-update]", self.flag(argv, "-p"))
        # Outside $HOME, so ~/.claude/settings.json never loads as project settings.
        self.assertEqual(call["cwd"], str(self.home / ".local/state/standup-post"))
        self.assertNotIn("Read", tools)
        # A prefix rule cannot restrict file arguments: jq reads any file and
        # date -f echoes each unparsable line back in its error.
        for tool in tools:
            self.assertFalse(tool.startswith(("Bash(jq", "Bash(date")), tool)
        self.assertIn("Read(~/.claude/projects/**)", tools)
        prompt = self.flag(argv, "-p")
        # Midnight Rome on Thursday is 22:00 UTC the day before.
        self.assertIn("window starting 2026-10-14T22:00:00", prompt)
        self.assertIn('--updated ">=2026-09-16"', prompt)
        self.assertIn("The team is Test Team.", prompt)
        self.assertIn("No work GitHub organisation is configured, so no repository counts as work: report Linear only and leave out all GitHub activity.", prompt)
        self.assertNotIn(CHANNEL, prompt)

    def test_work_org_reaches_prompt(self):
        (self.home / ".config/work-context.env").write_text(
            "WORK_GITHUB_ORG=example-org\nSTANDUP_CHANNEL=C0OTHER\n")
        self.run_script(output="SKIP: x\n")
        prompt = self.flag(self.calls()[0]["argv"], "-p")
        self.assertIn("The work GitHub organisation is example-org.", prompt)
        self.assertNotIn("No work GitHub organisation", prompt)
        self.assertEqual(self.slack_calls()[0][2], CHANNEL)

    def test_monday_window_starts_friday(self):
        monday_ts = f"{OLDEST + 3 * 86400 + 60}.1"
        self.run_script(output="SKIP: x\n", now="2026-10-19T09:31:00Z",
                        hist=history(root(monday_ts)), thr=thread(ts=monday_ts))
        prompt = self.flag(self.calls()[0]["argv"], "-p")
        self.assertIn("window starting 2026-10-15T22:00:00", prompt)

    def test_window_starts_at_last_post(self):
        self.posted_at.parent.mkdir(parents=True, exist_ok=True)
        self.posted_at.write_text("2026-10-15T10:43:57\n")
        self.run_script(output="SKIP: x\n")
        prompt = self.flag(self.calls()[0]["argv"], "-p")
        self.assertIn("window starting 2026-10-15T10:43:57", prompt)

    def test_stale_or_bad_post_time_falls_back(self):
        self.posted_at.parent.mkdir(parents=True, exist_ok=True)
        for value in ("2026-10-01T10:00:00", "garbage", "2026-10-20T10:00:00"):
            with self.subTest(value):
                self.posted_at.write_text(value + "\n")
                self.run_script(output="SKIP: x\n")
                prompt = self.flag(self.calls()[-1]["argv"], "-p")
                self.assertIn("window starting 2026-10-14T22:00:00", prompt)

    def test_missing_scanner_file_fails_closed(self):
        for name in ("scanner.py", "policy.json", "rules.md"):
            for args in ((), ("--approve",)):
                with self.subTest(name=name, args=args):
                    self.reset_state()
                    if args:
                        self.save_pending()
                    (self.rules / name).unlink()
                    result = self.run_script(*args, output=DRAFT_OUTPUT)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(name, result.stderr)
                    self.assertEqual(self.calls(), [])
                    self.assertEqual(self.slack_calls(), [])
                    (self.rules / name).write_text("")

    def test_bad_standup_env_fails_closed(self):
        cases = {
            "missing file": (None, "missing"),
            "missing key": (STANDUP_ENV.replace(f"STANDUP_SELF={SELF}\n", ""),
                            "does not set STANDUP_SELF"),
            "bad channel": (STANDUP_ENV.replace(CHANNEL, "c0test00001"),
                            "not a Slack channel ID"),
            "bad subteam": (STANDUP_ENV.replace(SUBTEAM, "S0.*"), "not a Slack user group ID"),
            "bad team": (STANDUP_ENV.replace("'Test Team'", "'Team $(x)'"),
                         "STANDUP_TEAM"),
        }
        for name, (content, message) in cases.items():
            with self.subTest(name):
                if content is None:
                    self.standup_env.unlink()
                else:
                    self.standup_env.write_text(content)
                result = self.run_script(output=DRAFT_OUTPUT)
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
                self.assertEqual(self.calls(), [])
                self.assertEqual(self.slack_calls(), [])
                self.standup_env.write_text(STANDUP_ENV)


if __name__ == "__main__":
    unittest.main()
