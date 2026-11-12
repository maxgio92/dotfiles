#!/usr/bin/env bash
# Tests for the publish-gate hook and the claude-grant CLI. A grant approves
# every permission prompt in one session until it expires, except prompts that
# match an exception. Nothing is executed but the hook and the CLI.
# Run: bash tests/publish-gate-tests.sh

set -uo pipefail

here="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
hook="$here/../.claude/hooks/publish-gate.py"
gate="$here/../.claude/hooks/gh-api-gate.py"
cli="$here/../bin/claude-grant"

XDG_STATE_HOME="$(mktemp -d)"
XDG_CONFIG_HOME="$(mktemp -d)"
export XDG_STATE_HOME XDG_CONFIG_HOME
work="$(mktemp -d)"
# Body and message files must live under /tmp, whatever TMPDIR says.
tb="$(mktemp -d /tmp/publish-gate-tests.XXXXXX)"
trap 'rm -rf "$XDG_STATE_HOME" "$XDG_CONFIG_HOME" "$work" "$tb"' EXIT
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

# tool_payload SESSION TOOL INPUT_JSON
tool_payload() {
  python3 -c 'import json,sys; print(json.dumps({"hook_event_name": "PermissionRequest", "session_id": sys.argv[1], "tool_name": sys.argv[2], "tool_input": json.loads(sys.argv[3])}))' "$1" "$2" "$3"
}

