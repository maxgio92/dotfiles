"""Detection and Bash side-effect scanning, moved as-is from scanner.py.

This module holds the prose detection and Bash scan logic byte-identical to
its original home in ``scanner.py``. No detection rule changes here; this is a
relocation only. The ``Config`` type lives in ``core.config``.
"""

from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.config import Config


BODY_FLAGS = {
    "--body",
    "-b",
    "--message",
    "-m",
    "--notes",
    "-n",
    "--title",
    "-t",
}
BODY_FILE_FLAGS = {
    "--body-file",
    "--notes-file",
}
API_FIELD_FLAGS = {
    "-f",
    "-F",
    "--field",
    "--raw-field",
}
API_BODY_KEYS = {
    "body",
    "comment",
    "message",
    "note",
    "notes",
    "text",
    "title",
}
POST_COMMANDS = {
    ("issue", "create"),
    ("issue", "edit"),
    ("issue", "comment"),
    ("pr", "create"),
    ("pr", "edit"),
    ("pr", "comment"),
    ("pr", "review"),
    ("release", "create"),
    ("release", "edit"),
}
# Leading tokens that can post to GitHub. gh-review-reply wraps the review
# thread reply endpoint and takes its body only via --body-file.
GH_POST_COMMANDS = {
    "gh",
    "gh-api-safe",
    "gh-review-reply",
}
REDIRECT_HEREDOC_COMMANDS = {
    "cat",
    "tee",
}
PROSE_SUFFIXES = {
    ".md",
    ".markdown",
    ".txt",
    ".adoc",
    ".rst",
}
PROSE_NAME_PARTS = {
    "body",
    "comment",
    "issue",
    "message",
    "pr",
    "release",
    "review",
}
DYNAMIC_MARKERS = ("$(", "${", "`", "<(")


def read_text_file(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    except UnicodeDecodeError:
        return None


def strip_fenced_code_blocks(text: str) -> str:
    output: list[str] = []
    in_fence = False
    fence_char = ""
    fence_len = 0

    for line in text.splitlines(keepends=True):
        if not in_fence:
            match = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})", line)
            if match:
                fence = match.group(1)
                in_fence = True
                fence_char = fence[0]
                fence_len = len(fence)
                continue
            output.append(line)
            continue

        close_pattern = r"^[ \t]{0,3}" + re.escape(fence_char) + "{" + str(fence_len) + r",}[ \t]*$"
        if re.match(close_pattern, line.rstrip("\n\r")):
            in_fence = False
            fence_char = ""
            fence_len = 0

    return "".join(output)


def strip_outer_fence(text: str) -> str:
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return text.strip()

    opening = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})(?:[A-Za-z0-9_-]+)?[ \t]*$", lines[0])
    if not opening:
        return text.strip()

    fence = opening.group(1)
    closing = re.match(
        r"^[ \t]{0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}[ \t]*$",
        lines[-1],
    )
    if not closing:
        return text.strip()

    return "\n".join(lines[1:-1]).strip()


def strip_blockquote_markers(text: str) -> str:
    lines = text.strip().splitlines()
    nonempty = [line for line in lines if line.strip()]
    if not nonempty or not all(line.lstrip().startswith(">") for line in nonempty):
        return text.strip()

    output: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith(">"):
            stripped = stripped[1:]
            if stripped.startswith(" "):
                stripped = stripped[1:]
        output.append(stripped)
    return "\n".join(output).strip()


def strip_disclosure_heading(text: str) -> str:
    stripped = text.strip()
    for heading in ("Communication Rules:", "## Communication Rules"):
        if stripped == heading:
            return ""
        prefix = heading + "\n"
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return stripped


def canonical_disclosure_body(text: str) -> str:
    return strip_disclosure_heading(strip_blockquote_markers(strip_outer_fence(text)))


def is_canonical_rules_disclosure(text: str, config: Config) -> bool:
    return canonical_disclosure_body(text) == config.rules_text.strip()


