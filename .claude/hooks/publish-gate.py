#!/usr/bin/env python3
"""Claude Code hook: let one session publish without prompts until a grant expires.

The ``git push`` and ``gh pr``/``gh issue`` ask rules in settings stay in
place. Claude Code evaluates them before any hook, so every other session
keeps prompting. This hook answers those prompts for a session that holds a
grant written by ``claude-grant``:

* ``PermissionRequest`` (Bash): when the session has an unexpired grant and
  the command passes the allowlist below with at least one publish or commit
  segment, it returns ``allow``.
* ``PreToolUse`` (Bash): commits do not prompt, so no ask rule covers them,
  but the auto-mode classifier can block one. With a grant, a command made
  only of ``git add``, ``git status``, ``cd`` and at least one ``git commit``
  gets ``allow``. It never approves ``git push`` or ``gh`` here.

What a grant approves, as ``&&``-joined segments that each match SPECS
exactly (listed flags only, no abbreviations, no unknown options):

* publish: ``git push`` (``-q`` allowed; ``--force-with-lease`` only as
  ``git push --force-with-lease REMOTE SRC:refs/heads/BRANCH`` where BRANCH
  is not HEAD, main, master or the remote's default branch, read locally
  or with ``git ls-remote``; no --force, no +refspec, no branch deletion,
  and refused when the repository config has a push refspec starting
  with + or : or a mirror remote; an explicit remote must be a name and must not exist as a path
  relative to the payload ``cwd``, since git treats a word that is not a
  configured remote as a URL or path and runs that repository's hooks),
  ``gh pr create|merge|comment|review|edit|ready|close|reopen`` and
  ``gh issue create|comment|edit|close|reopen``, which take a PR or issue
  number only (a URL would reach another repository);
* commit: ``git commit``;
* ``cd`` must name an absolute, normalised directory (a relative one goes
  through CDPATH, and ``..`` resolves differently in bash); the hook follows it and checks later segments against that
  directory. By default a grant covers any directory, including a
  repository the agent set up with its own hooks. ``claude-grant --root
  DIR`` limits publish and commit to directories under DIR, checked
  against the worktree and git directory as well;
* around them: ``cd``, ``git add|status|rev-parse|log|show``,
  ``gh pr view|checks|list|status|diff`` and ``gh issue|run view|list``.
  ``git push`` also runs the client ``pre-push`` hook.

Anything else gets no decision and prompts as before. The raw command is
refused before tokenising when it holds a control character (newline, NUL,
carriage return and so on), a backslash or any of ``$ ` { } * ? [ ] ~ < > ! #``,
or an empty quoted string. Those are the characters where bash and shlex
disagree. A message or body that needs one of them goes through a file:
use ``git commit -F file`` and ``gh ... --body-file file``.

An allowed command skips the auto-mode classifier, so during a grant nothing
checks what gets published: a secret pushed to a public repository goes
out unreviewed. ``-F``/``--file``/``--body-file`` must resolve, symlinks
followed, to a file below ``/tmp`` outside any ``.git``, so a granted agent
cannot publish an arbitrary local file such as a key or a ``.env``. The
file is also refused when it holds a private key or a common token format. Publish
commands take no ``--repo``/``-R``, so they act on the repository of the
current directory.
The allowlist closes command-line vectors only. Programs configured in the
repository still run: ``git commit`` runs repository hooks, ``git add`` runs
clean filters, ``git status`` and ``git add`` run ``core.fsmonitor``, ``git show`` runs
textconv drivers, and ``git push``
honours ``remote.*.receivepack`` and ``core.sshCommand``.

In every other case the hook prints nothing, which leaves the normal flow:
the ask rule prompts, the classifier decides. A missing or broken hook
therefore fails closed. The hook never exits 2.

Grants live in ``${XDG_STATE_HOME:-~/.local/state}/claude-publish-grants/
<session_id>.json`` as ``{"granted_at": <unix>, "expires_at": <unix>}``.
Subagents share their parent's ``session_id``, so a grant covers the whole
agent tree of that session. ``/clear`` starts a new session id and drops it.

This is a convenience boundary, not a security boundary. Deny rules keep the
agent from running ``claude-grant`` or editing the grant directory with its
file tools, but a script the agent runs can still write a grant file.
"""

import json
import os
import re
import shlex
import stat
import subprocess
import sys
import time

