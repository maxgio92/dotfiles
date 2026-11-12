#!/usr/bin/env bash
# Tests for the agent-slack wrapper. A copy of the wrapper with REAL_CLI
# rewritten points at a stub CLI
# that records its argv and whether it got the token, never the token value,
# so no network is touched. The test lives outside bin/ because the Makefile
# rsyncs that whole directory into ~/.local/bin.
# Run: bash tests/agent-slack-tests.sh

set -uo pipefail

here="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
script="$here/../bin/agent-slack"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

export HOME="$tmp/home"
mkdir -p "$HOME/.config/agent-slack" "$tmp/bin"
token_file="$HOME/.config/agent-slack/token"
fake_token="xoxp-test-not-a-token"

cat > "$tmp/bin/real" <<'STUB'
#!/usr/bin/env bash
{
  printf 'argv=%s\n' "$*"
  printf 'argc=%s\n' "$#"
  if [ "${SLACK_TOKEN:-}" = "$(<"$HOME/.config/agent-slack/token")" ]; then
    echo token=match
  elif [ -n "${SLACK_TOKEN:-}" ]; then
    echo token=other
  else
    echo token=unset
  fi
  printf 'no_update=%s\n' "${AGENT_SLACK_NO_UPDATE_CHECK:-}"
  printf 'workspace=%s\n' "${SLACK_WORKSPACE_URL:-}"
  printf 'cookie=%s\n' "${SLACK_COOKIE_D:+set}"
  printf 'node_options=%s\n' "${NODE_OPTIONS:-}"
  printf 'proxy=%s\n' "${HTTPS_PROXY:-}"
  printf 'tls=%s\n' "${NODE_TLS_REJECT_UNAUTHORIZED:-}"
} > "$HOME/stub.log"
echo '{"ok":true}'
STUB
chmod +x "$tmp/bin/real"
# copy_wrapper DEST REAL: a copy of the wrapper whose REAL_CLI is REAL.
copy_wrapper() {
  sed "s|^readonly REAL_CLI=.*|readonly REAL_CLI=$2|" "$here/../bin/agent-slack" > "$1"
  chmod +x "$1"
}
copy_wrapper "$tmp/bin/wrapper" "$tmp/bin/real"
script="$tmp/bin/wrapper"
# The wrapper clears the environment but keeps HOME, so the stub logs there.
export STUB_LOG="$HOME/stub.log"

fails=0
pass() { echo "ok   $1"; }
fail() { echo "FAIL $1: $2"; fails=$((fails + 1)); }

reset() {
  rm -f "$STUB_LOG"
  printf '%s\n' "$fake_token" > "$token_file"
  chmod 600 "$token_file"
  rm -f "$HOME/.config/agent-slack/workspace"
}

# expect_run NAME WANT_LINE... -- ARGS...: exit 0, the stub ran, and its log
# holds every WANT_LINE.
expect_run() {
  local name="$1"; shift
  local want=()
  while [ "$1" != "--" ]; do want+=("$1"); shift; done
  shift
  local out status
  out="$("$script" "$@" 2>&1)"; status=$?
  [ "$status" -eq 0 ] || { fail "$name" "exit $status: $out"; return; }
  [ -e "$STUB_LOG" ] || { fail "$name" "the CLI was not invoked"; return; }
  local line
  for line in "${want[@]}"; do
    grep -qxF -- "$line" "$STUB_LOG" || { fail "$name" "log lacks '$line': $(tr '\n' ' ' < "$STUB_LOG")"; return; }
  done
  [ "$out" = '{"ok":true}' ] || { fail "$name" "stdout was: $out"; return; }
  pass "$name"
}

# expect_refused NAME STATUS GREP -- ARGS...: exit STATUS, the stub never ran,
# stderr matches GREP and never shows the token.
expect_refused() {
  local name="$1" code="$2" pattern="$3"; shift 3
  [ "$1" = "--" ] && shift
  local out status
  out="$("$script" "$@" 2>&1)"; status=$?
  [ "$status" -eq "$code" ] || { fail "$name" "exit $status (want $code): $out"; return; }
  [ ! -e "$STUB_LOG" ] || { fail "$name" "the CLI was invoked"; return; }
  grep -q -- "$pattern" <<< "$out" || { fail "$name" "output lacks '$pattern': $out"; return; }
  if grep -qF -- "$fake_token" <<< "$out"; then fail "$name" "output shows the token"; return; fi
  pass "$name"
}