def blocked_codepoint_chars(policy: dict) -> list[str]:
    chars: list[str] = []
    for item in policy.get("blockedCodepoints", []):
        if not isinstance(item, dict):
            continue
        codepoint = item.get("codepoint")
        if not isinstance(codepoint, str) or not codepoint.upper().startswith("U+"):
            continue
        try:
            chars.append(chr(int(codepoint[2:], 16)))
        except ValueError:
            continue
    return chars


def term_pattern(term: str) -> re.Pattern[str] | None:
    parts = term.strip().split()
    if not parts:
        return None
    body = r"\s+".join(re.escape(part) for part in parts)
    return re.compile(r"(?<![A-Za-z0-9_])" + body + r"(?![A-Za-z0-9_])", re.IGNORECASE)


def term_patterns(policy: dict) -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    for term in policy.get("hardGateBannedTerms", []):
        if not isinstance(term, str):
            continue
        pattern = term_pattern(term)
        if pattern is not None:
            patterns.append(pattern)
    return patterns


def scan_prose(text: str, config: Config, strip_fences: bool) -> bool:
    if is_canonical_rules_disclosure(text, config):
        return False

    inspected = strip_fenced_code_blocks(text) if strip_fences else text
    for char in blocked_codepoint_chars(config.policy):
        if char in inspected:
            return True
    for pattern in term_patterns(config.policy):
        if pattern.search(inspected):
            return True
    return False


def command_text_from_args(parts: list[str]) -> str:
    if parts:
        return " ".join(parts)
    return sys.stdin.read()


def parse_command_line(line: str) -> list[str] | None:
    try:
        return shlex.split(line, posix=True)
    except ValueError:
        return None


def split_command_segments(argv: list[str]) -> list[list[str]]:
    # Split a parsed argv on sequential shell control operators so each chained
    # command is scanned in isolation. shlex.split keeps these operators as
    # standalone tokens, so a single line such as "gh ... && echo ... > notes.md"
    # yields a segment per command and the second command's redirect is no longer
    # hidden. A pipe "|" is deliberately not a split operator: it is a data
    # conduit, not a command boundary, so prose piped into "tee" or a redirect
    # must stay in one segment for the redirect collector to see the sink.
    segments: list[list[str]] = []
    current: list[str] = []
    for token in argv:
        if token in {"&&", "||", ";", "&"}:
            if current:
                segments.append(current)
            current = []
            continue
        current.append(token)
    if current:
        segments.append(current)
    return segments


def command_name(argv: list[str]) -> str:
    if not argv:
        return ""
    return Path(argv[0]).name


# A leading shell env assignment such as ``GH_TOKEN=x`` or ``FOO=bar`` precedes
# the real command. ``shlex.split`` keeps it as its own token, so every
# command-name check would otherwise see the assignment rather than the command
# and miss a wrapped post or write. We strip these leading assignments only;
# a ``key=value`` token AFTER the command is a genuine argument and stays.
_ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def strip_env_assignments(argv: list[str]) -> list[str]:
    """Return argv with any leading shell env assignments removed.

    Drops leading tokens that match a shell env assignment (``NAME=value``)
    until the first token that is not an assignment, which is the real command.
    Tokens after that command are returned untouched, even if they look like
    assignments. An argv that is all assignments returns an empty list.
    """
    index = 0
    while index < len(argv) and _ENV_ASSIGNMENT.match(argv[index]):
        index += 1
    return argv[index:]


def patch_added_text(patch: str) -> str:
    """Return the added text of an apply_patch body, the ``+`` lines only.

    Strips the leading ``+`` from each added line and skips the ``+++`` file
    headers and the ``*** ...`` patch markers, which do not start with a single
    ``+``. A patch with no added lines (a delete-only patch) returns an empty
    string. This is the text a patch would write to disk, the only part a prose
    scan should see.
    """
    lines: list[str] = []
    for line in patch.splitlines():
        if not line.startswith("+"):
            continue
        if line == "+++" or line.startswith("+++ ") or line.startswith("+++\t"):
            continue
        lines.append(line[1:])
    return "\n".join(lines)


