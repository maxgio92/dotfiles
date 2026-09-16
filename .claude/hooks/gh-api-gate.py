#!/usr/bin/env python3
"""Claude Code PreToolUse hook: prompt on a visible ``gh api`` write.

Settings ask rules run before hook decisions, so a ``Bash(gh api:*)`` row
prompts on every read. This hook replaces that row. It returns ``ask`` only
when a ``gh api`` call in the command carries a write signal:

* a method other than GET (``-X``, ``--method``, attached or separate);
* a request field (``-f``, ``-F``, ``--field``, ``--raw-field``), except a
  GraphQL ``query=`` or variable field whose document has no mutation;
* ``--input``;
* a GraphQL document containing ``mutation`` or ``subscription``.

Anything else, reads included, gets no decision, so the auto-mode
classifier and the remaining rules judge the command as they do for any
other Bash call. The hook never returns ``allow`` and never exits 2.
"""

import json
import re
import shlex
import sys

GH_API_RE = re.compile(r"(?<![\w-])gh\s+api(?![\w-])")
OPERATORS = set(";&|<>()\n")
FIELD_FLAGS = ("-f", "-F", "--field", "--raw-field")
GRAPHQL_WRITE_RE = re.compile(r"\bmutation\b|\bsubscription\b")


def tokens_of(command):
    """Shell words with quotes removed; whitespace split when shlex fails."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        return command.split()


def calls(tokens):
    """Yield the argv after each ``gh api``, up to the next shell operator."""
    for i in range(len(tokens) - 1):
        if tokens[i] == "gh" and tokens[i + 1] == "api":
            argv = []
            for tok in tokens[i + 2:]:
                if tok and set(tok) <= OPERATORS:
                    break
                argv.append(tok)
            yield argv
    # A quoted script (bash -c 'gh api ...') is one token; scan its words.
    for tok in tokens:
        if GH_API_RE.search(tok):
            inner = tok.split()
            for j in range(len(inner) - 1):
                if inner[j] == "gh" and inner[j + 1] == "api":
                    yield inner[j + 2:]


def write_signal(argv):
    """Return why ``gh api ARGV`` writes, or None."""
    endpoint = None
    fields = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok in ("-X", "--method"):
            method = argv[i + 1] if i + 1 < len(argv) else ""
            if method.upper() != "GET":
                return "method %s" % (method or "missing")
            i += 2
            continue
        if tok.startswith("--method="):
            if tok[9:].upper() != "GET":
                return "method %s" % tok[9:]
        elif tok.startswith("-X") and len(tok) > 2:
            if tok[2:].lstrip("=").upper() != "GET":
                return "method %s" % tok[2:].lstrip("=")
        elif tok == "--input" or tok.startswith("--input="):
            return "--input sends a request body"
        elif tok in FIELD_FLAGS:
            fields.append(argv[i + 1] if i + 1 < len(argv) else "")
            i += 2
            continue
        elif tok.startswith(("--field=", "--raw-field=")):
            fields.append(tok.split("=", 1)[1])
        elif tok[:2] in ("-f", "-F") and len(tok) > 2:
            fields.append(tok[2:].lstrip("="))
        elif not tok.startswith("-") and endpoint is None:
            endpoint = tok
        i += 1
    if fields:
        if endpoint != "graphql":
            return "request field on %s" % (endpoint or "unknown endpoint")
        for field in fields:
            if GRAPHQL_WRITE_RE.search(field):
                return "GraphQL mutation"
    return None


def main():
    try:
        payload = json.load(sys.stdin)
        command = payload.get("tool_input", {}).get("command", "")
    except Exception:  # noqa: BLE001 - unreadable input is not a gh api call
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    if not isinstance(command, str) or not GH_API_RE.search(command):
        return 0
    try:
        reason = None
        for argv in calls(tokens_of(command)):
            reason = write_signal(argv)
            if reason:
                break
    except Exception as exc:  # noqa: BLE001 - never crash the tool call
        reason = "could not parse the command (%s)" % exc.__class__.__name__
    if reason:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": "gh-api-gate: gh api write: %s" % reason,
                }
            },
            sys.stdout,
        )
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