MAX_GRANT = 8 * 3600
SESSION_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")
# Characters where bash expands, splits or redirects differently from shlex.
# shlex also splits on \r, \v and \f, which bash keeps inside a word.
FORBIDDEN = set("\\$`{}*?[]~<>!#\x7f") | {chr(c) for c in range(0x20) if c != 0x09}
# shlex punctuation_chars; with < and > forbidden, only these remain.
OPERATOR_CHARS = set("();|&")
REMOTE_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*$")
# Flags whose value names a local file that gets published.
FILE_FLAGS = {"-F", "--file", "--body-file"}
# A body or message file larger than this, or holding a secret, is refused.
MAX_FILE = 1 << 20
SECRET_RE = re.compile(
    rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"
    rb"|\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}"
    rb"|\bgithub_pat_[A-Za-z0-9_]{22,}"
    rb"|\bglpat-[A-Za-z0-9_-]{20}"
    rb"|\bAKIA[0-9A-Z]{16}\b"
    rb"|\bxox[abposr]-[A-Za-z0-9-]{10,}"
    rb"|\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}"
)

# Flag kinds: BOOL takes no value; VALUE takes the next token (even one that
# starts with '-', as git parse-options and pflag do) or an attached one;
# OPTIONAL takes a value only after '=' and never the next token.
BOOL, VALUE, OPTIONAL = "bool", "value", "optional"
# Positional limits; MANY (None) means no limit.
NONE, ONE, MANY = 0, 1, None


def spec(positionals, **flags):
    """Build a spec; each keyword maps a kind to its space-separated spellings."""
    table = {}
    for kind, names in flags.items():
        for name in names.split():
            table[name] = kind
    return table, positionals


def gh(positionals, **flags):
    return spec(positionals, **flags)


def gh_read(positionals, **flags):
    """A gh read; only reads take --repo, so a grant publishes to the cwd's repository."""
    flags["value"] = (flags.get("value", "") + " --repo -R").strip()
    return spec(positionals, **flags)


READ = dict(value="--json")
PUBLISH = {
    ("git", "push"): spec(MANY, bool="-u --set-upstream --tags --dry-run -n -q --quiet",
                          optional="--force-with-lease"),
    ("gh", "pr", "create"): gh(NONE, value="--title -t --body-file -F --base -B --head -H"
                               " --label -l --reviewer -r --assignee -a", bool="--draft -d --fill"),
    ("gh", "pr", "merge"): gh(ONE, value="--subject -t --body-file -F",
                              bool="--squash -s --merge -m --rebase -r --auto --delete-branch -d"),
    ("gh", "pr", "comment"): gh(ONE, value="--body-file -F"),
    ("gh", "pr", "review"): gh(ONE, value="--body-file -F",
                               bool="--approve -a --comment -c --request-changes -r"),
    ("gh", "pr", "edit"): gh(ONE, value="--title -t --body-file -F --add-label --remove-label"
                             " --add-reviewer --base -B"),
    ("gh", "pr", "ready"): gh(ONE),
    ("gh", "pr", "close"): gh(ONE, bool="--delete-branch -d"),
    ("gh", "pr", "reopen"): gh(ONE),
    ("gh", "issue", "create"): gh(NONE, value="--title -t --body-file -F --label -l --assignee -a"),
    ("gh", "issue", "comment"): gh(ONE, value="--body-file -F"),
    ("gh", "issue", "edit"): gh(ONE, value="--title -t --body-file -F --add-label --remove-label"),
    ("gh", "issue", "close"): gh(ONE, value="--reason -r"),
    ("gh", "issue", "reopen"): gh(ONE),
}
COMMIT = {
    # -am is the one bundle agents write often; it takes the message.
    ("git", "commit"): spec(NONE, value="-m --message -F --file -am",
                            bool="-a --all --amend --no-edit -s --signoff"),
}
LOCAL = {
    ("cd",): spec(ONE),
    ("git", "add"): spec(MANY, bool="-A --all -u --update"),
    ("git", "status"): spec(MANY, bool="-s --short"),
}
HISTORY = spec(MANY, bool="--oneline --stat --name-only", value="-n")
READS = {
    ("git", "rev-parse"): spec(MANY, bool="--show-toplevel", optional="--abbrev-ref --short"),
    # No git diff: a path outside the work tree makes it switch to --no-index
    # and print any local file.
    ("git", "log"): HISTORY, ("git", "show"): HISTORY,
    ("gh", "pr", "view"): gh_read(ONE, **READ), ("gh", "pr", "checks"): gh_read(ONE, **READ),
    ("gh", "pr", "list"): gh_read(NONE, **READ), ("gh", "pr", "status"): gh_read(NONE, **READ),
    ("gh", "pr", "diff"): gh_read(ONE, bool="--name-only"),
    ("gh", "issue", "view"): gh_read(ONE, **READ), ("gh", "issue", "list"): gh_read(NONE, **READ),
    ("gh", "run", "view"): gh_read(ONE, **READ), ("gh", "run", "list"): gh_read(NONE, **READ),
}