# Shell wrappers whose ``-c`` flag carries an inner script as a single token. A
# command such as ``bash -lc "printf 'x' > out.md"`` hides its redirect, prose,
# and any gh post inside one argv token, so detection must unwrap it and scan
# the inner script in its own right.
SHELL_WRAPPER_NAMES = {"sh", "bash", "zsh", "dash", "ash", "ksh"}

# A bound on wrapper recursion, so a pathological chain of nested wrappers cannot
# drive unbounded recursion. Three levels is far beyond any genuine use.
SHELL_WRAPPER_DEPTH_CAP = 3


def shell_c_inner_script(argv: list[str]) -> str | None:
    """Return the inner script of a shell ``-c`` invocation, else None.

    Recognises the shell names in ``SHELL_WRAPPER_NAMES`` via ``command_name``.
    The ``-c`` flag is recognised both bare (``-c``) and bundled into a short
    option group whose letters include ``c`` (``-lc``, ``-ic``, ``-lic``). Long
    options such as ``--norc`` are skipped. The inner script is the first
    non-option token that follows the ``-c`` flag. A bare non-option token
    before any ``-c`` (for example ``bash script.sh``) means this is not a
    ``-c`` invocation, so the function returns None.
    """
    if command_name(argv) not in SHELL_WRAPPER_NAMES:
        return None
    saw_c_flag = False
    index = 1
    while index < len(argv):
        token = argv[index]
        if saw_c_flag:
            # The first non-option token after ``-c`` is the inner script.
            if token.startswith("-"):
                index += 1
                continue
            return token
        if token.startswith("--"):
            # A long option such as ``--norc``; skip it and keep scanning.
            index += 1
            continue
        if token.startswith("-") and len(token) > 1:
            # A short-option group; ``-c`` may be bundled (``-lc``, ``-lic``).
            if "c" in token[1:]:
                saw_c_flag = True
            index += 1
            continue
        # A bare non-option token before any ``-c``: this is not a ``-c``
        # invocation (for example ``bash script.sh``).
        return None
    return None


def has_dynamic_value(value: str) -> bool:
    stripped = value.strip()
    if stripped.startswith("$"):
        return True
    return any(marker in stripped for marker in DYNAMIC_MARKERS)


def option_value(argv: list[str], index: int) -> tuple[str | None, int]:
    token = argv[index]
    if "=" in token and token.startswith("--"):
        return token.split("=", 1)[1], index
    # pflag also accepts the value attached to a short flag (``-fbody=x``,
    # ``-XPOST``) or joined with ``=`` (``-X=DELETE``, ``-f=body=x``), so the
    # value is the remainder of the token with one leading ``=`` dropped.
    if token.startswith("-") and not token.startswith("--") and len(token) > 2:
        value = token[2:]
        return (value[1:] if value.startswith("=") else value), index
    if index + 1 >= len(argv):
        return None, index
    return argv[index + 1], index + 1


def read_body_file(value: str) -> tuple[str | None, bool]:
    if has_dynamic_value(value) or value == "-":
        return None, True
    text = read_text_file(value)
    if text is None:
        return None, True
    return text, False


def clean_literal_path(value: str) -> str | None:
    cleaned = value.strip("'\"")
    if not cleaned or has_dynamic_value(cleaned):
        return None
    return cleaned