reset
expect_run "passes argv and the token" "argv=auth test" token=match no_update=1 workspace= -- auth test
reset
# shellcheck disable=SC2016 # the body must reach the CLI unexpanded
expect_run "message send body stays one argument" "argv=message send C1 a \"b\" \$(c)" argc=4 token=match -- message send C1 'a "b" $(c)'
reset
SLACK_TOKEN=xoxp-other expect_run "file token beats an inherited SLACK_TOKEN" token=match -- auth test
reset
SLACK_COOKIE_D=d expect_run "drops a browser cookie" cookie= -- auth test
reset
expect_run "--safe-mode before a read" "argv=--safe-mode message list C1" -- --safe-mode message list C1
reset
expect_run "auth whoami allowed" "argv=auth whoami" -- auth whoami
reset
expect_run "help update allowed" "argv=help update" -- help update
reset
printf 'https://example.slack.com\n' > "$HOME/.config/agent-slack/workspace"
expect_run "workspace file sets SLACK_WORKSPACE_URL" workspace=https://example.slack.com -- auth test
reset
printf 'https://example.slack.com\n' > "$HOME/.config/agent-slack/workspace"
SLACK_WORKSPACE_URL=https://other.slack.com expect_run "explicit SLACK_WORKSPACE_URL wins" workspace=https://other.slack.com -- auth test

reset
expect_refused "update" 64 "refusing 'update'" -- update
reset
expect_refused "update after a global flag" 64 "refusing 'update'" -- --safe-mode update --check
reset
for sub in import-chrome import-brave import-firefox import-desktop; do
  expect_refused "auth $sub" 64 "refusing 'auth $sub'" -- auth "$sub"
  reset
done
expect_refused "auth import after flags" 64 "refusing 'auth import-desktop'" -- --safe-mode auth -h import-desktop
reset
rm "$token_file"
expect_refused "missing token" 1 "missing .*token" -- auth test
reset
chmod 644 "$token_file"
expect_refused "token mode 644" 1 "mode 644" -- auth test
reset
: > "$token_file"
expect_refused "empty token" 1 "is empty" -- auth test
reset
printf 'https://evil.example.com\n' > "$HOME/.config/agent-slack/workspace"
expect_refused "bad workspace file" 1 "workspace URL" -- auth test
reset
copy_wrapper "$tmp/bin/wrapper-missing" "$tmp/bin/missing"
script="$tmp/bin/wrapper-missing" expect_refused "missing CLI" 1 "no executable" -- auth test
reset
copy_wrapper "$tmp/bin/wrapper-loop" "$tmp/bin/wrapper-loop"
script="$tmp/bin/wrapper-loop" expect_refused "CLI resolving to the wrapper" 1 "resolves to this wrapper" -- auth test
reset
script="$tmp/bin/wrapper"
reset
NODE_OPTIONS="--require /tmp/x.js" HTTPS_PROXY=http://127.0.0.1:9 NODE_TLS_REJECT_UNAUTHORIZED=0 expect_run "inherited Node, proxy and TLS overrides dropped" node_options= proxy= tls= token=match -- auth test
reset
expect_run "slack message URL allowed" token=match -- message get "https://acme.slack.com/archives/C1/p1700000000000000"
reset
expect_run "enterprise slack URL allowed" token=match -- canvas get "https://acme.enterprise.slack.com/docs/T1/F1"
reset
expect_run "--workspace name allowed" token=match -- message list C1 --workspace acme
reset
expect_run "--workspace slack URL allowed" token=match -- message list C1 --workspace https://acme.slack.com
reset
expect_run "text with a link allowed" token=match -- message send C1 "see https://github.com/o/r/pull/1"
reset
SLACK_WORKSPACE_URL=https://acme.slack.com expect_run "slack SLACK_WORKSPACE_URL allowed" token=match -- auth test
reset
SLACK_WORKSPACE_URL=https://evil.example.com expect_refused "foreign SLACK_WORKSPACE_URL" 64 "only https" -- auth test
reset
SLACK_WORKSPACE_URL=http://acme.slack.com expect_refused "http SLACK_WORKSPACE_URL" 64 "only https" -- auth test
reset
expect_refused "foreign message URL" 64 "only https" -- message get "https://evil.example.com/archives/C1/p1"
reset
expect_refused "userinfo trick URL" 64 "only https" -- message get "https://acme.slack.com@evil.example.com/archives/C1/p1"
reset
expect_refused "suffix trick URL" 64 "only https" -- message get "https://acme.slack.com.evil.example.com/x"
reset
expect_refused "uppercase scheme URL" 64 "only https" -- message get "HTTPS://evil.example.com/x"
reset
expect_refused "foreign --workspace" 64 "only https" -- message list C1 --workspace https://evil.example.com
reset
expect_refused "foreign --workspace=" 64 "only https" -- message list C1 --workspace=evil.example.com/x
printf '#!/bin/sh\necho EVIL "$SLACK_TOKEN"\n' > "$tmp/bin/evil"; chmod +x "$tmp/bin/evil"
if AGENT_SLACK_BIN="$tmp/bin/evil" "$script" auth test 2>&1 | grep -q EVIL; then fail "AGENT_SLACK_BIN ignored" "ran the override"; elif AGENT_SLACK_BIN="$tmp/bin/evil" "$script" auth test >/dev/null 2>&1; then pass "AGENT_SLACK_BIN ignored"; else fail "AGENT_SLACK_BIN ignored" "wrapper failed"; fi

echo
if [ "$fails" -eq 0 ]; then
  echo "all agent-slack tests passed"
else
  echo "$fails agent-slack test(s) failed"
  exit 1
fi
