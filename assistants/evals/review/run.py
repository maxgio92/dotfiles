"""Run the review eval cases against dastardly and review-pr with ``claude -p``.

Every row is a paid live model call. Offline tests inject a fake executor
through ``main(execute=...)``; nothing here runs a model unless the default
executor is used.

Per row and trial the runner builds a throwaway git repository from the case's
``base/`` and ``head/`` trees, runs one ``claude -p`` command with that
repository as its working directory and gh shims first on PATH, and scores the
result with ``score.py``:
dastardly's own Agent tool_result for dastardly rows, the saved local-mode
report for review-pr rows. A gh write logged by a shim zeroes the row.

Accepted residual: only gh calls that reach a shim are scored. In dastardly
rows a command form the allowlist does not grant, such as ``env gh`` or
``bash -c 'gh ...'``, is denied under dontAsk before it runs and is not
scored; the permission layer still blocks it. review-pr rows run under the
skill's unrestricted Bash grant, so those forms run into the shim and are
scored. An absolute path such as ``/usr/bin/gh`` skips the shim in any row
and is not scored; it runs the real gh with a placeholder token and an
empty GH_CONFIG_DIR, so GitHub rejects it with a 401.

Exit codes: 2 when a case fails to load (a bad pattern), 1 when a row's trial
mean is below the case ``min_score`` or the suite pass rate is below
``score.DEFAULT_MIN_PASS_RATE``, otherwise 0.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from score import (  # noqa: E402
    DASTARDLY,
    DEFAULT_MIN_PASS_RATE,
    REVIEW_PR,
    CaseError,
    RowResult,
    load_case,
    row_passed,
    score_output,
    suite_passed,
    trial_mean,
)

CASES_DIR = Path(__file__).resolve().parent / "cases"
DEFAULT_MAX_TURNS = 40
DEFAULT_MAX_BUDGET_USD = 2.0

# Every row runs with these names first on PATH. Each shim logs its argv and
# exits 1, so a row cannot reach GitHub through them, and the scorer reads the
# log to fail a row that tried to write.
SHIM_NAMES = ("gh", "gh-review-post", "gh-review-reply", "gh-api-safe")
SHIM_LOG = "calls.jsonl"
# gh credentials from the environment (https://cli.github.com/manual/gh_help_environment).
# row_env drops them and sets GH_TOKEN and GH_ENTERPRISE_TOKEN to a placeholder:
# an environment token wins over the config file and the keyring, so a real gh
# reached by absolute path gets a 401. A model that rewrites its own
# environment inside a review-pr row, whose skill grants all of Bash, can still
# reach the user's credentials; the shim log does not cover that.
GH_TOKEN_VARS = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")
GH_PLACEHOLDER_TOKEN = "invalid-eval-token"

# Allowing the shim names is safe: the shims are first on PATH and exit 1, and
# row_env leaves only a placeholder gh token and an empty GH_CONFIG_DIR, so an allowed call is
# logged and scored instead of reaching GitHub. Each name needs its own rule,
# since Bash(gh:*) does not match gh-review-post.
SINGLE_MODEL_TOOLS = ("Agent", "Read", "Glob", "Grep", "Write", "Bash(git:*)", "Bash(mkdir:*)") + tuple(
    f"Bash({name}:*)" for name in SHIM_NAMES
)
# The Codex companion runs through node. The codex skill locates it with
# `[ -f ... ] || ... $(ls -d ... | sort -V | tail -1)`, and dontAsk denies
# each of those commands unless it is listed here.
TWO_MODEL_TOOLS = SINGLE_MODEL_TOOLS + ("Bash(node:*)", "Bash([:*)", "Bash(ls:*)", "Bash(sort:*)", "Bash(tail:*)")

_SHIM = """#!{python} -I
import json, sys
with open({log!r}, "a", encoding="utf-8") as log:
    log.write(json.dumps({{"name": {name!r}, "args": sys.argv[1:]}}) + "\\n")