def extract_heredoc_blocks(script: str) -> list[tuple[str, str]]:
    lines = script.splitlines()
    blocks: list[tuple[str, str]] = []
    index = 0
    while index < len(lines):
        command_line = lines[index]
        match = re.search(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", command_line)
        if not match:
            index += 1
            continue
        delimiter = match.group(2)
        index += 1
        body: list[str] = []
        while index < len(lines) and lines[index].strip() != delimiter:
            body.append(lines[index])
            index += 1
        if body:
            blocks.append((command_line.strip(), "\n".join(body)))
        if index < len(lines):
            index += 1
    return blocks


def heredoc_bodies_by_line(blocks: list[tuple[str, str]]) -> dict[str, list[str]]:
    bodies: dict[str, list[str]] = {}
    for line, body in blocks:
        bodies.setdefault(line, []).append(body)
    return bodies


def heredoc_body_files(blocks: list[tuple[str, str]]) -> dict[str, str]:
    files: dict[str, str] = {}
    for line, body in blocks:
        argv = parse_command_line(line)
        if argv is None or command_name(argv) not in REDIRECT_HEREDOC_COMMANDS:
            continue
        for target in redirect_targets(argv):
            cleaned = clean_literal_path(target)
            if cleaned is not None:
                files[cleaned] = body
    return files


def command_lines_without_heredoc_bodies(script: str) -> list[str]:
    lines = script.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        output.append(line)
        match = re.search(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", line)
        if not match:
            index += 1
            continue
        delimiter = match.group(2)
        index += 1
        while index < len(lines) and lines[index].strip() != delimiter:
            index += 1
        if index < len(lines):
            index += 1
    return output


def is_known_post_command(argv: list[str]) -> bool:
    if is_help_command(argv):
        return False
    name = command_name(argv)
    if name == "gh":
        if len(argv) >= 3 and (argv[1], argv[2]) in POST_COMMANDS:
            return True
        if len(argv) >= 2 and argv[1] == "api":
            return has_api_post_signal(argv[2:])
        return any(has_body_flag(argv, index) for index in range(len(argv)))
    if name == "gh-api-safe":
        return has_api_post_signal(argv[1:])
    if name == "gh-review-reply":
        return any(has_body_flag(argv, index) for index in range(len(argv)))
    return False


def is_help_command(argv: list[str]) -> bool:
    return any(token in {"-h", "--help"} for token in argv[1:])


def is_api_field_flag(token: str) -> bool:
    # The unambiguous spellings of a gh api request field: bare (``-f``,
    # ``--field``) and equals (``--field=body=x``).
    if token in API_FIELD_FLAGS:
        return True
    return token.startswith("--field=") or token.startswith("--raw-field=")


def is_attached_api_field_flag(token: str) -> bool:
    # pflag also accepts the value attached to the short flag (``-fbody=x``,
    # ``-Fbody=@file``). This spelling is only a field flag inside a ``gh api``
    # argv: elsewhere a ``-f...`` token is usually an option value such as a
    # negated search qualifier (``gh pr list --search '-flaky'``).
    return (token.startswith("-f") or token.startswith("-F")) and not token.startswith("--") and len(token) > 2


def is_api_argv(argv: list[str]) -> bool:
    name = command_name(argv)
    return name == "gh-api-safe" or (name == "gh" and len(argv) >= 2 and argv[1] == "api")


def is_api_method_flag(token: str) -> bool:
    # ``-X POST``, ``-XPOST``, ``--method POST``, ``--method=POST``.
    if token in {"-X", "--method"} or token.startswith("--method="):
        return True
    return token.startswith("-X") and len(token) > 2


def is_api_input_flag(token: str) -> bool:
    return token == "--input" or token.startswith("--input=")


def has_body_flag(argv: list[str], index: int) -> bool:
    token = argv[index]
    if token in BODY_FLAGS or token in BODY_FILE_FLAGS or is_api_field_flag(token):
        return True
    if token.startswith("--body=") or token.startswith("--message="):
        return True
    if token.startswith("--notes=") or token.startswith("--title="):
        return True
    # The ``=`` forms of the body-file flags (``--body-file=`` and
    # ``--notes-file=``) must count too, so both the surface classifier and the
    # body scanner recognise a single source of truth for these flags.
    if token.startswith("--body-file=") or token.startswith("--notes-file="):
        return True
    return False


def has_api_post_signal(argv: list[str], attached_fields: bool = True) -> bool:
    # ``attached_fields`` admits the ``-fbody=x`` spelling; pass it only for a
    # ``gh api`` argv, where a ``-f...`` token cannot be an option value.
    index = 0
    while index < len(argv):
        token = argv[index]
        if is_api_method_flag(token):
            value, index = option_value(argv, index)
            if value and value.upper() in {"POST", "PATCH", "PUT", "DELETE"}:
                return True
        elif is_api_field_flag(token) or is_api_input_flag(token):
            return True
        elif attached_fields and is_attached_api_field_flag(token):
            return True
        index += 1
    return False


def _argv_is_gh_post(argv: list[str]) -> bool:
    # Test a parsed argv for a GH_POST_COMMANDS leading token carrying a post
    # signal. The signal is judged by the SAME canonical helpers the body
    # scanner uses (``has_body_flag`` and ``has_api_post_signal``), so the
    # surface choice and the body scan can never drift on which flags count.
    if not argv or command_name(argv) not in GH_POST_COMMANDS:
        return False
    if any(has_body_flag(argv, index) for index in range(len(argv))):
        return True
    return has_api_post_signal(argv, attached_fields=is_api_argv(argv))


def is_bash_gh_post(command: Any) -> bool:
    # A Bash command is external (B2) when its first token is gh/gh-api-safe and
    # it carries a post signal. A shell ``-c`` wrapper hides the gh post inside
    # one token, so also unwrap the wrapper and test the inner script's argv: a
    # wrapped ``gh issue create --body ...`` must classify as external too.
    if not isinstance(command, str):
        return False
    # Strip a leading env assignment (``GH_TOKEN=x gh ...``) so the gh leading
    # token test sees the real command, not the assignment.
    if _argv_is_gh_post(strip_env_assignments(command.split())):
        return True
    # The wrapper unwrap needs a shell-aware parse so the quoted inner script is
    # one token; the naive split above keeps the cheap direct path unchanged.
    # A chained line (``cd repo && gh pr comment ...``) is tested per segment
    # so the leading command cannot hide the post. shlex collapses newlines and
    # ``split_command_segments`` keeps a pipe inside its segment (the redirect
    # collector needs the sink), so here each line is parsed on its own and a
    # segment is further split on ``|``: ``cat reply.md | gh pr comment 1 -F -``
    # is the common way to post a file. Operators glued to a word
    # (``true;gh ...``) stay one token under shlex and are not split.
    for line in command.splitlines():
        argv = parse_command_line(line)
        if argv is None:
            continue
        for segment in split_command_segments(argv):
            for stage in _split_on_pipe(segment):
                stage = strip_env_assignments(stage)
                if _argv_is_gh_post(stage):
                    return True
                inner = shell_c_inner_script(stage)
                if inner is not None and is_bash_gh_post(inner):
                    return True
    return False


def _split_on_pipe(argv: list[str]) -> list[list[str]]:
    stages: list[list[str]] = []
    current: list[str] = []
    for token in argv:
        if token == "|":
            if current:
                stages.append(current)
            current = []
            continue
        current.append(token)
    if current:
        stages.append(current)
    return stages


def read_post_body_file(value: str, heredoc_files: dict[str, str]) -> tuple[str | None, bool]:
    cleaned = clean_literal_path(value)
    if cleaned is None or cleaned == "-":
        return None, True
    if cleaned in heredoc_files:
        return heredoc_files[cleaned], False
    return read_body_file(cleaned)


def extract_post_texts(argv: list[str], heredoc_files: dict[str, str]) -> tuple[list[str], bool]:
    texts: list[str] = []
    unresolved = False
    api_argv = is_api_argv(argv)
    index = 0

    while index < len(argv):
        token = argv[index]

        if token in BODY_FLAGS or any(token.startswith(flag + "=") for flag in BODY_FLAGS if flag.startswith("--")):
            value, index = option_value(argv, index)
            if value is None or has_dynamic_value(value):
                unresolved = True
            else:
                texts.append(value)
        elif token in BODY_FILE_FLAGS or any(token.startswith(flag + "=") for flag in BODY_FILE_FLAGS if flag.startswith("--")):
            value, index = option_value(argv, index)
            if value is None:
                unresolved = True
            else:
                text, failed = read_post_body_file(value, heredoc_files)
                unresolved = unresolved or failed
                if text is not None:
                    texts.append(text)
        elif is_api_field_flag(token) or (api_argv and is_attached_api_field_flag(token)):
            value, index = option_value(argv, index)
            text, failed = extract_api_field_text(value, heredoc_files)
            unresolved = unresolved or failed
            if text is not None:
                texts.append(text)
        elif is_api_input_flag(token):
            value, index = option_value(argv, index)
            if value is None:
                unresolved = True
            else:
                text, failed = read_post_body_file(value, heredoc_files)
                unresolved = unresolved or failed
                if text is not None:
                    texts.append(text)

        index += 1

    return texts, unresolved


def extract_api_field_text(value: str | None, heredoc_files: dict[str, str]) -> tuple[str | None, bool]:
    if value is None or "=" not in value:
        return None, True
    key, raw_value = value.split("=", 1)
    if key not in API_BODY_KEYS:
        return None, False
    if has_dynamic_value(raw_value):
        return None, True
    if raw_value.startswith("@"):
        return read_post_body_file(raw_value[1:], heredoc_files)
    return raw_value, False


def prose_target(path_value: str) -> bool:
    cleaned = clean_literal_path(path_value)
    if cleaned is None:
        return False
    path = Path(cleaned)
    if path.suffix.lower() in PROSE_SUFFIXES:
        return True
    lowered = path.name.lower()
    return any(part in lowered for part in PROSE_NAME_PARTS)


def redirect_targets(argv: list[str]) -> list[str]:
    targets: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in {">", ">>"}:
            if index + 1 < len(argv):
                targets.append(argv[index + 1])
                index += 1
        elif token.startswith(">>") and len(token) > 2:
            targets.append(token[2:])
        elif token.startswith(">") and len(token) > 1:
            targets.append(token[1:])
        elif token == "tee":
            index += 1
            while index < len(argv) and argv[index].startswith("-"):
                index += 1
            if index < len(argv):
                targets.append(argv[index])
        index += 1
    return targets


def bash_prose_sink(command_text: str, depth: int = 0) -> str | None:
    """Return the first prose-target sink path a Bash command writes, else None.

    This is the STABLE B1 target for a Bash write, mirroring the file path a
    Write/Edit tool keys on, so two breaching Bash writes to two different prose
    files each get their own one-block budget instead of sharing one coarse
    session+tool key.

    A sink is a ``>``/``>>`` redirect target or a ``cat``/``tee`` heredoc sink
    that passes ``prose_target`` (a prose suffix or a prose-name part) and
    resolves to a literal path. The FIRST such sink wins, scanning lines top to
    bottom and, within a line, its chained command segments in order; the
    heredoc sinks on a line are considered after that line's redirect sinks.
    Returns None when no prose sink resolves: a bare command, a dynamic or
    ``$(...)`` sink, a post-command, or a non-prose target. This reads the SINK
    only; it never changes ``scan_bash``'s detection behaviour.

    A shell ``-c`` wrapper (``bash -lc "..."``) hides its sink inside one token,
    so this unwraps such a segment and recurses on the inner script, bounded by
    ``SHELL_WRAPPER_DEPTH_CAP``. The inner script keeps its own newlines, so
    heredocs inside it still resolve through the existing line machinery.
    """
    heredoc_files = heredoc_body_files(extract_heredoc_blocks(command_text))

    for line in command_lines_without_heredoc_bodies(command_text):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        argv = parse_command_line(stripped)
        if argv is None:
            continue
        for raw_segment in split_command_segments(argv):
            # Drop a leading env assignment so the wrapper check and the redirect
            # sinks resolve against the real command. The sinks sit after the
            # assignments, so the front strip keeps them; an all-assignments
            # segment has no command and is skipped.
            segment = strip_env_assignments(raw_segment)
            if not segment:
                continue
            if depth < SHELL_WRAPPER_DEPTH_CAP:
                inner = shell_c_inner_script(segment)
                if inner is not None:
                    nested = bash_prose_sink(inner, depth + 1)
                    if nested is not None:
                        return nested
                    continue
            for target in redirect_targets(segment):
                cleaned = clean_literal_path(target)
                if cleaned is not None and prose_target(cleaned):
                    return cleaned

    for cleaned in heredoc_files:
        if prose_target(cleaned):
            return cleaned

    return None


APPLY_PATCH_FILE_MARKERS = ("*** Add File:", "*** Update File:")


def apply_patch_target(patch_text: str) -> str | None:
    """Return the first file path an apply_patch body writes, else None.

    Codex's ``apply_patch`` tool carries no ``file_path`` key; the target path
    lives in the patch body behind an ``*** Add File:`` or ``*** Update File:``
    marker. This reads the FIRST such path so a breaching patch keys its B1
    strike on the target file, mirroring the Write/Edit tools, instead of
    collapsing to one coarse session+turn+tool key (under which the first patch
    blocks and every later patch lands). A delete-only or pathless patch returns
    None: the key then falls back to the coarse session+turn+tool form.
    """
    for line in patch_text.splitlines():
        stripped = line.strip()
        for marker in APPLY_PATCH_FILE_MARKERS:
            if stripped.startswith(marker):
                path = stripped[len(marker) :].strip()
                if path:
                    return path
    return None


def extract_redirect_texts(argv: list[str], heredocs: list[str]) -> tuple[list[str], bool]:
    targets = [target for target in redirect_targets(argv) if prose_target(target)]
    if not targets:
        return [], False

    command = command_name(argv)
    if command in {"echo", "printf"}:
        texts: list[str] = []
        for token in argv[1:]:
            if token in {">", ">>"} or token.startswith(">") or token.startswith("<<"):
                break
            if has_dynamic_value(token):
                return [], True
            texts.append(token)
        return ([" ".join(texts)], False) if texts else ([], True)

    if command in REDIRECT_HEREDOC_COMMANDS and "<<" in " ".join(argv) and heredocs:
        return heredocs, False

    return [], False


def scan_bash(command_text: str, config: Config, _depth: int = 0) -> bool:
    heredoc_blocks = extract_heredoc_blocks(command_text)
    heredocs_by_line = heredoc_bodies_by_line(heredoc_blocks)
    body_files = heredoc_body_files(heredoc_blocks)
    blocked = False

    for line in command_lines_without_heredoc_bodies(command_text):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        argv = parse_command_line(stripped)
        if argv is None:
            continue

        heredocs = heredocs_by_line.get(stripped, [])
        for raw_segment in split_command_segments(argv):
            # Drop a leading env assignment (``GH_TOKEN=x gh ...``) so the
            # command-name checks see the real command. The ``>``/heredoc sinks
            # sit after the assignments, so stripping the front keeps them. A
            # segment that is all assignments has no command, so skip it.
            segment = strip_env_assignments(raw_segment)
            if not segment:
                continue
            if _depth < SHELL_WRAPPER_DEPTH_CAP:
                inner = shell_c_inner_script(segment)
                if inner is not None:
                    # A shell ``-c`` wrapper hides its script in one token. Scan
                    # the inner script in its own right; the wrapper level has no
                    # direct redirect or post to process.
                    blocked = blocked or scan_bash(inner, config, _depth + 1)
                    continue

            if is_known_post_command(segment):
                texts, unresolved = extract_post_texts(segment, body_files)
                if unresolved or not texts:
                    return True
                for text in texts:
                    blocked = blocked or scan_prose(text, config, strip_fences=True)

            texts, unresolved = extract_redirect_texts(segment, heredocs)
            if unresolved:
                return True
            for text in texts:
                blocked = blocked or scan_prose(text, config, strip_fences=True)

    return blocked
