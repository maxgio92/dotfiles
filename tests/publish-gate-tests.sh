#!/usr/bin/env bash
# Tests for the publish-gate hook and the claude-grant CLI. A grant lets one
# session's publish prompts through until it expires; everything else gets no
# decision. Nothing is executed but the hook and the CLI.
# Run: bash tests/publish-gate-tests.sh

set -uo pipefail

here="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
hook="$here/../.claude/hooks/publish-gate.py"
gate="$here/../.claude/hooks/gh-api-gate.py"
cli="$here/../bin/claude-grant"

XDG_STATE_HOME="$(mktemp -d)"
export XDG_STATE_HOME
work="$(mktemp -d)"
# Body and message files must live under /tmp, whatever TMPDIR says.
tb="$(mktemp -d /tmp/publish-gate-tests.XXXXXX)"
trap 'rm -rf "$XDG_STATE_HOME" "$work" "$tb"' EXIT
for f in b.md r.md c.md msg.txt pr-body.md; do echo "plain text" >"$tb/$f"; done
grants="$XDG_STATE_HOME/claude-publish-grants"
unset CLAUDE_CODE_SESSION_ID

A=11111111-aaaa-4aaa-8aaa-111111111111
B=22222222-bbbb-4bbb-8bbb-222222222222

fails=0
pass() { echo "ok   $1"; }
fail() { echo "FAIL $1: $2"; fails=$((fails + 1)); }

# payload EVENT SESSION COMMAND [CWD]: CWD defaults to $work.
payload() {
  python3 -c 'import json,sys; print(json.dumps({"hook_event_name": sys.argv[1], "session_id": sys.argv[2], "tool_name": "Bash", "cwd": sys.argv[4], "tool_input": {"command": sys.argv[3]}}))' "$1" "$2" "$3" "${4-$work}"
}

decision() {
  python3 -c '
import json, sys
d = sys.stdin.read()
if not d.strip():
    print("none")
else:
    h = json.loads(d)["hookSpecificOutput"]
    print(h["decision"]["behavior"] if "decision" in h else h["permissionDecision"])'
}

# expect NAME EVENT SESSION WANT COMMAND [CWD]: exit 0 and WANT is allow, or none.
expect() {
  local name="$1" event="$2" sid="$3" want="$4" cmd="$5" out status got
  out="$(payload "$event" "$sid" "$cmd" "${6-$work}" | "$hook" 2>&1)"; status=$?
  [ "$status" -eq 0 ] || { fail "$name" "exit $status: $out"; return; }
  got="$(printf '%s' "$out" | decision)"
  [ "$got" = "$want" ] || { fail "$name" "decided $got, want $want: $out"; return; }
  pass "$name"
}

# write_grant SESSION GRANTED_AT EXPIRES_AT (raw JSON values)
write_grant() {
  mkdir -p "$grants"
  printf '{"granted_at": %s, "expires_at": %s}' "$2" "$3" >"$grants/$1.json"
}

now=$(date +%s)
P=PermissionRequest
T=PreToolUse

# No grant: no decision, so the ask rule prompts.
expect "no grant: git push" $P "$A" none "git push"
expect "no grant: gh pr merge" $P "$A" none "gh pr merge 1 --squash"
expect "no grant: compound push" $P "$A" none "cd x && git push"
expect "no grant: nested shell" $P "$A" none "bash -c 'git push'"
expect "no grant: git commit" $T "$A" none "git commit -m x"

write_grant "$A" "$now" "$((now + 3600))"