sys.exit(1)
"""

BASE_BRANCH = "main"
HEAD_BRANCH = "case"

# Fixed identity and dates give every build of a case the same head SHA, so the
# review-pr report path is the same on every trial.
_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Review Eval",
    "GIT_AUTHOR_EMAIL": "review-eval@example.invalid",
    "GIT_COMMITTER_NAME": "Review Eval",
    "GIT_COMMITTER_EMAIL": "review-eval@example.invalid",
    "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+0000",
    "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+0000",
    # User and system config (hooks, signing, templates) stay out of fixtures.
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


@dataclass(frozen=True)
class Row:
    name: str
    reviewer: str
    two_model: bool

    def prompt(self, repo: Path) -> str:
        if self.reviewer == DASTARDLY:
            return "/code-review" if self.two_model else "/code-review Claude only"
        tier = "senior" if self.two_model else "junior"
        return f"/review-pr --tier {tier} --local {repo} --base {BASE_BRANCH} --head {HEAD_BRANCH}"

    @property
    def tools(self) -> tuple[str, ...]:
        return TWO_MODEL_TOOLS if self.two_model else SINGLE_MODEL_TOOLS


ROWS = (
    Row("dastardly-single", DASTARDLY, False),
    Row("dastardly-two", DASTARDLY, True),
    Row("review-pr-single", REVIEW_PR, False),
    Row("review-pr-two", REVIEW_PR, True),
)
ROW_NAMES = tuple(row.name for row in ROWS)

# Runs a command in a directory with an environment and returns its stdout
# (the stream-json log).
Executor = Callable[[list[str], Path, Mapping[str, str]], str]


def subprocess_executor(command: list[str], cwd: Path, env: Mapping[str, str]) -> str:
    return subprocess.run(command, cwd=cwd, env=dict(env), capture_output=True, text=True, check=False).stdout


def install_shims(directory: Path) -> Path:
    """Write the gh shims into ``directory`` and return the log they append to."""
    log = directory / SHIM_LOG
    log.touch()
    for name in SHIM_NAMES:
        shim = directory / name
        shim.write_text(_SHIM.format(python=sys.executable, log=str(log), name=name), encoding="utf-8")
        shim.chmod(0o755)
    return log


def row_env(env: Mapping[str, str], shim_dir: Path, gh_config_dir: Path) -> dict[str, str]:
    """Return ``env`` with the shims first on PATH and a placeholder gh token."""
    out = {k: v for k, v in env.items() if k not in GH_TOKEN_VARS}
    path = env.get("PATH")
    out["PATH"] = f"{shim_dir}{os.pathsep}{path}" if path else str(shim_dir)
    out["GH_CONFIG_DIR"] = str(gh_config_dir)
    out["GH_TOKEN"] = GH_PLACEHOLDER_TOKEN
    out["GH_ENTERPRISE_TOKEN"] = GH_PLACEHOLDER_TOKEN
    return out


def build_command(row: Row, repo: Path, max_turns: int, max_budget_usd: float) -> list[str]:
    # No --bare: it skips slash commands, and every row is one.
    return [
        "claude",
        "-p",
        row.prompt(repo),
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        "dontAsk",
        "--no-session-persistence",
        "--max-turns",
        str(max_turns),
        "--max-budget-usd",
        f"{max_budget_usd:g}",
        "--allowedTools",
        *row.tools,
    ]


def repo_dir_name(case_name: str) -> str:
    return f"review-eval-{case_name}"


def _git(repo: Path, *args: str) -> str:
    env = {**os.environ, **_GIT_ENV}
    result = subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _files(root: Path) -> list[Path]:
    return sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file())


def _copy_tree(src: Path, dest: Path) -> None:
    for rel in _files(src):
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / rel, dest / rel)


def _apply_head(case_dir: Path, repo: Path) -> None:
    # A file in base/ that is missing from head/ is a deletion.
    for rel in set(_files(case_dir / "base")) - set(_files(case_dir / "head")):
        (repo / rel).unlink()
    _copy_tree(case_dir / "head", repo)


def build_fixture(case_dir: Path, parent: Path, reviewer: str) -> Path:
    """Build the case repository under ``parent`` and return its path.

    review-pr rows get base/ committed on ``main`` and head/ committed on
    ``case``. dastardly rows get ``main`` checked out with head/ as uncommitted
    changes; new files are marked intent-to-add so ``git diff HEAD``, the
    default /code-review scope, shows them.
    """
    repo = parent / repo_dir_name(case_dir.name)
    repo.mkdir()
    _git(repo, "init", "-q", "-b", BASE_BRANCH)
    _copy_tree(case_dir / "base", repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _apply_head(case_dir, repo)
    if reviewer == DASTARDLY:
        _git(repo, "add", "-N", ".")
        return repo
    _git(repo, "checkout", "-q", "-b", HEAD_BRANCH)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "case")
    _git(repo, "checkout", "-q", BASE_BRANCH)
    return repo


def data_home(env: Mapping[str, str]) -> Path:
    # Matches the shell ${XDG_DATA_HOME:-$HOME/.local/share}: empty means unset.
    value = env.get("XDG_DATA_HOME") or ""
    return Path(value) if value else Path(env.get("HOME", str(Path.home()))) / ".local" / "share"


def report_path(env: Mapping[str, str], repo: Path, day: datetime.date) -> Path:
    """Where review-pr local mode saves its report (assistants/skills/review-pr/SKILL.md, Safety)."""
    short_head = _git(repo, "rev-parse", HEAD_BRANCH)[:12]
    return data_home(env) / "agent-reports" / repo.name / f"{day.isoformat()}-review-pr-local-{short_head}.md"


def summary_path(env: Mapping[str, str], day: datetime.date) -> Path:
    return data_home(env) / "agent-reports" / "dotfiles" / f"{day.isoformat()}-eval-reviews.md"


def _events(stream: str) -> list[dict]:
    events = []
    for line in stream.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _content_blocks(event: dict) -> list:
    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def agent_report(stream: str, subagent_type: str) -> str | None:
    """Return the text the last top-level ``subagent_type`` Agent call returned.

    /code-review relays dastardly's report in its own words, which may drop
    the finding and verdict lines the scorer reads, so dastardly rows score
    the Agent tool_result instead of the session's final result. Events with
    a ``parent_tool_use_id`` belong to a subagent and are skipped.
    """
    ids = set()
    text = None
    for event in _events(stream):
        if event.get("parent_tool_use_id"):
            continue
        for block in _content_blocks(event):
            if block.get("type") == "tool_use" and block.get("name") == "Agent":
                if (block.get("input") or {}).get("subagent_type") == subagent_type:
                    ids.add(block.get("id"))
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in ids and not block.get("is_error"):
                content = block.get("content")
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    text = "\n".join(
                        part["text"] for part in content if isinstance(part, dict) and isinstance(part.get("text"), str)
                    )
    return text


def run_trial(
    case,
    case_dir: Path,
    row: Row,
    args: argparse.Namespace,
    execute: Executor,
    env: Mapping[str, str],
    today: Callable[[], datetime.date],
) -> RowResult:
    # The shim directory is separate from the fixture parent so the reviewer
    # does not find it next to the repository; both go when the row ends.
    with tempfile.TemporaryDirectory(prefix="review-eval-") as tmp, tempfile.TemporaryDirectory(prefix="review-eval-gh-") as gh_tmp:
        shim_dir = Path(gh_tmp)
        log = install_shims(shim_dir)
        gh_config_dir = shim_dir / "config"
        gh_config_dir.mkdir()
        repo = build_fixture(case_dir, Path(tmp), row.reviewer)
        command = build_command(row, repo, args.max_turns, args.max_budget_usd)
        days = [today()]
        reports = []
        if row.reviewer == REVIEW_PR:
            reports = [report_path(env, repo, days[0])]
            # A report left by an earlier trial must not be scored as this one.
            reports[0].unlink(missing_ok=True)
        try:
            stream = execute(command, repo, row_env(env, shim_dir, gh_config_dir))
        except OSError as exc:
            return RowResult(0.0, error=f"cannot run claude: {exc}")
        if row.reviewer == DASTARDLY:
            text = agent_report(stream, DASTARDLY)
            if text is None:
                return RowResult(0.0, error="stream has no dastardly Agent result")
        else:
            # The model dates the report; a run across midnight uses the later day.
            end = today()
            if end != days[0]:
                reports.append(report_path(env, repo, end))
            found = [p for p in reports if p.is_file()]
            if not found:
                return RowResult(0.0, error=f"no report at {reports[-1]}")
            text = found[-1].read_text(encoding="utf-8")
        calls = log.read_text(encoding="utf-8").splitlines()
        return score_output(case, row.reviewer, text, calls, row.two_model)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the review evals. Every row is a paid live model call.")
    parser.add_argument("--trials", type=int, default=1, help="runs per row; the mean gates min_score")
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS)
    parser.add_argument("--max-budget-usd", type=float, default=DEFAULT_MAX_BUDGET_USD)
    parser.add_argument("--case", action="append", help="case name; repeat for more (default: all)")
    parser.add_argument("--row", action="append", choices=ROW_NAMES, help="row name; repeat for more (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="print the commands without running them")
    args = parser.parse_args(argv)
    if args.trials < 1:
        parser.error("--trials must be at least 1")
    return args


def _summary(day: datetime.date, args: argparse.Namespace, lines: list[tuple[str, str, str, str, list[str]]], rate: float) -> str:
    out = [
        f"# Review evals {day.isoformat()}",
        "",
        f"Trials: {args.trials}. Max turns: {args.max_turns}. Max budget (USD): {args.max_budget_usd:g}.",
        f"Pass rate: {rate:.2f} (minimum {DEFAULT_MIN_PASS_RATE:.2f}).",
        "",
        "| Case | Row | Score | Result |",
        "| --- | --- | --- | --- |",
    ]
    out += [f"| {c} | {r} | {s} | {res} |" for c, r, s, res, _ in lines]
    notes = [(c, r, reasons) for c, r, _, _, reasons in lines if reasons]
    if notes:
        out += ["", "## Reasons", ""]
        for c, r, reasons in notes:
            out += [f"- {c} {r}: {reason}" for reason in reasons]
    return "\n".join(out) + "\n"


def main(
    argv: list[str] | None = None,
    execute: Executor = subprocess_executor,
    env: Mapping[str, str] | None = None,
    today: Callable[[], datetime.date] = datetime.date.today,
    cases_dir: Path = CASES_DIR,
) -> int:
    args = parse_args(argv)
    env = os.environ if env is None else env
    case_dirs = sorted(p.parent for p in cases_dir.glob("*/case.json"))
    if args.case:
        unknown = set(args.case) - {d.name for d in case_dirs}
        if unknown:
            print(f"unknown case: {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        case_dirs = [d for d in case_dirs if d.name in args.case]
    rows = [row for row in ROWS if not args.row or row.name in args.row]

    if args.dry_run:
        for case_dir in case_dirs:
            for row in rows:
                repo = Path("<fixture-parent>") / repo_dir_name(case_dir.name)
                command = build_command(row, repo, args.max_turns, args.max_budget_usd)
                print(f"{case_dir.name} {row.name}: (cd {repo} && {shlex.join(command)})")
        return 0

    day = today()
    pattern_error = False
    passed = []
    lines = []
    for case_dir in case_dirs:
        try:
            case = load_case(case_dir / "case.json")
        except CaseError as exc:
            pattern_error = True
            for row in rows:
                print(f"{case_dir.name} {row.name} ERROR")
                lines.append((case_dir.name, row.name, "ERROR", "error", [str(exc)]))
            continue
        for row in rows:
            trials = [run_trial(case, case_dir, row, args, execute, env, today) for _ in range(args.trials)]
            result = trial_mean(trials)
            ok = row_passed(case, result)
            passed.append(ok)
            shown = "ERROR" if result.is_error else f"{result.score:.2f}"
            print(f"{case_dir.name} {row.name} {shown}")
            reasons = [result.error] if result.is_error else result.reasons
            lines.append((case_dir.name, row.name, shown, "pass" if ok else "fail", reasons))

    rate = sum(passed) / len(passed) if passed else 0.0
    path = summary_path(env, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_summary(day, args, lines, rate), encoding="utf-8")
    print(f"summary: {path}")
    if pattern_error:
        return 2
    if not all(passed) or not suite_passed(passed):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
