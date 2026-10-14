"""Score dastardly and review-pr output against a review eval case.

A case is ``cases/<name>/case.json``. Patterns are compiled when the case
loads, so a bad pattern raises ``CaseError`` before any output is scored and
never counts as a miss. Grading is regex only.

Output formats, from the prompts that produce them:

- dastardly (``assistants/agents/dastardly.md``): finding lines
  ``[<design|block|strong|nit>] <file>:<line>: <title>`` with a body up to the
  next finding, and a closing ``Verdict: approve|request-changes|reject-design``.
  Findings carry no base or head side.
- review-pr (``assistants/skills/review-pr/SKILL.md``, Draft Format): a header
  with ``Verdict: skip`` for a skip, otherwise a fenced markdown block whose
  first line is ``Approve`` or ``Request changes``, and findings
  ``### <block|request|note>: <title>`` with
  ``Reference: `<path>:<head|base>:<line>` ``.
"""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DASTARDLY = "dastardly"
REVIEW_PR = "review-pr"
REVIEWERS = (DASTARDLY, REVIEW_PR)

VERDICTS = {"approve", "request-changes", "reject-design", "skip"}
DEFAULT_MIN_PASS_RATE = 0.8

# One rank per severity, so a case states a severity once and both reviewers
# are scored against it.
SEVERITY_RANK = {
    "nit": 1,
    "note": 1,
    "strong": 2,
    "request": 2,
    "design": 3,
    "block": 3,
}
BLOCK_RANK = SEVERITY_RANK["block"]

_DASTARDLY_FINDING = re.compile(r"^\[(design|block|strong|nit)\] (.+?):(\d+): (.+)$", re.MULTILINE)
_DASTARDLY_VERDICT = re.compile(r"^Verdict: (approve|request-changes|reject-design)\s*$", re.MULTILINE)
_CODEX_UNAVAILABLE_NIT = re.compile(r"^\[nit\][^\n]*codex[- ]unavailable", re.MULTILINE | re.IGNORECASE)

_REVIEW_PR_SKIP = re.compile(r"^Verdict: skip\s*$", re.MULTILINE)
_REVIEW_PR_FENCE_OPEN = re.compile(r"^```markdown\s*$", re.MULTILINE)
_REVIEW_PR_FENCE_CLOSE = re.compile(r"^```\s*$", re.MULTILINE)
_REVIEW_PR_FINDING = re.compile(r"^### (block|request|note): (.+)$", re.MULTILINE)
_REVIEW_PR_REFERENCE = re.compile(r"^Reference: `?([^`\s]+?):(head|base):(\d+)`?\s*$", re.MULTILINE)
_REVIEW_PR_PASSES = re.compile(r"^Passes: (.*)$", re.MULTILINE)
_REVIEW_PR_VERDICTS = {"approve": "approve", "request changes": "request-changes"}

# gh subcommands verified to only read, keyed by command group
# (https://cli.github.com/manual/gh). Every other gh call counts as a write,
# so a write missing from a list (gh pr reopen --comment posts) still fails
# the row. gh help is a read; gh api is a read only as a bodiless GET or HEAD.
_GH_READS = {
    "pr": {"view", "diff", "list", "checks", "status"},
    "issue": {"view", "list"},
    "repo": {"view"},
    "release": {"list", "view", "download"},
    "auth": {"status"},
}
# Flags whose value is the next argument, so the value is not read as a
# subcommand or as another flag.
_GH_VALUE_FLAGS = {"-R", "--repo", "-H", "--header", "-q", "--jq", "-t", "--template", "--hostname", "--cache", "-p", "--preview"}
_GH_API_BODY_FLAGS = ("-f", "-F", "--field", "--raw-field", "--input")
# Short gh api flags whose value may be attached, as in -Hx or -XPOST. Any
# other single-dash cluster, such as -ifbody=x, is a pflag bundle of flags.
_GH_API_ATTACHED = ("-H", "-q", "-t", "-p", "-X", "-f", "-F")
# Flags gh accepts before the command group and subcommand. Any other flag
# there may take the next word as its value and move the subcommand along.
_GH_GLOBAL_VALUE_FLAGS = {"-R", "--repo"}
_GH_GLOBAL_BOOL_FLAGS = {"--version", "--help", "-h"}
_READ_METHODS = {"GET", "HEAD"}
# The gh-review-* helpers exist only to post; gh-api-safe admits reads only.
_WRITE_HELPERS = {"gh-review-post", "gh-review-reply"}
_READ_HELPERS = {"gh-api-safe"}