# Valid grant for session A: commands inside the allowlist.
expect "grant: push upstream" $P "$A" allow "git push -u origin br"
expect "grant: add commit push" $P "$A" allow "git add -A && git commit -m 'fix(scope): y' && git push"
expect "grant: scoped PR title" $P "$A" allow "gh pr create --title 'feat(x): y' --body-file $tb/b.md"
expect "grant: gh pr merge" $P "$A" allow "gh pr merge 12 --squash --delete-branch"
expect "grant: push origin HEAD" $P "$A" allow "git push origin HEAD"
expect "grant: force-with-lease" $P "$A" none "git push --force-with-lease origin br"
expect "grant: force-with-lease value" $P "$A" none "git push --force-with-lease=br origin br"
expect "grant: gh pr create flags" $P "$A" allow "gh pr create -B main -H x -t t -F $tb/b.md --draft"
expect "grant: gh pr create -R refused" $P "$A" none "gh pr create -B main -t t -F b.md -R o/r"
expect "grant: gh pr review approve" $P "$A" allow "gh pr review 3 --approve --body-file $tb/r.md"
expect "grant: body file under /tmp" $P "$A" allow "gh pr create -t t --body-file $tb/pr-body.md"
expect "grant: commit file attached" $P "$A" allow "git commit -F$tb/msg.txt"
expect "grant: abs body file refused" $P "$A" none "gh pr create -t t --body-file /etc/passwd"
expect "grant: attached abs body refused" $P "$A" none "gh pr comment 1 --body-file=/etc/passwd"
expect "grant: short abs body refused" $P "$A" none "gh issue create -t t -F/etc/passwd"
expect "grant: dotdot body refused" $P "$A" none "gh pr create -t t -F ../secret"
expect "grant: tmp escape refused" $P "$A" none "gh pr create -t t -F /tmp/../etc/passwd"
expect "grant: bare /tmp refused" $P "$A" none "gh pr create -t t -F /tmp"
expect "grant: abs commit file refused" $P "$A" none "git add -A && git commit -F /etc/passwd && git push"
expect "commit: abs file refused" $T "$A" none "git commit -F /etc/passwd"
expect "grant: cd then body file refused" $P "$A" none "cd /etc && gh pr create -t t --body-file passwd"
expect "grant: cd then commit file refused" $P "$A" none "cd /etc && git commit -F passwd && git push"
ln -s /etc/passwd "$work/linked.md"
expect "grant: symlinked body refused" $P "$A" none "gh pr create -t t --body-file linked.md"
expect "grant: symlinked commit file refused" $T "$A" none "git commit -F linked.md"
expect "grant: publish --repo refused" $P "$A" none "gh pr comment 1 -R other/repo --body-file b.md"
expect "grant: read --repo allowed" $P "$A" allow "gh pr view 1 -R o/r && gh pr merge 1 --squash"
expect "grant: -F= attached abs refused" $P "$A" none "gh pr create -t t -F=/etc/passwd"
expect "grant: -F= attached review refused" $P "$A" none "gh pr review 1 -c -F=$tb/r.md"
expect "grant: PR URL merge refused" $P "$A" none "gh pr merge https://github.com/other/repo/pull/1 --squash"
expect "grant: PR URL comment refused" $P "$A" none "gh pr comment https://github.com/other/repo/pull/1 --body-file $tb/b.md"
expect "grant: issue URL close refused" $P "$A" none "gh issue close https://github.com/other/repo/issues/1"
expect "grant: branch selector refused" $P "$A" none "gh pr merge feature-x --squash"
expect "grant: cd then gh merge refused" $P "$A" none "cd /tmp/x && gh pr merge 1 --squash"
expect "grant: bare cd then push refused" $P "$A" none "cd && git push"
expect "grant: cd then commit refused" $T "$A" none "cd x && git add -A && git commit -m x"
expect "grant: force-with-lease refspec refused" $P "$A" none "git push --force-with-lease origin HEAD:main"
expect "grant: --delete refused" $P "$A" none "git push --delete origin main"
expect "grant: :dst delete refused" $P "$A" none "git push origin :main"
expect "grant: .git/config body refused" $P "$A" none "gh pr comment 1 --body-file .git/config"
expect "grant: cwd body file refused" $P "$A" none "gh pr comment 1 --body-file notes.md"
expect "grant: /tmp .git body refused" $P "$A" none "gh pr comment 1 --body-file /tmp/r/.git/config"
expect "commit: /tmp message file" $T "$A" allow "git commit -F $tb/msg.txt"
printf -- '-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n' >"$tb/key.md"
echo "token ghp_abcdefghijklmnopqrstuvwxyz0123456789" >"$tb/tok.md"
expect "grant: private key body refused" $P "$A" none "gh pr comment 1 --body-file $tb/key.md"
expect "grant: token body refused" $P "$A" none "gh pr create -t t -F $tb/tok.md"
expect "commit: private key message refused" $T "$A" none "git commit -F $tb/key.md"
expect "grant: missing body refused" $P "$A" none "gh pr comment 1 --body-file $tb/missing.md"
mkfifo "$tb/fifo.md"
expect "grant: fifo body refused" $P "$A" none "gh pr comment 1 --body-file $tb/fifo.md"
ln -s "$tb/b.md" "$tb/link.md"
expect "grant: /tmp symlink to /tmp allowed" $P "$A" allow "gh pr comment 1 --body-file $tb/link.md"
repo="$work/cfg"; git init -q "$repo"
git -C "$repo" config remote.origin.push 'refs/heads/main:refs/heads/main'
expect "grant: plain push config allowed" $P "$A" allow "git push" "$repo"
git -C "$repo" config remote.origin.push '+refs/heads/*:refs/heads/*'
expect "grant: + push config refused" $P "$A" none "git push" "$repo"
expect "grant: + push config explicit refused" $P "$A" none "git push origin main" "$repo"
git -C "$repo" config remote.origin.push ':refs/heads/release'
expect "grant: : push config refused" $P "$A" none "git push" "$repo"
git -C "$repo" config --unset remote.origin.push
git -C "$repo" config remote.origin.mirror true
expect "grant: mirror remote refused" $P "$A" none "git push" "$repo"
git -C "$repo" config remote.origin.mirror false
expect "grant: mirror false allowed" $P "$A" allow "git push" "$repo"
git -C "$repo" config 'remote.a b.push' '+refs/heads/*:refs/heads/*'
expect "grant: + push config on spaced remote refused" $P "$A" none "git push" "$repo"
git -C "$repo" config --unset 'remote.a b.push'
printf '[remote "origin"]\n\tmirror\n' >>"$repo/.git/config"
expect "grant: bare mirror key refused" $P "$A" none "git push" "$repo"
expect "grant: relative cwd push refused" $P "$A" none "git push" "relative/dir"
expect "grant: gh issue comment" $P "$A" allow "gh issue comment 3 --body-file $tb/c.md"
expect "grant: gh issue close reason" $P "$A" allow "gh issue close 3 --reason completed"
expect "grant: read then push" $P "$A" allow "git status && git log --oneline -n 3 && git push"
expect "grant: attached short value" $P "$A" allow "git log -n5 && git push"
expect "grant: checks after create" $P "$A" allow "gh pr create -t t -F $tb/b.md && gh pr checks --json name"
expect "grant: message that looks like a flag" $P "$A" allow "git commit -m --no-verify && git push"
expect "grant: message with operators" $P "$A" allow "git commit -m 'a; b | c (d) R&D' && git push"
expect "grant: commit -am" $P "$A" allow "git commit -am 'fix: x' && git push"
expect "grant: commit -F" $P "$A" allow "git commit -F $tb/msg.txt && git push"
expect "grant: git commit PreToolUse" $T "$A" allow "git commit -m 'fix(evals): x'"
expect "grant: add then commit PreToolUse" $T "$A" allow "git add a b && git status && git commit -m x"