# expect_tool NAME SESSION WANT TOOL INPUT_JSON
expect_tool() {
  local out status got
  out="$(tool_payload "$2" "$4" "$5" | "$hook" 2>&1)"; status=$?
  [ "$status" -eq 0 ] || { fail "$1" "exit $status: $out"; return; }
  got="$(printf '%s' "$out" | decision)"
  [ "$got" = "$3" ] || { fail "$1" "decided $got, want $3: $out"; return; }
  pass "$1"
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

# pin: what claude-grant records for the current exceptions file.
pin() {
  if [ -f "$XDG_CONFIG_HOME/claude-grant/exceptions" ]; then
    sha256sum "$XDG_CONFIG_HOME/claude-grant/exceptions" | cut -d' ' -f1
  else
    echo defaults
  fi
}

# write_grant SESSION GRANTED_AT EXPIRES_AT [PIN] (raw JSON values)
write_grant() {
  mkdir -p "$grants"
  printf '{"granted_at": %s, "expires_at": %s, "exceptions": "%s"}' "$2" "$3" "${4-$(pin)}" >"$grants/$1.json"
}

now=$(date +%s)
P=PermissionRequest
T=PreToolUse

# No grant: never a decision.
expect "no grant: git push" $P "$A" none "git push"
expect "no grant: compound" $P "$A" none "cd ~/x && sed -i s/a/b/ f && git push -q --force-with-lease fork b 2>&1 | tail -1"
expect_tool "no grant: Edit" "$A" none Edit '{"file_path": "/tmp/x", "old_string": "a", "new_string": "b"}'

write_grant "$A" "$now" "$((now + 3600))"

# Grant: anything that prompts is approved...
expect "grant: plain push" $P "$A" allow "git push"
expect "grant: the agent's real compound push" $P "$A" allow "cd ~/wd/feat-1 && sed -i '0,/^  epoch: 0\$/s//  epoch: 1/' f.yaml && (cd e && ./lint.sh f.yaml | tail -1) && git add f.yaml && GIT_EDITOR=true git rebase --continue 2>&1 | tail -1 && git push -q --force-with-lease fork feat-1 2>&1 | tail -1; gh pr view 1 --repo o/r --json headRefOid -q .headRefOid"
expect "grant: loop with substitutions" $P "$A" allow 'for b in a c; do (cd ~/wd/$b && git push -q --force-with-lease fork $b); done'
expect "grant: lease value" $P "$A" allow "git push --force-with-lease=b:abc fork HEAD:refs/heads/b"
expect "grant: gh pr create draft" $P "$A" allow "git push -u fork b && gh pr create -d -t t -F /tmp/b.md"
expect "grant: gh pr merge" $P "$A" allow "gh pr merge 1 --squash --delete-branch"
expect "grant: gh pr ready" $P "$A" allow "gh pr ready 1"
expect "grant: gh pr review" $P "$A" allow "gh pr review 1 --approve"
expect "grant: gh issue comment" $P "$A" allow "gh issue comment 1 --body-file /tmp/c.md"
expect "grant: rm -f elsewhere" $P "$A" allow "git push fork b && rm -f /tmp/x"
expect_tool "grant: Edit in repo" "$A" allow Edit '{"file_path": "/tmp/repo/x.go", "old_string": "a", "new_string": "b"}'
expect_tool "grant: WebFetch" "$A" allow WebFetch '{"url": "https://example.com", "prompt": "x"}'
expect_tool "grant: Linear save" "$A" allow mcp__linear__save_comment '{"issueId": "X-1", "body": "b"}'

# ...except the default exceptions.
expect "exc: --force" $P "$A" none "git push --force fork b"
expect "exc: --force=" $P "$A" none "git push --force=yes fork b"
expect "exc: -f" $P "$A" none "git push -f fork b"
expect "exc: bundled -qf" $P "$A" none "git push -qf fork b"
expect "exc: +refspec" $P "$A" none "git push fork +b"
expect "exc: force in compound" $P "$A" none "cd /x && git add . && git push -q -f fork b 2>&1 | tail -1"
expect "exc: git -C push -f" $P "$A" none "git -C /x push -f fork b"
expect "deletion allowed: --delete" $P "$A" allow "git push --delete fork b"
expect "deletion allowed: -d" $P "$A" allow "git push -d fork b"
expect "deletion allowed: :dst" $P "$A" allow "git push fork :b"
expect "exc: quoted +refspec" $P "$A" none "git push fork '+b'"
expect "deletion allowed: quoted :dst" $P "$A" allow 'git push fork ":b"'
expect "exc: --mirror" $P "$A" none "git push --mirror fork"
expect "exc: --prune" $P "$A" none "git push --prune fork 'refs/heads/*:refs/heads/*'"
expect "exc: config push refspec" $P "$A" none "git config remote.fork.push '+refs/heads/*:refs/heads/*' && git push fork"
expect "exc: config mirror" $P "$A" none "git config remote.fork.mirror true; git push fork"
expect "exc: git -c" $P "$A" none "git -c remote.fork.mirror=true push fork"
expect "exc: git -C x -c" $P "$A" none "git -C /x -c core.hooksPath=/tmp push fork b"
expect "exc: gh api write" $P "$A" none "gh api -X POST repos/o/r/issues/1/comments -f body=x"
expect "exc: gh api in compound" $P "$A" none "git push fork b && gh api -X PUT repos/o/r/pulls/1/merge"
expect "deletion allowed: delete in loop" $P "$A" allow 'for b in a c; do git push -q fork --delete $b; done'
expect "exc: shell on .claude" $P "$A" none "sed -i s/ask/allow/ ~/.claude/settings.json"
expect "exc: shell on dotfiles .claude" $P "$A" none "cp x ~/.dotfiles/.claude/settings.json"
expect "exc: claude-grant" $P "$A" none "~/.local/bin/claude-grant 8h"
expect "exc: grant dir" $P "$A" none "echo x > ~/.local/state/claude-publish-grants/y.json"
expect "exc: Slack send" $P "$A" none 'agent-slack message send C1 "$(cat /tmp/m.txt)" --thread-ts 1.2'
expect "exc: Slack send via wrapper path" $P "$A" none "~/.local/bin/agent-slack message send C1 hi"
expect "exc: Slack send via npm path" $P "$A" none "/home/linuxbrew/.linuxbrew/bin/agent-slack message send C1 hi"
expect "exc: Slack send via node" $P "$A" none "node /x/node_modules/agent-slack/bin/agent-slack.js message send C1 hi"
expect "exc: Slack send after env prefix" $P "$A" none "SLACK_TOKEN=x agent-slack message send C1 hi"
expect "exc: Slack send after global flag" $P "$A" none "agent-slack --safe-mode message send C1 hi"
expect "exc: Slack send quoted" $P "$A" none "agent-slack 'message' \"send\" C1 hi"
expect "exc: Slack send in compound" $P "$A" none "cd /tmp && agent-slack message send C1 hi | jq .ts"
expect "exc: Slack send after line continuation" $P "$A" none $'agent-slack message \\\nsend C1 hi'
expect "exc: Slack send split mid-word" $P "$A" none $'agent-sl\\\nack message send C1 hi'
expect "exc: Slack compose after flag between words" $P "$A" none "agent-slack message --safe-mode compose C1 hi"
expect "exc: Slack send after quoted flag and continuation" $P "$A" none $'agent-slack \'message\' --safe-mode \\\n  "send" C1 hi'
expect "exc: Slack scheduled cancel after flag" $P "$A" none "agent-slack message scheduled --safe-mode cancel X"
expect "exc: push after line continuation" $P "$A" none $'git \\\npush --force origin main'
for sub in "message edit" "message delete" "message compose" "message draft create" "message react add" \
  "message react remove" "message scheduled cancel" "canvas create" "canvas edit" "channel new" \
  "channel invite" "channel mark" "user dm-open" "workflow run"; do
  expect "exc: Slack $sub" $P "$A" none "agent-slack $sub X"
done
expect "exc: Slack token read" $P "$A" none "cat ~/.config/agent-slack/token"
expect "exc: Slack compose after quoted flag and env prefix" $P "$A" none 'CI=1 agent-slack message "--safe-mode" compose C1 hi'
expect "exc: Slack send with quote inside a word" $P "$A" none "agent-slack mess'age' send C1 hi"
expect "exc: Slack send after empty quotes" $P "$A" none 'agent-slack message ""send C1 hi'
expect "exc: Slack read with substitution" $P "$A" none 'agent-slack message list C1 "$(agent-slack message send C1 hi)"'
expect "exc: Slack in subshell" $P "$A" none '(agent-slack message send C1 hi)'
expect "exc: Slack outside the read list" $P "$A" none "agent-slack message scheduled list"
expect_tool "exc: Slack MCP send" "$A" none mcp__plugin_slack_slack__slack_send_message '{"channel_id": "C1", "message": "m"}'
expect_tool "exc: Slack MCP canvas" "$A" none mcp__plugin_slack_slack__slack_create_canvas '{"title": "t"}'
expect "not exc: Slack message list" $P "$A" allow "agent-slack message list C1 --thread-ts 1.2"
expect "not exc: Slack search messages send" $P "$A" allow "agent-slack search messages send --limit 5"
expect "not exc: Slack channel list" $P "$A" allow "agent-slack channel list --limit 100"
expect "not exc: Slack search with quoted query" $P "$A" allow 'cd /tmp && agent-slack search messages "release notes" --limit 5 | jq .'
expect "not exc: send in a later segment" $P "$A" allow "agent-slack message list C1; echo message send"
expect_tool "exc: AskUserQuestion" "$A" none AskUserQuestion '{"questions": []}'
expect_tool "exc: ExitPlanMode" "$A" none ExitPlanMode '{"plan": "p"}'
expect_tool "exc: Edit ~/.claude" "$A" none Edit "{\"file_path\": \"$HOME/.claude/settings.json\", \"old_string\": \"a\", \"new_string\": \"b\"}"
expect_tool "exc: Write dotfiles .claude" "$A" none Write "{\"file_path\": \"$HOME/.dotfiles/.claude/x\", \"content\": \"c\"}"
expect_tool "exc: Write exceptions file (XDG)" "$A" none Write "{\"file_path\": \"$XDG_CONFIG_HOME/claude-grant/exceptions\", \"content\": \"\"}"
expect_tool "exc: Write grant file (XDG)" "$A" none Write "{\"file_path\": \"$grants/x.json\", \"content\": \"\"}"
expect_tool "exc: Write via ~" "$A" none Write '{"file_path": "~/.claude/settings.json", "content": ""}'
python3 -c 'import json,sys; print(json.dumps({"hook_event_name": "PermissionRequest", "session_id": sys.argv[1], "tool_name": "Edit", "cwd": sys.argv[2], "tool_input": {"file_path": "settings.json"}}))' "$A" "$HOME/.claude" | "$hook" | grep -q . && fail "exc: relative path under .claude" "approved" || pass "exc: relative path under .claude"
python3 -c 'import json,sys; print(json.dumps({"hook_event_name": "PermissionRequest", "session_id": sys.argv[1], "tool_name": "Edit", "tool_input": {"file_path": "x"}}))' "$A" | "$hook" | grep -q . && fail "exc: relative path without cwd" "approved" || pass "exc: relative path without cwd"
ln -s "$HOME/.claude" "$work/claude-link"
expect_tool "exc: Edit through symlink" "$A" none Edit "{\"file_path\": \"$work/claude-link/settings.json\", \"old_string\": \"a\", \"new_string\": \"b\"}"
expect_tool "exc: project .claude settings" "$A" none Write '{"file_path": "/tmp/repo/.claude/settings.json", "content": "{}"}'
expect_tool "exc: git hook via file tool" "$A" none Write '{"file_path": "/tmp/repo/.git/hooks/pre-push", "content": "x"}'
expect_tool "not exc: file named .gitignore" "$A" allow Edit '{"file_path": "/tmp/repo/.gitignore", "old_string": "a", "new_string": "b"}'
expect "exc: cd into .claude" $P "$A" none "cd ~/.claude && git push"
expect "exc: git hooks in shell" $P "$A" none "cp x .git/hooks/pre-push && git push"
expect_tool "exc: edit claude-grant script" "$A" none Edit "{\"file_path\": \"$HOME/.local/bin/claude-grant\", \"old_string\": \"a\", \"new_string\": \"b\"}"
expect_tool "exc: edit claude-grant source" "$A" none Write "{\"file_path\": \"$HOME/.dotfiles/bin/claude-grant\", \"content\": \"x\"}"
expect "exc: --forc" $P "$A" none "git push --forc fork b"
expect "exc: --fo=" $P "$A" none "git push --fo=1 fork b"
expect "deletion allowed: --del" $P "$A" allow "git push --del fork b"
expect "exc: --mirr" $P "$A" none "git push --mirr fork"
expect "exc: --pru" $P "$A" none "git push --pru fork x"
expect "exc: --config-env" $P "$A" none "git --config-env=remote.fork.mirror=M push fork"
expect "exc: GIT_CONFIG_COUNT env" $P "$A" none "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=remote.fork.mirror GIT_CONFIG_VALUE_0=true git push fork"
expect "exc: env GIT_CONFIG_PARAMETERS" $P "$A" none "env GIT_CONFIG_PARAMETERS=\"'remote.fork.mirror'='true'\" git push fork"
expect "exc: export GIT_CONFIG_GLOBAL" $P "$A" none "export GIT_CONFIG_GLOBAL=/tmp/g && git push fork b"
expect "exc: git remote add --mirror" $P "$A" none "git remote add --mirror=push m /tmp/x && git push m"
expect "exc: shell write to .git/config" $P "$A" none "printf '[remote \"fork\"]\\n\\tmirror = true\\n' >> .git/config && git push fork"
cr="$work/cr"; git init -q "$cr"
expect "config check: clean repo allowed" $P "$A" allow "git push fork b" "$cr"
git -C "$cr" config remote.fork.push '+refs/heads/*:refs/heads/*'
expect "config check: forcing push config" $P "$A" none "git push fork b" "$cr"
git -C "$cr" config --unset remote.fork.push; git -C "$cr" config remote.fork.mirror true
expect "config check: mirror remote" $P "$A" none "git push fork" "$cr"
git -C "$cr" config 'remote.a b.push' ':refs/heads/x'; git -C "$cr" config --unset remote.fork.mirror
expect "config check: spaced remote name" $P "$A" none "git push fork" "$cr"
expect "config check: non-push prompt unaffected" $P "$A" allow "gh pr ready 1" "$cr"
expect "config check: no cwd refused" $P "$A" none "git push fork b" ""
expect "exc: SLACK_TOKEN" $P "$A" none "SLACK_TOKEN=x agent-slack message list C1"
expect "exc: AGENT_SLACK_BIN" $P "$A" none "AGENT_SLACK_BIN=/tmp/e agent-slack auth test"
expect "exc: slack_token lower" $P "$A" none "echo \$slack_token && git push"
expect_tool "exc: Read token file" "$A" none Read "{\"file_path\": \"$HOME/.config/agent-slack/token\"}"
expect "not exc: --follow-tags" $P "$A" allow "git push --follow-tags fork b"
expect "not exc: --dry-run" $P "$A" allow "git push --dry-run fork b"
expect_tool "exc: MCP tool path field" "$A" none mcp__fs__write_file "{\"path\": \"$HOME/.claude/settings.json\", \"content\": \"x\"}"
expect_tool "exc: MCP destination field" "$A" none mcp__fs__move "{\"source\": \"/tmp/a\", \"destination\": \"/tmp/r/.git/hooks/pre-push\"}"
expect_tool "exc: camelCase filePath" "$A" none mcp__linear__create_attachment_from_upload "{\"filePath\": \"$HOME/.claude/settings.json\"}"
expect_tool "exc: MCP non-string path" "$A" none mcp__fs__write_file '{"path": ["x"]}'
expect_tool "not exc: MCP harmless path" "$A" allow mcp__fs__write_file '{"path": "/tmp/notes.md", "content": "x"}'
expect_tool "exc: edit ~/.local/bin helper" "$A" none Edit "{\"file_path\": \"$HOME/.local/bin/gh-api-safe\", \"old_string\": \"a\", \"new_string\": \"b\"}"
expect_tool "exc: write dotfiles bin" "$A" none Write "{\"file_path\": \"$HOME/.dotfiles/bin/workmux\", \"content\": \"x\"}"
expect_tool "exc: write clorch handler" "$A" none Write "{\"file_path\": \"$HOME/.local/share/clorch/hooks/event_handler.sh\", \"content\": \"x\"}"
expect_tool "exc: edit bashrc" "$A" none Edit "{\"file_path\": \"$HOME/.bashrc\", \"old_string\": \"a\", \"new_string\": \"b\"}"
expect_tool "exc: write systemd unit" "$A" none Write "{\"file_path\": \"$HOME/.config/systemd/user/x.service\", \"content\": \"x\"}"
expect "exc: shell into ~/.local/bin" $P "$A" none "cp /tmp/x ~/.local/bin/gh-api-safe && git push"
expect "exc: shell on zshrc" $P "$A" none "echo x >> ~/.zshrc"
expect_tool "not exc: Linear comment" "$A" allow mcp__linear__save_comment '{"issueId": "X-1", "body": "b"}'
expect_tool "not exc: edit outside workdir" "$A" allow Edit '{"file_path": "/tmp/other/main.go", "old_string": "a", "new_string": "b"}'
expect_tool "exc: NotebookEdit no path" "$A" none NotebookEdit '{"new_source": "x"}'
expect_tool "exc: non-dict input" "$A" none Bash '"git push"'
# Not exceptions: lease, -d on gh, refspec colons.
expect "not exc: lease" $P "$A" allow "git push --force-with-lease fork b"
expect "not exc: gh -d after push" $P "$A" allow "git push fork b && gh pr create -d -t t"
expect "not exc: src:dst" $P "$A" allow "git push fork HEAD:refs/heads/b"
expect "not exc: fork remote" $P "$A" allow "git push -u fork feat"

# A custom exceptions file replaces the defaults.
mkdir -p "$XDG_CONFIG_HOME/claude-grant"
printf '# only merges\nbash gh pr merge\ntool mcp__linear__*\n' >"$XDG_CONFIG_HOME/claude-grant/exceptions"
expect "pin: edited file stops the grant" $P "$A" none "git push"
write_grant "$A" "$now" "$((now + 3600))"
expect "custom: merge excepted" $P "$A" none "gh pr merge 1"
expect "custom: force now allowed" $P "$A" allow "git push -f fork b"
expect_tool "custom: Linear excepted" "$A" none mcp__linear__save_comment '{"body": "b"}'
expect "custom: Slack now allowed" $P "$A" allow "agent-slack message send C1 hi"
expect_tool "custom: Slack MCP now allowed" "$A" allow mcp__plugin_slack_slack__slack_send_message '{"message": "m"}'
expect "custom: core still guards .claude" $P "$A" none "sed -i s/a/b/ ~/.claude/settings.json"
expect_tool "custom: core still guards questions" "$A" none AskUserQuestion '{"questions": []}'
: >"$XDG_CONFIG_HOME/claude-grant/exceptions"; write_grant "$A" "$now" "$((now + 3600))"
expect "custom: empty file keeps core" $P "$A" none "cat ~/.claude/x && git push"
expect "custom: empty file allows force" $P "$A" allow "git push -f fork b"
printf 'bash (unclosed\n' >"$XDG_CONFIG_HOME/claude-grant/exceptions"; write_grant "$A" "$now" "$((now + 3600))"
expect "custom: bad regex excepts all" $P "$A" none "ls"
printf 'nonsense line\n' >"$XDG_CONFIG_HOME/claude-grant/exceptions"; write_grant "$A" "$now" "$((now + 3600))"
expect "custom: unknown kind excepts all" $P "$A" none "ls"
printf 'bash\n' >"$XDG_CONFIG_HOME/claude-grant/exceptions"; write_grant "$A" "$now" "$((now + 3600))"
expect "custom: empty value excepts all" $P "$A" none "ls"
printf 'bash x\n' >"$XDG_CONFIG_HOME/claude-grant/exceptions"; chmod 000 "$XDG_CONFIG_HOME/claude-grant/exceptions"
if [ -r "$XDG_CONFIG_HOME/claude-grant/exceptions" ]; then pass "custom: unreadable (skipped as root)"; else expect "custom: unreadable excepts all" $P "$A" none "ls"; fi
rm -f "$XDG_CONFIG_HOME/claude-grant/exceptions"; write_grant "$A" "$now" "$((now + 3600))"

# check mode: the publish skill asks whether a grant covers a post command.
chk() { CLAUDE_CODE_SESSION_ID="$1" "$hook" check -- "$2"; }
[ "$(chk "$A" 'gh pr comment 1 --body-file /tmp/b.md')" = approved ] && pass "check: granted post approved" || fail "check: granted post approved" "$(chk "$A" 'gh pr comment 1 --body-file /tmp/b.md')"
chk "$A" 'gh pr comment 1 --body-file /tmp/b.md' >/dev/null; [ $? -eq 0 ] && pass "check: approved exits 0" || fail "check: approved exits 0" "nonzero"
[ "$(chk "$A" 'agent-slack message send C1 "$(cat /tmp/m)"')" = excepted ] && pass "check: Slack post excepted" || fail "check: Slack post excepted" "approved"
chk "$A" 'agent-slack message send C1 x' >/dev/null; [ $? -eq 1 ] && pass "check: excepted exits 1" || fail "check: excepted exits 1" "exit 0"
[ "$(chk "$A" 'gh api -X POST repos/o/r/issues/1/comments -f body=x')" = excepted ] && pass "check: gh api excepted" || fail "check: gh api excepted" "approved"
[ "$(chk "$B" 'gh pr comment 1 --body-file /tmp/b.md')" = excepted ] && pass "check: no grant excepted" || fail "check: no grant excepted" "approved"
[ "$(CLAUDE_CODE_SESSION_ID= "$hook" check -- 'gh pr comment 1')" = excepted ] && pass "check: no session id excepted" || fail "check: no session id excepted" "approved"
[ "$("$hook" check 'gh pr comment 1' 2>/dev/null)" = excepted ] && pass "check: bad usage excepted" || fail "check: bad usage excepted" "approved"
out="$(payload $P "$A" "gh pr comment 1" | "$hook")"; printf '%s' "$out" | grep -q '"allow"' && pass "check: hook mode unchanged" || fail "check: hook mode unchanged" "$out"

# PreToolUse is ignored: commits go to the classifier.
expect "PreToolUse ignored" $T "$A" none "git commit -m x"

# Same grant, another session.
expect "other session: git push" $P "$B" none "git push"

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
write_grant "$B" "$now" "$((now + 60))" "deadbeef"
expect "wrong exceptions pin" $P "$B" none "git push"
printf '{"granted_at": %s, "expires_at": %s}' "$now" "$((now + 60))" >"$grants/$B.json"
expect "missing exceptions pin" $P "$B" none "git push"
printf 'not json' >"$grants/$B.json"
expect "malformed grant file" $P "$B" none "git push"
rm -f "$grants/$B.json"

# Other tools and unreadable input: silent.
out="$(echo 'not json' | "$hook")"; status=$?
if [ "$status" -eq 0 ] && [ -z "$out" ]; then pass "malformed stdin ignored"; else fail "malformed stdin ignored" "exit $status: $out"; fi

# Decision shapes.
out="$(payload $P "$A" "git push" | "$hook")"
if printf '%s' "$out" | python3 -c 'import json,sys; o=json.load(sys.stdin); h=o["hookSpecificOutput"]; assert h["hookEventName"]=="PermissionRequest"; assert h["decision"]=={"behavior":"allow"}; assert o["systemMessage"].startswith("publish-gate")'; then pass "PermissionRequest shape"; else fail "PermissionRequest shape" "$out"; fi

# gh-api-gate is independent of grants.
out="$(payload $T "$A" "gh api -X POST repos/o/r/issues -f title=x" | "$gate")"
if printf '%s' "$out" | grep -q '"permissionDecision": "ask"'; then pass "gh-api-gate still asks"; else fail "gh-api-gate still asks" "$out"; fi

# claude-grant CLI.
rm -rf "$grants"
if out="$("$cli" 30m "$B")" && python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["exceptions"]=="defaults"' "$grants/$B.json"; then expect "cli grant allows" $P "$B" allow "git push"; else fail "cli grant" "$out"; fi
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
if "$cli" 1h "$B" --root /tmp >/dev/null 2>&1; then fail "cli rejects extra args" "accepted"; else pass "cli rejects extra args"; fi

if [ "$fails" -eq 0 ]; then echo "all passed"; else echo "$fails failed"; exit 1; fi