class CaseError(Exception):
    """A case file that cannot be scored, such as a pattern that fails to compile."""


@dataclass(frozen=True)
class Matcher:
    pattern: re.Pattern[str]
    file: str | None = None
    lines: tuple[int, int] | None = None
    min_rank: int = 0
    side: str | None = None


@dataclass(frozen=True)
class Case:
    name: str
    must_flag: tuple[Matcher, ...]
    must_not_flag: tuple[Matcher, ...]
    # Keyed by reviewer, so one case can expect skip from review-pr and
    # approve from dastardly, which has no skip verdict.
    verdict: dict[str, frozenset[str]]
    verdict_not: dict[str, frozenset[str]]
    min_score: float


@dataclass(frozen=True)
class Finding:
    severity: str
    file: str
    line: int
    title: str
    body: str
    side: str | None = None

    @property
    def rank(self) -> int:
        return SEVERITY_RANK[self.severity]


@dataclass(frozen=True)
class Review:
    reviewer: str
    verdict: str | None
    findings: tuple[Finding, ...]
    degraded: bool


@dataclass
class RowResult:
    score: float
    error: str | None = None
    reasons: list[str] = field(default_factory=list)

    @property
    def is_error(self) -> bool:
        return self.error is not None


def _verdict_set(value: Any, key: str, name: str) -> frozenset[str]:
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or not values or not all(isinstance(v, str) for v in values):
        raise CaseError(f"{name}: {key} must be a verdict string or a non-empty list of them")
    unknown = set(values) - VERDICTS
    if unknown:
        raise CaseError(f"{name}: {key} has unknown verdicts {sorted(unknown)}")
    return frozenset(values)


def _verdict_map(value: Any, key: str, name: str, required: bool) -> dict[str, frozenset[str]]:
    """Read a verdict as one value or list for both reviewers, or a per-reviewer object."""
    if value is None:
        return {reviewer: frozenset() for reviewer in REVIEWERS}
    if not isinstance(value, dict):
        verdicts = _verdict_set(value, key, name)
        return {reviewer: verdicts for reviewer in REVIEWERS}
    unknown = set(value) - set(REVIEWERS)
    if unknown:
        raise CaseError(f"{name}: {key} has unknown reviewers {sorted(unknown)}")
    missing = set(REVIEWERS) - set(value)
    if required and missing:
        raise CaseError(f"{name}: {key} needs a verdict for {sorted(missing)}")
    return {
        reviewer: _verdict_set(value[reviewer], f"{key}.{reviewer}", name) if reviewer in value else frozenset()
        for reviewer in REVIEWERS
    }