# Valid grant, but the command falls outside the allowlist: no decision.
expect "grant: abbreviated receive-pack" $P "$A" none "git push --recei=x origin"
expect "grant: abbreviated upload-pack" $P "$A" none "git push --upl=x origin"
expect "grant: receive-pack" $P "$A" none "git push --receive-pack=x origin"
expect "grant: ANSI-C quoted receive-pack" $P "$A" none "git push . \$'--receive-pack=x'"
expect "grant: parameter expansion" $P "$A" none "git push \"\$X\""
expect "grant: brace expansion" $P "$A" none "git push origin {a,b}"
expect "grant: log --output" $P "$A" none "git log --output=f && git push"
expect "grant: diff --ext-diff" $P "$A" none "git diff --ext-diff && git push"
expect "grant: diff outside work tree" $P "$A" none "git diff /etc/os-release /dev/null && git push"
expect "grant: gh release download" $P "$A" none "gh release download v1 -O /tmp/t"
expect "grant: gh release create" $P "$A" none "gh release create v1 --notes-file n.md"
expect "grant: force push" $P "$A" none "git push --force origin br"
expect "grant: short force push" $P "$A" none "git push -f origin br"
expect "grant: plus refspec" $P "$A" none "git push origin +main"
expect "grant: path remote" $P "$A" none "git push /tmp/repo main"
expect "grant: url remote" $P "$A" none "git push file:///tmp/repo main"
# git opens a word that is not a configured remote as a path and runs its hooks.
mkdir "$work/evil" "$work/bare.git"
expect "grant: relative path remote" $P "$A" none "git push evil HEAD:main"
expect "grant: relative path remote with .git" $P "$A" none "git push bare HEAD:main"
expect "grant: explicit remote after cd" $P "$A" none "cd evil && git push origin"
expect "grant: implicit remote after cd" $P "$A" none "cd evil && git push"
# git changes into the worktree root before resolving, so check cwd's ancestors.
mkdir "$work/sub"
out="$(payload $P "$A" "git push bare HEAD:main" "$work/sub" | "$hook")"
if [ -z "$out" ]; then pass "grant: relative path remote in ancestor"; else fail "grant: relative path remote in ancestor" "$out"; fi
out="$(payload $P "$A" "git push origin br" "" | "$hook")"
if [ -z "$out" ]; then pass "grant: explicit remote without cwd"; else fail "grant: explicit remote without cwd" "$out"; fi
expect "grant: no-verify" $P "$A" none "git commit --no-verify -m x && git push"
expect "grant: semicolon" $P "$A" none "git push; rm -rf x"
expect "grant: pipe" $P "$A" none "git push | tail -5"
expect "grant: or" $P "$A" none "git push || true"
expect "grant: background" $P "$A" none "git push & git status"
expect "grant: triple ampersand" $P "$A" none "git push &&& git status"
expect "grant: subshell" $P "$A" none "(git push)"
expect "grant: heredoc" $P "$A" none "$(printf 'git commit -F- <<EOF\nmsg\nEOF\n')"
expect "grant: here-string" $P "$A" none "git commit -F - <<< x && git push"
expect "grant: newline" $P "$A" none "$(printf 'git push\nrm -rf x')"
expect "grant: carriage return" $P "$A" none "$(printf 'git push\rorigin')"
expect "grant: vertical tab" $P "$A" none "$(printf 'git push\vorigin')"
expect "grant: backslash" $P "$A" none "git push origin\\ x"
expect "grant: unknown flag" $P "$A" none "git push --verbose"
expect "grant: abbreviated flag" $P "$A" none "git push --set-up origin br"
expect "grant: bundled booleans" $P "$A" none "git push -un origin br"
expect "grant: git fetch" $P "$A" none "git fetch && git push"
expect "grant: git -C" $P "$A" none "git -C d push"
expect "grant: git -c" $P "$A" none "git -c core.sshCommand=x push"
expect "grant: gh -R before subcommand" $P "$A" none "gh -R o/r pr create -t t -F b.md"
expect "grant: gh jq on read" $P "$A" none "gh pr view 1 --jq .x && git push"
expect "grant: gh pr comment approve" $P "$A" none "gh pr comment 1 --approve"
expect "grant: gh-review-reply" $P "$A" none "gh-review-reply u --body-file r.md"
expect "grant: trailing value flag" $P "$A" none "git commit -m && git push"
expect "grant: empty attached value" $P "$A" none "git commit -m'' x && git push"
expect "grant: empty positional" $P "$A" none "git push '' br"
expect "grant: quoted operator" $P "$A" none "git push origin '&&' git status"
expect "grant: leading operator" $P "$A" none "&& git push"
expect "grant: trailing operator" $P "$A" none "git push &&"
expect "grant: cd two args" $P "$A" none "cd a b && git push"
expect "grant: angle bracket message" $P "$A" none "git commit -m 'feat(x): <y>' && git push"
expect "grant: nested shell" $P "$A" none "bash -c 'git push'"
expect "grant: env prefix" $P "$A" none "GIT_SSH_COMMAND=x git push"
expect "grant: file redirect" $P "$A" none "git push >out.txt"
expect "grant: unterminated quote" $P "$A" none "git push 'x"
expect "grant: only harmless" $P "$A" none "git status && git log"
expect "grant: unrelated prompt" $P "$A" none "curl -X POST https://example.com"
expect "grant: push in PreToolUse" $T "$A" none "git push"
expect "grant: commit and push in PreToolUse" $T "$A" none "git commit -m x && git push"
expect "grant: gh in PreToolUse" $T "$A" none "git commit -m x && gh pr view 1"
expect "grant: log in PreToolUse" $T "$A" none "git log && git commit -m x"
expect "grant: unrelated PreToolUse" $T "$A" none "ls -la"
# argv cannot carry NUL, so this payload is built directly.
out="$(printf '{"hook_event_name":"PermissionRequest","session_id":"%s","tool_name":"Bash","tool_input":{"command":"git push\\u0000origin"}}' "$A" | "$hook")"
if [ -z "$out" ]; then pass "grant: NUL"; else fail "grant: NUL" "$out"; fi