def grant_dir():
    state = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(state, "claude-publish-grants")


def grant_info(session_id, now):
    """Return (expires_at, roots) of a valid grant for SESSION_ID, else None.

    ROOTS is None when the grant covers every directory, else the list of
    resolved directories a publish or commit must run under.
    """
    if not isinstance(session_id, str) or not SESSION_RE.match(session_id):
        return None
    try:
        with open(os.path.join(grant_dir(), session_id + ".json")) as f:
            grant = json.load(f)
        granted, expires = grant["granted_at"], grant["expires_at"]
        roots = grant.get("roots")
    except Exception:  # noqa: BLE001 - missing or malformed means no grant
        return None
    for value in (granted, expires):
        if type(value) is not int:
            return None
    if not granted <= now < expires or expires - granted > MAX_GRANT:
        return None
    if roots is not None:
        if not isinstance(roots, list) or not roots:
            return None
        if not all(isinstance(r, str) and os.path.isabs(r) for r in roots):
            return None
        roots = [os.path.realpath(r) for r in roots]
    return expires, roots


def under(path, roots):
    """True when ROOTS is None or PATH is one of ROOTS or below one."""
    return roots is None or any(os.path.commonpath([path, r]) == r for r in roots)


def repo_under(base, roots):
    """True when ROOTS is None, or BASE and the repository git uses there are under ROOTS.

    git walks up from BASE and follows a ``.git`` file, so the worktree top
    level and the common git directory are checked as well as BASE.
    """
    if roots is None:
        return True
    out = git_out(base, "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-common-dir")
    if out is None:
        return False
    paths = [base] + [os.path.realpath(p) for p in out.splitlines() if p]
    return len(paths) == 3 and all(under(p, roots) for p in paths)


def segments(command):
    """Split COMMAND on && into argv lists, or None when it is outside the grammar."""
    if any(c in FORBIDDEN for c in command):
        return None
    # Backslash and $ are forbidden, so quotes only toggle. Count the unquoted
    # && operators: a quoted '&&' lexes to the same token as the operator.
    quote, operators, i = None, 0, 0
    while i < len(command):
        c = command[i]
        if quote:
            if c == quote:
                quote = None
        elif c in "'\"":
            if command[i + 1:i + 2] == c:
                return None  # empty quoted string: shlex drops '' glued to a flag
            quote = c
        elif c in OPERATOR_CHARS:
            j = i
            while j < len(command) and command[j] in OPERATOR_CHARS:
                j += 1
            if command[i:j] != "&&":
                return None
            operators += 1
            i = j
            continue
        i += 1
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    if tokens.count("&&") != operators:
        return None
    result, current = [], []
    for tok in tokens + ["&&"]:
        if tok == "&&":
            if not current:
                return None
            result.append(current)
            current = []
        else:
            current.append(tok)
    return result


def lookup(argv, specs):
    """Return (key, spec) for the longest key that equals argv's leading words."""
    for n in (3, 2, 1):
        key = tuple(argv[:n])
        if key in specs:
            return key, specs[key]
    return None, None


