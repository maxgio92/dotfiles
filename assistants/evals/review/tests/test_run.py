import contextlib
import datetime
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[1]
CASES_DIR = EVAL_DIR / "cases"
sys.path.insert(0, str(EVAL_DIR))

import run  # noqa: E402

DAY = datetime.date(2026, 1, 2)

DASTARDLY_FINAL = "Problem: sum a series.\n\n[block] series.py:5: loop bound reads past the end\n\nIndexError.\n\nVerdict: request-changes\n"

REVIEW_PR_FINAL = """\
# Review: series

Passes: dastardly, codex

```markdown
Request changes

### block: loop bound reads past the end

`range(n + 1)` reads one past the end.

Reference: `series.py:head:5`
```
"""


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def result_event(text):
    return json.dumps({"type": "result", "subtype": "success", "result": text})


def bash_event(command):
    return json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": command}}]}})


# The shape of an Agent call in a stream-json log: the launch, the subagent's
# own events tagged with parent_tool_use_id, then the tool_result.
def agent_events(subagent_type, report, tool_id="toolu_1"):
    launch = {"type": "tool_use", "id": tool_id, "name": "Agent", "input": {"subagent_type": subagent_type, "prompt": "review"}}
    inner = {"type": "text", "text": "[nit] scratch.py:1: draft inside the subagent\n\nVerdict: approve\n"}
    result = {"type": "tool_result", "tool_use_id": tool_id, "content": [{"type": "text", "text": report}]}
    return [
        json.dumps({"type": "assistant", "message": {"content": [launch]}, "parent_tool_use_id": None}),
        json.dumps({"type": "assistant", "message": {"content": [inner]}, "parent_tool_use_id": tool_id}),
        json.dumps({"type": "user", "message": {"content": [result]}, "parent_tool_use_id": None}),
    ]


# A relay that restates the report without the finding and verdict lines.
RELAY = "Dastardly found one blocking issue: the loop reads past the end. It asks for changes."


class FakeExecutor:
    """Stands in for ``claude -p``: records each call and writes what the reviewer would."""

    def __init__(self, env, dastardly=DASTARDLY_FINAL, review_pr=REVIEW_PR_FINAL, extra_events=(), gh_argv=None):
        # dastardly=None stands for a session that never launched dastardly.
        self.env, self.dastardly, self.review_pr, self.extra = env, dastardly, review_pr, list(extra_events)
        # gh_argv, when set, is run through the row's PATH as the reviewer would.
        self.gh_argv = gh_argv
        self.calls = []

    def __call__(self, command, cwd, env):
        self.calls.append((command, cwd, env))
        if self.gh_argv is not None:
            shim = shutil.which(self.gh_argv[0], path=env["PATH"])
            # Refuse to run anything but a shim, so a broken PATH cannot reach GitHub.
            assert shim and Path(shim).parent == Path(env["PATH"].split(os.pathsep)[0]), shim
            subprocess.run([shim, *self.gh_argv[1:]], cwd=cwd, env=env, check=False)
        prompt = command[2]
        events = list(self.extra)
        if prompt.startswith("/review-pr"):
            if self.review_pr is not None:
                path = run.report_path(self.env, cwd, DAY)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(self.review_pr)
            final = "Report saved."
        else:
            if self.dastardly is not None:
                events += agent_events("dastardly", self.dastardly)
            final = RELAY
        return "\n".join([*events, result_event(final)]) + "\n"


def write_case(root, name, case_json):
    case_dir = root / name
    for tree, body in (("base", "for i in range(n):\n"), ("head", "for i in range(n + 1):\n")):
        (case_dir / tree).mkdir(parents=True)
        (case_dir / tree / "series.py").write_text(body)
    (case_dir / "case.json").write_text(json.dumps(case_json))
    return case_dir


OFF_BY_ONE = {
    "must_flag": [{"pattern": "past the end", "file": "series.py", "lines": [4, 6]}],
    "must_not_flag": [],
    "verdict": "request-changes",
    "min_score": 1.0,
}


class FixtureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_review_pr_fixture_commits_head_on_case(self) -> None:
        case_dir = CASES_DIR / "clean-rename"
        repo = run.build_fixture(case_dir, self.tmp, run.REVIEW_PR)
        self.assertEqual(repo.name, "review-eval-clean-rename")
        self.assertEqual(git(repo, "branch", "--show-current").strip(), "main")
        self.assertEqual(git(repo, "status", "--porcelain"), "")
        self.assertEqual(sorted(git(repo, "ls-tree", "-r", "--name-only", "main").split()), ["calc.py", "main.py"])
        self.assertEqual(sorted(git(repo, "ls-tree", "-r", "--name-only", "case").split()), ["cart.py", "main.py"])
        self.assertEqual(git(repo, "rev-list", "--count", "main..case").strip(), "1")
        (self.tmp / "again").mkdir()
        again = run.build_fixture(case_dir, self.tmp / "again", run.REVIEW_PR)
        self.assertEqual(git(repo, "rev-parse", "case"), git(again, "rev-parse", "case"), "head SHA must be stable across builds")

    def test_dastardly_fixture_leaves_head_uncommitted(self) -> None:
        case_dir = CASES_DIR / "clean-rename"
        repo = run.build_fixture(case_dir, self.tmp, run.DASTARDLY)
        self.assertEqual(git(repo, "branch", "--list").strip(), "* main")
        self.assertEqual(git(repo, "rev-list", "--count", "HEAD").strip(), "1")
        changed = sorted(git(repo, "diff", "--no-renames", "HEAD", "--name-status").splitlines())
        self.assertEqual(changed, ["A\tcart.py", "D\tcalc.py", "M\tmain.py"])
        self.assertEqual((repo / "cart.py").read_bytes(), (case_dir / "head" / "cart.py").read_bytes())


class CommandTest(unittest.TestCase):
    def test_rows(self) -> None:
        repo = Path("/tmp/x/review-eval-c")
        expected = {
            "dastardly-single": ("/code-review Claude only", False),
            "dastardly-two": ("/code-review", True),
            "review-pr-single": ("/review-pr --tier junior --local /tmp/x/review-eval-c --base main --head case", False),
            "review-pr-two": ("/review-pr --tier senior --local /tmp/x/review-eval-c --base main --head case", True),
        }
        self.assertEqual(run.ROW_NAMES, tuple(expected))
        for row in run.ROWS:
            prompt, two_model = expected[row.name]
            with self.subTest(row=row.name):
                command = run.build_command(row, repo, 40, 2.0)
                allowed = command.index("--allowedTools")
                tools = command[allowed + 1 :]
                self.assertNotIn("--disallowedTools", command)
                self.assertEqual(command[:3], ["claude", "-p", prompt])
                self.assertEqual(
                    command[3:allowed],
                    ["--output-format", "stream-json", "--verbose", "--permission-mode", "dontAsk", "--no-session-persistence", "--max-turns", "40", "--max-budget-usd", "2"],
                )
                shims = ["Bash(gh:*)", "Bash(gh-review-post:*)", "Bash(gh-review-reply:*)", "Bash(gh-api-safe:*)"]
                single = ["Agent", "Read", "Glob", "Grep", "Write", "Bash(git:*)", "Bash(mkdir:*)", *shims]
                companion = ["Bash(node:*)", "Bash([:*)", "Bash(ls:*)", "Bash(sort:*)", "Bash(tail:*)"]
                self.assertEqual(tools, single + companion if two_model else single)
                self.assertNotIn("--bare", command)

    def test_limits_override(self) -> None:
        command = run.build_command(run.ROWS[0], Path("/r"), 7, 0.5)
        self.assertEqual(command[command.index("--max-turns") + 1], "7")
        self.assertEqual(command[command.index("--max-budget-usd") + 1], "0.5")


