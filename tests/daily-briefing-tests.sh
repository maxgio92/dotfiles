#!/usr/bin/env bash
# Tests for bin/daily-briefing. Stub claude and gh on PATH record their argv,
# so no model or network is touched. The checks cover the permission flags:
# the run loads user settings, so every user Bash allow must come back denied.
# Run: bash tests/daily-briefing-tests.sh

set -uo pipefail

here="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
script="$here/../bin/daily-briefing"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

export HOME="$tmp/home"
export XDG_STATE_HOME="$tmp/state"
mkdir -p "$HOME/.claude" "$HOME/.config/daily-briefing" "$tmp/bin"
printf 'repos:\n  - example/repo\n' >"$HOME/.config/daily-briefing/config.yaml"

cat >"$tmp/bin/claude" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$@" >"$STUB_LOG"
echo '# Briefing'
STUB
cat >"$tmp/bin/gh" <<'STUB'
#!/usr/bin/env bash
echo '[]'
STUB
chmod +x "$tmp/bin/claude" "$tmp/bin/gh"
export PATH="$tmp/bin:$PATH"
export STUB_LOG="$tmp/argv"

fails=0
pass() { echo "ok   $1"; }
fail() { echo "FAIL $1: $2"; fails=$((fails + 1)); }

# The value after --disallowedTools up to the next flag, one per line.
denied() {
  awk '$0 == "--disallowedTools" { on = 1; next } /^--/ { on = 0 } on' "$STUB_LOG"
}

cat >"$HOME/.claude/settings.json" <<'JSON'
{"permissions": {"allow": ["Bash(codex-companion:*)", "Bash(gh-api-safe:*)", "Bash(gh pr view:*)", "Read(~/notes/**)"]}}
JSON
rm -f "$STUB_LOG"
if sh "$script" >/dev/null 2>&1; then
  for want in "Bash(codex-companion:*)" "Bash(gh-api-safe:*)" "Bash(gh pr view:*)" Read Write WebFetch; do
    if denied | grep -qxF -- "$want"; then
      pass "denies $want"
    else
      fail "denies $want" "missing from --disallowedTools: $(denied | tr '\n' ' ')"
    fi
  done
  if denied | grep -qxF -- "Read(~/notes/**)"; then
    fail "keeps non-Bash allows out of the denies" "Read(~/notes/**) denied"
  else
    pass "keeps non-Bash allows out of the denies"
  fi
  if grep -qxF -- "Bash(agent-slack message list:*)" "$STUB_LOG"; then
    pass "allows the agent-slack reads"
  else
    fail "allows the agent-slack reads" "rule missing"
  fi
  # Built-in read-only commands skip permission rules, so the Bash gate hook
  # must reach the run through --settings.
  hook=$(awk 'prev == "--settings" { print; exit } { prev = $0 }' "$STUB_LOG" |
    jq -r '.hooks.PreToolUse[] | select(.matcher == "Bash|Monitor") | .hooks[].command' 2>/dev/null)
  if [ "$hook" = "sh '$(readlink -f "$script")' --bash-gate" ]; then
    pass "gates every Bash call with the hook"
  else
    fail "gates every Bash call with the hook" "hook command: $hook"
  fi
else
  fail "runs with user Bash allows" "exit $?"
fi

# gate <command>: exit status of the hook for a Bash call running <command>.
gate() {
  jq -nc --arg c "$1" '{tool_name: "Bash", tool_input: {command: $c}}' |
    sh "$script" --bash-gate 2>/dev/null
}
for cmd in \
  'agent-slack channel list --limit 200 --cursor dXNlcjpVMDYx==' \
  'agent-slack message list C123 --oldest 1700000000 --limit 200 --include-reactions' \
  'agent-slack message list C123 --thread-ts 1700000000.000100' \
  'agent-slack search messages "release notes" --channel general'; do
  if gate "$cmd"; then pass "gate allows: $cmd"; else fail "gate allows: $cmd" "exit $?"; fi
done
# The denied commands must reach the gate unexpanded.
# shellcheck disable=SC2016
for cmd in \
  'grep -r xoxp- ~/.config' \
  "find ~ -name '*.env'" \
  'cat ~/.config/agent-slack/credentials.json' \
  'agent-slack message send C123 hi' \
  'agent-slack message list C1; cat /etc/passwd' \
  'agent-slack message list C1 && ls' \
  'agent-slack message list C1 | sh' \
  'agent-slack message list C1 >/tmp/x' \
  'agent-slack message list ~/x' \
  'agent-slack search messages "$(id)"' \
  'agent-slack search messages "`id`"' \
  'agent-slack search messages "a\" ; id; \""' \
  "$(printf 'agent-slack message list C1\nls')"; do
  gate "$cmd"
  status=$?
  if [ "$status" -eq 2 ]; then pass "gate denies: $cmd"; else fail "gate denies: $cmd" "exit $status"; fi
done
for input in '{}' 'not json'; do
  status=0
  printf '%s' "$input" | sh "$script" --bash-gate 2>/dev/null || status=$?
  if [ "$status" -eq 2 ]; then pass "gate denies input $input"; else fail "gate denies input $input" "exit $status"; fi
done

echo 'not json' >"$HOME/.claude/settings.json"
rm -f "$STUB_LOG"
if sh "$script" >/dev/null 2>&1; then
  fail "unreadable user settings stop the run" "exit 0"
elif [ -e "$STUB_LOG" ]; then
  fail "unreadable user settings stop the run" "claude ran"
else
  pass "unreadable user settings stop the run"
fi

rm -f "$HOME/.claude/settings.json" "$STUB_LOG"
if sh "$script" >/dev/null 2>&1 && [ -e "$STUB_LOG" ]; then
  pass "runs without user settings"
else
  fail "runs without user settings" "claude did not run"
fi

[ "$fails" -eq 0 ] || { echo "$fails failed"; exit 1; }
echo "all passed"