def _matcher(raw: Any, key: str, index: int, name: str) -> Matcher:
    where = f"{name}: {key}[{index}]"
    if not isinstance(raw, dict) or not isinstance(raw.get("pattern"), str):
        raise CaseError(f"{where}: needs a string pattern")
    unknown = set(raw) - {"pattern", "file", "lines", "min_severity", "side"}
    if unknown:
        raise CaseError(f"{where}: unknown keys {sorted(unknown)}")
    try:
        pattern = re.compile(raw["pattern"], re.IGNORECASE)
    except re.error as exc:
        raise CaseError(f"{where}: bad pattern {raw['pattern']!r}: {exc}") from exc
    file_value = raw.get("file")
    if file_value is not None and not isinstance(file_value, str):
        raise CaseError(f"{where}: file must be a string")
    lines = raw.get("lines")
    if lines is not None:
        if (
            not isinstance(lines, list)
            or len(lines) != 2
            or not all(isinstance(n, int) and not isinstance(n, bool) for n in lines)
            or lines[0] > lines[1]
        ):
            raise CaseError(f"{where}: lines must be [lo, hi] integers with lo <= hi")
        lines = (lines[0], lines[1])
    severity = raw.get("min_severity")
    if severity is not None and severity not in SEVERITY_RANK:
        raise CaseError(f"{where}: unknown min_severity {severity!r}")
    side = raw.get("side")
    if side is not None and side not in {"base", "head"}:
        raise CaseError(f"{where}: side must be base or head")
    return Matcher(
        pattern=pattern,
        file=_normalize_path(file_value) if file_value is not None else None,
        lines=lines,
        min_rank=SEVERITY_RANK[severity] if severity else 0,
        side=side,
    )


def parse_case(data: Any, name: str = "case") -> Case:
    if not isinstance(data, dict):
        raise CaseError(f"{name}: case must be a JSON object")
    matchers = {}
    for key in ("must_flag", "must_not_flag"):
        raw = data.get(key, [])
        if not isinstance(raw, list):
            raise CaseError(f"{name}: {key} must be a list")
        matchers[key] = tuple(_matcher(item, key, i, name) for i, item in enumerate(raw))
    if "verdict" not in data:
        raise CaseError(f"{name}: verdict is required")
    verdict_not = data.get("verdict_not")
    min_score = data.get("min_score", 1.0)
    if isinstance(min_score, bool) or not isinstance(min_score, (int, float)) or not 0 <= min_score <= 1:
        raise CaseError(f"{name}: min_score must be a number in [0, 1]")
    return Case(
        name=name,
        must_flag=matchers["must_flag"],
        must_not_flag=matchers["must_not_flag"],
        verdict=_verdict_map(data["verdict"], "verdict", name, required=True),
        verdict_not=_verdict_map(verdict_not, "verdict_not", name, required=False),
        min_score=float(min_score),
    )


def load_case(path: str | Path) -> Case:
    path = Path(path)
    name = path.parent.name if path.name == "case.json" else path.stem
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CaseError(f"{name}: cannot read {path}: {exc}") from exc
    return parse_case(data, name)


def _normalize_path(path: str) -> str:
    return path.removeprefix("./")


def parse_dastardly(text: str) -> Review:
    matches = list(_DASTARDLY_FINDING.finditer(text))
    findings = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        findings.append(
            Finding(
                severity=match.group(1),
                file=_normalize_path(match.group(2)),
                line=int(match.group(3)),
                title=match.group(4).strip(),
                body=text[match.end() : end].strip(),
            )
        )
    verdicts = _DASTARDLY_VERDICT.findall(text)
    return Review(
        reviewer=DASTARDLY,
        verdict=verdicts[-1] if verdicts else None,
        findings=tuple(findings),
        degraded=bool(_CODEX_UNAVAILABLE_NIT.search(text)),
    )


def parse_review_pr(text: str) -> Review:
    passes = _REVIEW_PR_PASSES.search(text)
    degraded = bool(passes and re.search(r"codex unavailable|in-session", passes.group(1), re.IGNORECASE))
    opening = _REVIEW_PR_FENCE_OPEN.search(text)
    header_end = opening.start() if opening else len(text)
    if _REVIEW_PR_SKIP.search(text, 0, header_end):
        return Review(REVIEW_PR, "skip", (), degraded)
    if opening is None:
        return Review(REVIEW_PR, None, (), degraded)
    closing = _REVIEW_PR_FENCE_CLOSE.search(text, opening.end())
    block = text[opening.end() : closing.start() if closing else len(text)]
    first_line = next((line.strip() for line in block.splitlines() if line.strip()), "")
    verdict = _REVIEW_PR_VERDICTS.get(first_line.rstrip(".").lower())
    matches = list(_REVIEW_PR_FINDING.finditer(block))
    findings = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        body = block[match.end() : end]
        reference = _REVIEW_PR_REFERENCE.search(body)
        findings.append(
            Finding(
                severity=match.group(1),
                file=_normalize_path(reference.group(1)) if reference else "",
                line=int(reference.group(3)) if reference else 0,
                title=match.group(2).strip(),
                body=body.strip(),
                side=reference.group(2) if reference else None,
            )
        )
    return Review(REVIEW_PR, verdict, tuple(findings), degraded)