# Same grant, another session.
expect "other session: git push" $P "$B" none "git push"
expect "other session: git commit" $T "$B" none "git commit -m x"

# Malformed session ids and grant files.
expect "traversal session id" $P "../$A" none "git push"
expect "empty session id" $P "" none "git push"
write_grant "$B" "$((now - 7200))" "$((now - 60))"
expect "expired grant" $P "$B" none "git push"
write_grant "$B" "$now" "$((now + 9 * 3600))"
expect "grant over 8h" $P "$B" none "git push"
write_grant "$B" "$now" "\"$((now + 60))\""
expect "string expires_at" $P "$B" none "git push"
write_grant "$B" "$((now + 60))" "$((now + 120))"
expect "grant from the future" $P "$B" none "git push"
printf 'not json' >"$grants/$B.json"
expect "malformed grant file" $P "$B" none "git push"
rm -f "$grants/$B.json"

# Other tools and unreadable input: silent.
out="$(python3 -c 'import json,sys; print(json.dumps({"hook_event_name": "PermissionRequest", "session_id": sys.argv[1], "tool_name": "Edit", "tool_input": {"command": "git push"}}))' "$A" | "$hook")"; status=$?
if [ "$status" -eq 0 ] && [ -z "$out" ]; then pass "Edit tool ignored"; else fail "Edit tool ignored" "exit $status: $out"; fi
out="$(echo 'not json' | "$hook")"; status=$?
if [ "$status" -eq 0 ] && [ -z "$out" ]; then pass "malformed stdin ignored"; else fail "malformed stdin ignored" "exit $status: $out"; fi

