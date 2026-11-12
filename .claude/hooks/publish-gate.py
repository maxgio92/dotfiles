#!/usr/bin/env python3
"""Claude Code PermissionRequest hook: trust one session until its grant expires.

A grant written by ``claude-grant`` tells this hook to answer ``allow`` to
every permission prompt in that session, except prompts that match an
exception. Every other session, and every exception, gets no decision, so
the prompt appears as before.

Exceptions live in ``${XDG_CONFIG_HOME:-~/.config}/claude-grant/exceptions``,
one per line; ``#`` starts a comment:

* ``bash REGEX``: a Bash prompt whose command matches REGEX anywhere
  (Python ``re.search``);
* ``tool GLOB``: a prompt for a tool whose name matches GLOB (``fnmatch``);
* ``path DIR``: a prompt from any tool whose path-like input (``file_path``,
  ``path``, ``notebook_path``, ``destination`` and so on) is at or below DIR,
  both resolved with realpath. ``~`` expands. A built-in file tool with no
  path is excepted.

Before approving a Bash prompt that pushes, the hook also reads the push
and mirror config of the payload ``cwd`` and refuses when it would force.

CORE always applies: questions to the user, plan approval, and anything
touching Claude config, the exceptions file or the grants. File tools also
never get approval inside any ``.claude`` or ``.git`` directory. The file
replaces only DEFAULTS, which apply when it is missing. A file that cannot
be read, or with a line that does not parse, makes every prompt an
exception, so a broken config costs prompts, never approvals. A grant pins
the file's sha256 (or "defaults"); when the file changes during a grant,
the grant stops approving until the user grants again.

An approved prompt skips the auto-mode classifier for the whole call, so
during a grant anything in the session that would have prompted runs
unreviewed unless an exception matches. Calls that never prompt, such as
most ``git commit`` calls, still go through the classifier. Deny rules
still win over this hook. Subagents share their parent's ``session_id``,
so a grant covers the whole agent tree of that session; ``/clear`` starts
a new session id and drops it.

Grants live in ``${XDG_STATE_HOME:-~/.local/state}/claude-publish-grants/
<session_id>.json`` as ``{"granted_at": <unix>, "expires_at": <unix>,
"exceptions": <pin>}``.
This is a convenience boundary, not a security boundary: the CORE shell
rule matches text, so a disguised command bundled with a prompting one can
still write a grant file. Only a separate OS user would close that.

The hook never exits 2 and prints nothing on any error.
"""

import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import time

MAX_GRANT = 8 * 3600
SESSION_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")
FILE_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
# File tools never get approval inside a directory with one of these names:
# project Claude settings and git internals such as hooks.
GUARDED_DIRS = {".claude", ".git"}
# tool_input keys whose value names a file or directory, on any tool.
PUSH_RE = re.compile(r"\bgit\b[^\n;&|]*\bpush\b")
PATH_KEY_RE = re.compile(r"(path|file|dir|directory|destination|target)s?$", re.IGNORECASE)

# Always applied, whatever the exceptions file says, so a grant can never
# widen itself or answer the user's questions.
CORE = r"""
# Shell access to Claude config, the exceptions file and the grants.
bash \.claude\b|claude-grant|claude-publish-grants|\.git/hooks
# Questions and plan approval belong to the user.
tool AskUserQuestion
tool ExitPlanMode
# File tools on Claude config; load_rules adds the exceptions and grant
# directories from the same XDG variables the hook reads.
path ~/.claude
path ~/.dotfiles/.claude
path ~/.dotfiles/bin/claude-grant
path ~/.local/bin/claude-grant
"""

# Applied when the exceptions file is missing; the file replaces these.
DEFAULTS = r"""
# Force pushes in the same command segment: --force, -f (alone or bundled),
# +refspec (quoted or not), --mirror, --prune, and the abbreviations git
# accepts for them. --force-with-lease passes.
bash \bgit\b[^\n;&|]*\bpush\b[^\n;&|]*(\s--fo(r|rc|rce)?(\s|=|$)|\s-[a-zA-Z]*f[a-zA-Z]*(\s|$)|\s['"]?\+[^\s]|\s--mi(r|rr|rro|rror)?(\s|=|$)|\s--pr(u|un|une)?(\s|=|$))
# Branch or tag deletion: --delete, -d, :dst.
bash \bgit\b[^\n;&|]*\bpush\b[^\n;&|]*(\s--de(l|le|let|lete)?(\s|=|$)|\s-[a-zA-Z]*d[a-zA-Z]*(\s|$)|\s['"]?:[^\s])
# Push config that turns a plain push into a force push: git config, git -c,
# --config-env, and GIT_CONFIG_* environment variables.
bash \bgit\b[^\n;&|]*\bconfig\b[^\n;&|]*(push|mirror)
bash \bgit\b[^\n;&|]*\s(-c|--config-env)(\s|=)
bash \bGIT_CONFIG
bash \bgit\b[^\n;&|]*\bremote\b[^\n;&|]*--mirror
bash \.git/config\b
# Raw GitHub API writes; gh-api-gate asks only for writes, reads never prompt.
bash \bgh\s+api\b
# Slack speaks for the user as a person.
tool mcp__plugin_slack_slack__slack_send_message
tool mcp__plugin_slack_slack__*canvas*
"""