def safe_file(path, base):
    """True when PATH, resolved against BASE, is a file below /tmp outside any .git.

    A message or body file is published as-is with no classifier check, so
    it must not name an arbitrary local file such as a key, a ``.env`` or a
    ``.git/config`` that holds a token. BASE is the directory the segment
    runs in, or None when it is unknown. realpath follows symlinks, so a link to a key is refused.
    The file must exist, be a regular file of at most MAX_FILE bytes, and
    hold nothing that SECRET_RE matches, so a key copied into /tmp is
    refused too. This catches common formats only; it is not a secret scanner.
    """
    if not path or base is None:
        return False
    real = os.path.realpath(os.path.join(base, path))
    root = os.path.realpath("/tmp")
    if real == root or os.path.commonpath([real, root]) != root:
        return False
    if ".git" in real.split(os.sep):
        return False
    try:
        fd = os.open(real, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return False
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE:
            return False
        with os.fdopen(fd, "rb") as f:
            fd = None
            data = f.read(MAX_FILE + 1)
    finally:
        if fd is not None:
            os.close(fd)
    return len(data) <= MAX_FILE and not SECRET_RE.search(data)


def conforms(argv, key, entry, base):
    """True when argv after KEY uses only the flags and positionals ENTRY allows.

    BASE is the directory file flags resolve against, or None when unknown.
    """
    flags, limit = entry
    args, positionals, i = argv[len(key):], [], 0
    while i < len(args):
        tok = args[i]
        i += 1
        if tok.startswith("--"):
            name, eq, value = tok.partition("=")
            kind = flags.get(name)
            if kind is None or (kind == BOOL and eq):
                return False
            if kind == VALUE and not eq:
                if i == len(args):
                    return False
                i += 1
            if name in FILE_FLAGS and not safe_file(value if eq else args[i - 1], base):
                return False
        elif tok.startswith("-") and len(tok) > 1:
            kind = flags.get(tok) or flags.get(tok[:2])
            if kind is None or kind == OPTIONAL:
                return False
            if kind == BOOL and tok not in flags:
                return False  # bundled short flags such as -nv
            if kind == VALUE and tok[2:3] == "=":
                return False  # pflag strips the = and git keeps it
            if kind == VALUE and tok in flags:
                if i == len(args):
                    return False
                i += 1
            if tok[:2] in FILE_FLAGS and not safe_file(args[i - 1] if tok in flags else tok[2:], base):
                return False
        else:
            if not tok or tok.startswith("-"):
                return False
            if key in PUBLISH and key[0] == "gh" and not tok.isdigit():
                return False  # a URL or owner/repo#N would reach another repository
            positionals.append(tok)
    if limit is not None and len(positionals) > limit:
        return False
    if key == ("git", "push"):
        if positionals and not REMOTE_RE.match(positionals[0]):
            return False
        if any(p.startswith(("+", ":")) for p in positionals):
            return False  # +refspec force-pushes; :dst deletes a branch
    return True


def config_forces(cwd):
    """True unless the repository at CWD has no push config that force-pushes.

    A remote.<name>.push refspec that starts with + or :, or a
    remote.<name>.mirror, turns a plain ``git push`` into a force push or a
    branch deletion. Reading config runs no program. Any error counts as
    forcing, so a miss costs a prompt.
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
        return False  # no such keys
    if res.returncode != 0:
        return True
    # With -z each record is KEY, a newline, VALUE, then NUL; a key with no
    # value (a bare boolean) has no newline. Remote names may hold spaces.
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


def push_args(argv):
    """Return (remote, refspecs, lease) for a conforming git push ARGV."""
    positionals = [a for a in argv[2:] if not a.startswith("-")]
    lease = any(a == "--force-with-lease" or a.startswith("--force-with-lease=") for a in argv[2:])
    return (positionals[0] if positionals else None), positionals[1:], lease


BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def git_out(base, *args, timeout=5):
    """Return stdout of ``git -C BASE ARGS`` on success, else None."""
    try:
        res = subprocess.run(["git", "-C", base, *args], capture_output=True, text=True, timeout=timeout)
    except Exception:  # noqa: BLE001 - no answer
        return None
    return res.stdout if res.returncode == 0 else None


def default_branch(base, remote):
    """Return the default branch of REMOTE for the repository at BASE, or None.

    The local refs/remotes/REMOTE/HEAD symref is read in full (``--short``
    can shorten it ambiguously). Without it the remote is asked with
    ``git ls-remote --symref``. None means unknown, and the caller refuses.
    """
    prefix = "refs/remotes/%s/" % remote
    out = git_out(base, "symbolic-ref", "--quiet", prefix + "HEAD")
    if out and out.strip().startswith(prefix):
        return out.strip()[len(prefix):]
    out = git_out(base, "ls-remote", "--symref", remote, "HEAD", timeout=7)
    for line in (out or "").splitlines():
        # ref: refs/heads/main<TAB>HEAD
        head, _, name = line.partition("\t")
        if name == "HEAD" and head.startswith("ref: refs/heads/"):
            return head[len("ref: refs/heads/"):]
    return None


def unsafe_lease(argv, base):
    """True when git push ARGV is a lease push the hook cannot prove safe.

    git resolves short destinations (``heads/main``), ``@`` and
    ``remote.<name>.push`` mappings on its own, so a lease push must spell
    every refspec as ``<src>:refs/heads/<name>``. NAME must be a plain
    branch name other than HEAD, main, master or the remote's default
    branch (case-insensitive). ``--tags`` with a lease, any configured
    ``remote.*.push``, and an unknown default branch are refused.
    """
    remote, refspecs, lease = push_args(argv)
    if not lease:
        return False
    if remote is None or not refspecs or "--tags" in argv:
        return True
    if git_out(base, "config", "-z", "--get-regexp", r"^remote\..*\.push$") is not None:
        return True  # a push mapping exists (exit 1 with no output means none)
    default = default_branch(base, remote)
    if default is None:
        return True
    protected = {"head", "main", "master", default.casefold()}
    for refspec in refspecs:
        src, colon, dst = refspec.partition(":")
        if not colon or not src or src == "@" or not dst.startswith("refs/heads/"):
            return True
        name = dst[len("refs/heads/"):]
        if (not BRANCH_RE.match(name) or name.endswith((".lock", "/", ".")) or ".." in name
                or "//" in name or name.casefold() in protected):
            return True
    return False


def local_remote(argv, base):
    """True when git push ARGV names a remote that git could open as a local path.

    git tries NAME and NAME.git (enter_repo also tries the /.git forms, which
    imply one of these exists). git resolves the name from the worktree root,
    which is BASE or one of its ancestors, so every ancestor is checked.
    """
    remote = push_args(argv)[0]
    if remote is None:
        return False
    d = base
    while True:
        if any(os.path.lexists(os.path.join(d, remote + s)) for s in ("", ".git")):
            return True
        parent = os.path.dirname(d)
        if parent == d:
            return False
        d = parent


def approved(command, wanted, others, cwd=None, roots=None):
    """True when every segment conforms to WANTED or OTHERS and one to WANTED.

    The hook follows each ``cd`` to an absolute directory, so later segments
    are checked against the directory they run in. A publish or commit must
    run under one of ROOTS when the grant lists any.
    """
    argvs = segments(command)
    if not argvs:
        return False
    hit = False
    base = os.path.realpath(cwd) if isinstance(cwd, str) and os.path.isabs(cwd) else None
    for argv in argvs:
        key, entry = lookup(argv, wanted)
        if key:
            hit = True
        else:
            key, entry = lookup(argv, others)
        if not key or not conforms(argv, key, entry, base):
            return False
        if base is None:
            return False
        if key == ("cd",):
            # Absolute only: bash looks a relative target up in CDPATH.
            # bash resolves . and .. by text before the kernel follows
            # symlinks, so only a normalised path means the same place to both.
            target = argv[1] if len(argv) == 2 else ""
            if not target.startswith("/") or os.path.normpath(target) != target:
                return False
            base = os.path.realpath(target)
            if not os.path.isdir(base):
                return False
            continue
        if (key in PUBLISH or key in COMMIT) and not repo_under(base, roots):
            return False
        if key == ("git", "push") and (
                local_remote(argv, base) or config_forces(base) or unsafe_lease(argv, base)):
            return False
    return hit


def main():
    try:
        payload = json.load(sys.stdin)
        event = payload.get("hook_event_name")
        command = payload.get("tool_input", {}).get("command", "")
        if payload.get("tool_name") != "Bash" or not isinstance(command, str):
            return 0
        now = int(time.time())
        info = grant_info(payload.get("session_id"), now)
        if info is None:
            return 0
        expires, roots = info
        until = time.strftime("%H:%M", time.localtime(expires))
        if event == "PermissionRequest" and approved(command, {**PUBLISH, **COMMIT}, {**LOCAL, **READS},
                                                     payload.get("cwd"), roots):
            out = {
                "systemMessage": "publish-gate: approved by grant until %s" % until,
                "hookSpecificOutput": {
                    "hookEventName": "PermissionRequest",
                    "decision": {"behavior": "allow"},
                },
            }
        elif event == "PreToolUse" and approved(command, COMMIT, LOCAL, payload.get("cwd"), roots):
            out = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "publish-gate: git commit allowed by grant until %s" % until,
                }
            }
        else:
            return 0
    except Exception:  # noqa: BLE001 - no decision is the safe failure
        return 0
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