# Decision shapes.
out="$(payload $P "$A" "git push" | "$hook")"
if printf '%s' "$out" | python3 -c 'import json,sys; o=json.load(sys.stdin); h=o["hookSpecificOutput"]; assert h["hookEventName"]=="PermissionRequest"; assert h["decision"]=={"behavior":"allow"}; assert o["systemMessage"].startswith("publish-gate")'; then pass "PermissionRequest shape"; else fail "PermissionRequest shape" "$out"; fi
out="$(payload $T "$A" "git commit -m x" | "$hook")"
if printf '%s' "$out" | python3 -c 'import json,sys; h=json.load(sys.stdin)["hookSpecificOutput"]; assert h["hookEventName"]=="PreToolUse"; assert h["permissionDecision"]=="allow"; assert h["permissionDecisionReason"].startswith("publish-gate")'; then pass "PreToolUse shape"; else fail "PreToolUse shape" "$out"; fi

# gh-api-gate is independent of grants.
out="$(payload $T "$A" "gh api -X POST repos/o/r/issues -f title=x" | "$gate")"
if printf '%s' "$out" | grep -q '"permissionDecision": "ask"'; then pass "gh-api-gate still asks"; else fail "gh-api-gate still asks" "$out"; fi

# claude-grant CLI.
rm -rf "$grants"
if out="$("$cli" 30m "$B")" && [ -f "$grants/$B.json" ]; then expect "cli grant allows" $P "$B" allow "git push"; else fail "cli grant" "$out"; fi
perm="$(stat -c '%a' "$grants/$B.json")"; dperm="$(stat -c '%a' "$grants")"
if [ "$perm" = 600 ] && [ "$dperm" = 700 ]; then pass "cli modes"; else fail "cli modes" "file $perm dir $dperm"; fi
out="$(CLAUDE_CODE_SESSION_ID="$A" "$cli" 2h)"
case "$out" in *"$A"*) pass "cli resolves CLAUDE_CODE_SESSION_ID" ;; *) fail "cli resolves CLAUDE_CODE_SESSION_ID" "$out" ;; esac
if python3 -c 'import json,sys; g=json.load(open(sys.argv[1])); assert g["expires_at"]-g["granted_at"]==7200' "$grants/$A.json"; then pass "cli 2h duration"; else fail "cli 2h duration" "$(cat "$grants/$A.json")"; fi
if "$cli" 90 "$B" >/dev/null && python3 -c 'import json,sys; g=json.load(open(sys.argv[1])); assert g["expires_at"]-g["granted_at"]==5400' "$grants/$B.json"; then pass "cli bare minutes"; else fail "cli bare minutes" "$(cat "$grants/$B.json")"; fi
for bad in 9h 481 0 2d x ""; do
  if "$cli" "$bad" "$B" >/dev/null 2>&1; then fail "cli rejects duration '$bad'" "accepted"; else pass "cli rejects duration '$bad'"; fi
done
if "$cli" 1h "../x" >/dev/null 2>&1; then fail "cli rejects bad session id" "accepted"; else pass "cli rejects bad session id"; fi
out="$("$cli" list)"
case "$out" in *"$A until"*"$B until"*) pass "cli list" ;; *) fail "cli list" "$out" ;; esac
"$cli" revoke "$A" >/dev/null && expect "cli revoke" $P "$A" none "git push"
"$cli" revoke all >/dev/null
if [ -z "$(ls -A "$grants")" ]; then pass "cli revoke all"; else fail "cli revoke all" "$(ls -A "$grants")"; fi

if "$cli" 1h >/dev/null 2>&1; then fail "cli without session id" "accepted"; else pass "cli without session id"; fi
if "$cli" revoke >/dev/null 2>&1; then fail "cli revoke without session id" "accepted"; else pass "cli revoke without session id"; fi

if [ "$fails" -eq 0 ]; then echo "all passed"; else echo "$fails failed"; exit 1; fi