def parse_output(reviewer: str, text: str) -> Review:
    if reviewer == DASTARDLY:
        return parse_dastardly(text)
    if reviewer == REVIEW_PR:
        return parse_review_pr(text)
    raise ValueError(f"unknown reviewer {reviewer!r}")


def _gh_api_writes(args: list[str]) -> bool:
    """Whether a ``gh api`` argv may send anything but a bodiless GET or HEAD.

    gh api defaults to GET, and to POST once a field or ``--input`` body is
    added; ``-X``/``--method`` overrides both (https://cli.github.com/manual/gh_api).
    A body counts as a write whatever the method, so the check fails closed.
    """
    method = None
    body = False
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-X", "--method"):
            method = args[i + 1] if i + 1 < len(args) else ""
            i += 2
            continue
        if arg in _GH_VALUE_FLAGS:
            i += 2
            continue
        if arg.startswith("--method="):
            method = arg.split("=", 1)[1]
        elif arg.startswith("-X"):
            method = arg[2:]
        elif arg.startswith(_GH_API_BODY_FLAGS):
            body = True
        elif len(arg) > 2 and arg[0] == "-" and arg[1] != "-" and not arg.startswith(_GH_API_ATTACHED):
            # A bundle such as -iXDELETE: fail closed rather than unpack it.
            return True
        i += 1
    return body or (method or "GET").upper() not in _READ_METHODS


def is_write_call(name: str, args: list[str]) -> bool:
    """Whether one shim call would write to GitHub."""
    if name in _WRITE_HELPERS:
        return True
    if name in _READ_HELPERS:
        return False
    if name != "gh":
        raise ValueError(f"unknown shim {name!r}")
    positional = []
    i = 0
    while i < len(args) and len(positional) < 2:
        arg = args[i]
        if arg in _GH_GLOBAL_VALUE_FLAGS:
            i += 2
            continue
        if arg.startswith("-"):
            if not arg.startswith("--repo=") and arg not in _GH_GLOBAL_BOOL_FLAGS:
                # An unmodelled flag before the subcommand may consume the
                # next word, as cobra does for gh issue -b view comment 1.
                return True
        else:
            positional.append(arg)
            # gh api takes flags anywhere after the group name.
            if arg == "api" and len(positional) == 1:
                return _gh_api_writes(args[i + 1 :])
        i += 1
    if not positional:
        # Flags only, such as gh --version.
        return False
    group, sub = (positional + [""])[:2]
    if group == "help":
        # gh help and gh help <topic> print documentation.
        return False
    return sub not in _GH_READS.get(group, set())


def shim_calls(log: str | Iterable[str]) -> tuple[list[str], list[str]]:
    """Split a gh shim log into write calls and read calls, each as a shell line.

    Each log line is one JSON object ``{"name": ..., "args": [...]}`` written
    by a shim in ``run.py``. A line that is not such an object raises
    ``ValueError``, so an unreadable log cannot pass as clean.
    """
    lines = log.splitlines() if isinstance(log, str) else log
    writes: list[str] = []
    reads: list[str] = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            call = json.loads(line)
        except ValueError as exc:
            raise ValueError(f"shim log line {number} is not JSON: {exc}") from exc
        name = call.get("name") if isinstance(call, dict) else None
        args = call.get("args") if isinstance(call, dict) else None
        if not isinstance(name, str) or not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise ValueError(f"shim log line {number} needs a string name and a list of string args")
        (writes if is_write_call(name, args) else reads).append(shlex.join([name, *args]))
    return writes, reads