class ConfigError(Exception):
    pass


def grant_dir():
    state = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(state, "claude-publish-grants")


def exceptions_file():
    config = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(config, "claude-grant", "exceptions")


def exceptions_pin():
    """Return the pin claude-grant records for the current exceptions file.

    "defaults" when the file is missing, else the sha256 of its bytes; None
    when it cannot be read.
    """
    try:
        with open(exceptions_file(), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except FileNotFoundError:
        return "defaults"
    except OSError:
        return None


def grant_expiry(session_id, now):
    """Return expires_at of a valid grant for SESSION_ID, else None.

    The grant must carry the exceptions pin it was made with, and the file
    must still match it, so an edit during the grant stops approvals.
    """
    if not isinstance(session_id, str) or not SESSION_RE.match(session_id):
        return None
    try:
        with open(os.path.join(grant_dir(), session_id + ".json")) as f:
            grant = json.load(f)
        granted, expires, pin = grant["granted_at"], grant["expires_at"], grant["exceptions"]
    except Exception:  # noqa: BLE001 - missing or malformed means no grant
        return None
    if not isinstance(pin, str) or pin != exceptions_pin():
        return None
    for value in (granted, expires):
        if type(value) is not int:
            return None
    if not granted <= now < expires or expires - granted > MAX_GRANT:
        return None
    return expires


def parse(text):
    """Return a list of (kind, matcher) from exception TEXT; raise ConfigError."""
    rules = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        kind, _, value = line.partition(" ")
        value = value.strip()
        if not value:
            raise ConfigError(line)
        if kind == "bash":
            try:
                rules.append((kind, re.compile(value)))
            except re.error as exc:
                raise ConfigError(line) from exc
        elif kind == "tool":
            rules.append((kind, value))
        elif kind == "path":
            rules.append((kind, os.path.realpath(os.path.expanduser(value))))
        else:
            raise ConfigError(line)
    return rules


def load_rules():
    """Return CORE plus the exceptions file, or CORE plus DEFAULTS without one."""
    path = exceptions_file()
    try:
        with open(path) as f:
            text = f.read()
    except FileNotFoundError:
        text = DEFAULTS
    except OSError as exc:
        raise ConfigError(path) from exc
    own = [("path", os.path.realpath(os.path.dirname(exceptions_file()))),
           ("path", os.path.realpath(grant_dir()))]
    return parse(CORE) + own + parse(text)


def config_forces(cwd):
    """True unless the repository at CWD provably has no forcing push config.

    A remote.<name>.push refspec starting with + or :, or a mirror remote,
    turns a plain push into a force push or a deletion. Reading config runs
    no program. Any error counts as forcing.
    """
    if not isinstance(cwd, str) or not os.path.isabs(cwd):
        return True
    try:
        res = subprocess.run(
            ["git", "-C", cwd, "config", "-z", "--get-regexp", r"^remote\..*\.(push|mirror)$"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:  # noqa: BLE001 - no answer means refuse
        return True
    if res.returncode == 1 and not res.stdout:
        return False
    if res.returncode != 0:
        return True
    for record in res.stdout.split("\0"):
        if not record:
            continue
        name, sep, value = record.partition("\n")
        value = value.strip() if sep else "true"
        if name.endswith(".mirror") and value.lower() not in ("false", "no", "off", "0"):
            return True
        if name.endswith(".push") and value.startswith(("+", ":")):
            return True
    return False


def excepted(payload, rules):
    """True when the prompt in PAYLOAD matches an exception, or cannot be checked."""
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool, str) or not isinstance(tool_input, dict):
        return True
    command = tool_input.get("command") if tool == "Bash" else None
    if isinstance(command, str) and PUSH_RE.search(command) and config_forces(payload.get("cwd")):
        return True  # the repository's own config would force the push
    for kind, matcher in rules:
        if kind == "tool" and fnmatch.fnmatchcase(tool, matcher):
            return True
        if kind == "bash" and tool == "Bash":
            command = tool_input.get("command")
            if not isinstance(command, str) or matcher.search(command):
                return True
        if kind == "path":
            targets = [v for k, v in tool_input.items() if PATH_KEY_RE.search(k)]
            if tool in FILE_TOOLS and not targets:
                return True
            for target in targets:
                if not isinstance(target, str) or path_excepted(target, matcher, payload):
                    return True
    return False


def path_excepted(target, matcher, payload):
    """True when TARGET resolves at or below MATCHER, inside a guarded dir, or cannot resolve."""
    target = os.path.expanduser(target)
    if not os.path.isabs(target):
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not os.path.isabs(cwd):
            return True
        target = os.path.join(cwd, target)
    real = os.path.realpath(target)
    if GUARDED_DIRS & set(real.split(os.sep)[:-1]):
        return True
    return os.path.commonpath([real, matcher]) == matcher


def main():
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict) or payload.get("hook_event_name") != "PermissionRequest":
            return 0
        expires = grant_expiry(payload.get("session_id"), int(time.time()))
        if expires is None or excepted(payload, load_rules()):
            return 0
        until = time.strftime("%H:%M", time.localtime(expires))
        out = {
            "systemMessage": "publish-gate: approved by grant until %s" % until,
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {"behavior": "allow"},
            },
        }
    except Exception:  # noqa: BLE001 - no decision is the safe failure
        return 0
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