class PathTest(unittest.TestCase):
    def test_report_path_uses_fixed_repo_name_and_short_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = run.build_fixture(CASES_DIR / "off-by-one-loop", Path(tmp), run.REVIEW_PR)
            head = git(repo, "rev-parse", "case").strip()
            path = run.report_path({"XDG_DATA_HOME": "/data"}, repo, DAY)
            self.assertEqual(path, Path(f"/data/agent-reports/review-eval-off-by-one-loop/2026-01-02-review-pr-local-{head[:12]}.md"))

    def test_data_home_fallback(self) -> None:
        for env, want in (
            ({"XDG_DATA_HOME": "/x", "HOME": "/h"}, "/x"),
            ({"XDG_DATA_HOME": "", "HOME": "/h"}, "/h/.local/share"),
            ({"HOME": "/h"}, "/h/.local/share"),
        ):
            with self.subTest(env=env):
                self.assertEqual(run.data_home(env), Path(want))
        self.assertEqual(run.summary_path({"HOME": "/h"}, DAY), Path("/h/.local/share/agent-reports/dotfiles/2026-01-02-eval-reviews.md"))

    def test_agent_report_takes_the_last_top_level_dastardly_result(self) -> None:
        stream = "\n".join(
            [
                *agent_events("dastardly", "first", "toolu_1"),
                "not json",
                *agent_events("peter", "not dastardly", "toolu_2"),
                *agent_events("dastardly", "last", "toolu_3"),
                result_event(RELAY),
            ]
        )
        self.assertEqual(run.agent_report(stream, "dastardly"), "last")
        self.assertIsNone(run.agent_report("\n".join([bash_event("git diff"), result_event(DASTARDLY_FINAL)]), "dastardly"))


class ShimTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_each_shim_logs_its_argv_and_exits_1(self) -> None:
        log = run.install_shims(self.tmp)
        self.assertEqual(log, self.tmp / run.SHIM_LOG)
        self.assertEqual(log.read_text(), "")
        for name in run.SHIM_NAMES:
            result = subprocess.run([str(self.tmp / name), "pr", "comment", "1", "--body", "a 'b' \"c\""], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1, name)
        lines = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual(lines, [{"name": name, "args": ["pr", "comment", "1", "--body", "a 'b' \"c\""]} for name in run.SHIM_NAMES])

    def test_row_env_puts_shims_first_and_drops_credentials(self) -> None:
        env = {"PATH": "/usr/bin", "HOME": "/h", "GH_TOKEN": "x", "GITHUB_TOKEN": "y", "GH_ENTERPRISE_TOKEN": "z", "GITHUB_ENTERPRISE_TOKEN": "w", "GH_CONFIG_DIR": "/h/.config/gh"}
        out = run.row_env(env, Path("/shims"), Path("/shims/config"))
        placeholder = run.GH_PLACEHOLDER_TOKEN
        self.assertEqual(out, {"PATH": f"/shims{os.pathsep}/usr/bin", "HOME": "/h", "GH_CONFIG_DIR": "/shims/config", "GH_TOKEN": placeholder, "GH_ENTERPRISE_TOKEN": placeholder})
        self.assertEqual(run.row_env({}, Path("/shims"), Path("/c"))["PATH"], "/shims")

    def test_trial_runs_with_shims_and_an_empty_gh_config(self) -> None:
        seen = {}

        def execute(command, cwd, env):
            shim_dir = Path(env["PATH"].split(os.pathsep)[0])
            seen["shims"] = sorted(p.name for p in shim_dir.iterdir() if p.is_file() and os.access(p, os.X_OK))
            seen["config"] = list(Path(env["GH_CONFIG_DIR"]).iterdir())
            seen["tokens"] = [k for k in run.GH_TOKEN_VARS if env.get(k, run.GH_PLACEHOLDER_TOKEN) != run.GH_PLACEHOLDER_TOKEN]
            seen["repo_parent"] = cwd.parent
            seen["shim_dir"] = shim_dir
            return "\n".join(agent_events("dastardly", DASTARDLY_FINAL))

        args = run.parse_args([])
        loaded = run.load_case(CASES_DIR / "off-by-one-loop" / "case.json")
        run.run_trial(loaded, CASES_DIR / "off-by-one-loop", run.ROWS[0], args, execute, {"PATH": "/usr/bin", "GH_TOKEN": "x"}, lambda: DAY, self.tmp / "s.stream.jsonl")
        self.assertEqual(seen["shims"], sorted(run.SHIM_NAMES))
        self.assertEqual((seen["config"], seen["tokens"]), ([], []))
        self.assertNotEqual(seen["shim_dir"], seen["repo_parent"])


class MainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.env = {"XDG_DATA_HOME": str(self.tmp / "data"), "HOME": str(self.tmp / "home")}
        self.cases = self.tmp / "cases"

    def main(self, argv, execute):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run.main(argv, execute=execute, env=self.env, today=lambda: DAY, cases_dir=self.cases)
        return code, out.getvalue().splitlines()

    def test_passing_suite_exits_0_and_writes_summary(self) -> None:
        write_case(self.cases, "loop", OFF_BY_ONE)
        fake = FakeExecutor(self.env)
        code, lines = self.main(["--trials", "2"], fake)
        self.assertEqual(code, 0)
        self.assertEqual(lines[:4], [f"loop {row} 1.00" for row in run.ROW_NAMES])
        self.assertEqual(len(fake.calls), 8)
        self.assertTrue(all(cwd.name == "review-eval-loop" for _, cwd, _ in fake.calls))
        summary = run.summary_path(self.env, DAY)
        self.assertEqual(lines[4], f"summary: {summary}")
        self.assertIn("| loop | review-pr-two | 1.00 | pass |", summary.read_text())

    def test_row_and_case_filters(self) -> None:
        write_case(self.cases, "loop", OFF_BY_ONE)
        write_case(self.cases, "other", OFF_BY_ONE)
        fake = FakeExecutor(self.env)
        code, lines = self.main(["--case", "other", "--row", "dastardly-single"], fake)
        self.assertEqual((code, lines[0]), (0, "other dastardly-single 1.00"))
        self.assertEqual(len(fake.calls), 1)

    def test_below_min_score_exits_1(self) -> None:
        write_case(self.cases, "loop", OFF_BY_ONE)
        fake = FakeExecutor(self.env, dastardly="Verdict: approve\n")
        code, lines = self.main(["--row", "dastardly-single", "--row", "review-pr-single"], fake)
        self.assertEqual(code, 1)
        self.assertEqual(lines[:2], ["loop dastardly-single 0.00", "loop review-pr-single 1.00"])

    def test_dastardly_row_scores_the_agent_result_not_the_relay(self) -> None:
        write_case(self.cases, "loop", OFF_BY_ONE)
        code, lines = self.main(["--row", "dastardly-single"], FakeExecutor(self.env))
        self.assertEqual((code, lines[0]), (0, "loop dastardly-single 1.00"))
        # The relay alone, with no dastardly Agent call, is an error, not a score.
        code, lines = self.main(["--row", "dastardly-single"], FakeExecutor(self.env, dastardly=None))
        self.assertEqual((code, lines[0]), (1, "loop dastardly-single ERROR"))

    def test_logged_write_fails_the_row(self) -> None:
        write_case(self.cases, "loop", OFF_BY_ONE)
        for argv in (["gh", "pr", "review", "1", "--approve"], ["gh-review-post", "url", "--body-file", "r.md"]):
            with self.subTest(argv=argv):
                code, lines = self.main(["--row", "dastardly-single"], FakeExecutor(self.env, gh_argv=argv))
                self.assertEqual((code, lines[0]), (1, "loop dastardly-single 0.00"))
                self.assertIn(f"write call: {' '.join(argv)}", run.summary_path(self.env, DAY).read_text())

    def test_failed_and_error_rows_cite_the_saved_stream(self) -> None:
        write_case(self.cases, "loop", OFF_BY_ONE)
        fake = FakeExecutor(self.env, dastardly="Verdict: approve\n", review_pr=None, gh_argv=["gh", "pr", "view", "1"])
        code, _ = self.main(["--trials", "2", "--row", "dastardly-single", "--row", "review-pr-single"], fake)
        self.assertEqual(code, 1)
        summary = run.summary_path(self.env, DAY)
        text = summary.read_text()
        for row in ("dastardly-single", "review-pr-single"):
            for trial in (1, 2):
                with self.subTest(row=row, trial=trial):
                    stream = run.stream_path(self.env, DAY, "loop", row, trial)
                    self.assertEqual(stream.parent, summary.parent)
                    self.assertIn(f"- loop {row}: stream: {stream}\n", text)
                    self.assertIn(result_event("Report saved." if row.startswith("review-pr") else RELAY), stream.read_text())
                    calls = [json.loads(line) for line in run.calls_path(stream).read_text().splitlines()]
                    self.assertEqual(calls, [{"name": "gh", "args": ["pr", "view", "1"]}])

    def test_passing_row_keeps_the_stream_without_citing_it(self) -> None:
        write_case(self.cases, "loop", OFF_BY_ONE)
        self.main(["--row", "dastardly-single"], FakeExecutor(self.env))
        self.assertTrue(run.stream_path(self.env, DAY, "loop", "dastardly-single", 1).is_file())
        self.assertNotIn("stream:", run.summary_path(self.env, DAY).read_text())

    def test_framed_dastardly_report_scores_like_the_plain_one(self) -> None:
        write_case(self.cases, "loop", OFF_BY_ONE)
        framed = "Report from the dastardly agent:\n" + "".join(f"  {line}" if line.strip() else line for line in DASTARDLY_FINAL.splitlines(keepends=True))
        code, lines = self.main(["--row", "dastardly-single"], FakeExecutor(self.env, dastardly=framed))
        self.assertEqual((code, lines[0]), (0, "loop dastardly-single 1.00"))

    def test_logged_read_passes_the_row(self) -> None:
        write_case(self.cases, "loop", OFF_BY_ONE)
        fake = FakeExecutor(self.env, gh_argv=["gh", "pr", "view", "1"])
        code, lines = self.main(["--row", "review-pr-single"], fake)
        self.assertEqual((code, lines[0]), (0, "loop review-pr-single 1.00"))
        self.assertIn("read call: gh pr view 1", run.summary_path(self.env, DAY).read_text())

    def test_shim_dir_is_removed_after_the_row(self) -> None:
        write_case(self.cases, "loop", OFF_BY_ONE)
        fake = FakeExecutor(self.env)
        self.main(["--row", "dastardly-single"], fake)
        shim_dir = Path(fake.calls[0][2]["PATH"].split(os.pathsep)[0])
        self.assertFalse(shim_dir.exists())

    def test_missing_report_and_stale_report_are_error(self) -> None:
        write_case(self.cases, "loop", OFF_BY_ONE)
        # A report from an earlier run sits at the predictable path; the runner
        # removes it so a run that writes nothing cannot reuse it.
        with tempfile.TemporaryDirectory() as tmp:
            repo = run.build_fixture(self.cases / "loop", Path(tmp), run.REVIEW_PR)
            stale = run.report_path(self.env, repo, DAY)
        stale.parent.mkdir(parents=True)
        stale.write_text(REVIEW_PR_FINAL)
        code, lines = self.main(["--row", "review-pr-single"], FakeExecutor(self.env, review_pr=None))
        self.assertEqual((code, lines[0]), (1, "loop review-pr-single ERROR"))
        self.assertFalse(stale.exists())

    def test_bad_pattern_exits_2(self) -> None:
        write_case(self.cases, "loop", OFF_BY_ONE)
        write_case(self.cases, "broken", {**OFF_BY_ONE, "must_flag": [{"pattern": "("}]})
        fake = FakeExecutor(self.env)
        code, lines = self.main(["--row", "dastardly-single"], fake)
        self.assertEqual(code, 2)
        self.assertEqual(lines[:2], ["broken dastardly-single ERROR", "loop dastardly-single 1.00"])
        self.assertEqual(len(fake.calls), 1, "a case that fails to load runs no model")

    def test_dry_run_prints_commands_and_runs_nothing(self) -> None:
        write_case(self.cases, "loop", OFF_BY_ONE)

        def refuse(command, cwd, env):
            raise AssertionError("dry run executed a command")

        code, lines = self.main(["--dry-run", "--max-turns", "5"], refuse)
        self.assertEqual(code, 0)
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[0].startswith("loop dastardly-single: (cd "))
        self.assertIn("claude -p '/code-review Claude only'", lines[0])
        self.assertIn("--max-turns 5", lines[0])
        self.assertFalse(run.summary_path(self.env, DAY).exists())


if __name__ == "__main__":
    unittest.main()