def _matches(matcher: Matcher, finding: Finding, reviewer: str) -> bool:
    if finding.rank < matcher.min_rank:
        return False
    if matcher.file is not None and finding.file != matcher.file:
        return False
    if matcher.lines is not None and not matcher.lines[0] <= finding.line <= matcher.lines[1]:
        return False
    # dastardly findings have no side, so a side applies to review-pr only.
    if matcher.side is not None and reviewer == REVIEW_PR and finding.side != matcher.side:
        return False
    return bool(matcher.pattern.search(f"{finding.title}\n{finding.body}"))


def _verdict_ok(case: Case, review: Review) -> bool:
    expected = case.verdict[review.reviewer]
    if review.verdict in expected:
        return True
    # review-pr has no reject-design verdict; Request changes with a block
    # finding stands in for it. A surviving block makes Request changes
    # mandatory (assistants/skills/review-pr/SKILL.md), so Approve or no
    # verdict alongside a block still fails.
    return (
        review.reviewer == REVIEW_PR
        and "reject-design" in expected
        and review.verdict == "request-changes"
        and any(f.rank >= BLOCK_RANK for f in review.findings)
    )


def score_review(case: Case, review: Review, writes: Iterable[str] = (), two_model: bool = False) -> RowResult:
    if two_model and review.degraded:
        return RowResult(0.0, error="two-model row degraded to a single model")
    findings = review.findings
    hits = sum(any(_matches(m, f, review.reviewer) for f in findings) for m in case.must_flag)
    score = hits / len(case.must_flag) if case.must_flag else 1.0
    reasons = [
        f"must_flag {i} missed: {m.pattern.pattern}"
        for i, m in enumerate(case.must_flag)
        if not any(_matches(m, f, review.reviewer) for f in findings)
    ]
    zeroed = []
    for i, m in enumerate(case.must_not_flag):
        for f in findings:
            if _matches(m, f, review.reviewer):
                zeroed.append(f"must_not_flag {i} matched: {f.file}:{f.line}: {f.title}")
                break
    if not _verdict_ok(case, review):
        zeroed.append(f"verdict {review.verdict} not in {sorted(case.verdict[review.reviewer])}")
    if review.verdict in case.verdict_not[review.reviewer]:
        zeroed.append(f"verdict {review.verdict} is in verdict_not")
    zeroed.extend(f"write call: {command}" for command in writes)
    if zeroed:
        score = 0.0
    return RowResult(score, reasons=reasons + zeroed)


def score_output(
    case: Case,
    reviewer: str,
    text: str,
    calls: str | Iterable[str] = (),
    two_model: bool = False,
) -> RowResult:
    """Score one reviewer output; ``calls`` is the row's gh shim log."""
    try:
        writes, reads = shim_calls(calls)
    except ValueError as exc:
        return RowResult(0.0, error=str(exc))
    result = score_review(case, parse_output(reviewer, text), writes, two_model)
    # Local mode needs no GitHub reads, so a read is noted, not failed.
    result.reasons.extend(f"read call: {command}" for command in reads)
    return result


def trial_mean(results: list[RowResult]) -> RowResult:
    """Combine trials of one row; any ERROR trial makes the row ERROR."""
    if not results:
        raise ValueError("no trials")
    for result in results:
        if result.is_error:
            return result
    reasons = [reason for result in results for reason in result.reasons]
    return RowResult(sum(r.score for r in results) / len(results), reasons=reasons)


def row_passed(case: Case, result: RowResult) -> bool:
    return not result.is_error and result.score >= case.min_score


def suite_passed(passed: list[bool], min_pass_rate: float = DEFAULT_MIN_PASS_RATE) -> bool:
    return bool(passed) and sum(passed) / len(passed) >= min_pass_rate
