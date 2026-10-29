#!/usr/bin/env bash
# Tests for codex-companion. A fake HOME holds the plugin cache and a PATH
# shim replaces node, recording the script path, argv, and stdin, so no real
# Codex runs. The test lives outside bin/ because the Makefile rsyncs that
# whole directory into ~/.local/bin.
# Run: bash tests/codex-companion-tests.sh

set -uo pipefail

here="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
script="$here/../bin/codex-companion"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/bin"
cat > "$tmp/bin/node" <<'SHIM'
#!/usr/bin/env bash
printf '%s\n' "$@" > "$NODE_SHIM_ARGV"
cat > "$NODE_SHIM_STDIN"
exit 3
SHIM
chmod +x "$tmp/bin/node"
export NODE_SHIM_ARGV="$tmp/argv" NODE_SHIM_STDIN="$tmp/stdin"
export PATH="$tmp/bin:$PATH"
unset CLAUDE_PLUGIN_ROOT

fails=0
pass() { echo "ok   $1"; }
fail() { echo "FAIL $1: $2"; fails=$((fails + 1)); }

reset_shim() { rm -f "$NODE_SHIM_ARGV" "$NODE_SHIM_STDIN"; }

plugin() {
  mkdir -p "$1/scripts"
  : > "$1/scripts/codex-companion.mjs"
}

home="$tmp/home"
cache="$home/.claude/plugins/cache/openai-codex/codex"
# 1.0.10 sorts after 1.0.9 only under version sort.
plugin "$cache/1.0.9"
plugin "$cache/1.0.10"
plugin "$cache/1.0.6"

# expect_node NAME WANT_SCRIPT ENV... -- ARGS...: node runs WANT_SCRIPT with
# ARGS, the shim's exit status comes back, and stdin "piped" passes through.
expect_node() {
  local name="$1" want="$2"; shift 2
  local envs=()
  while [ "$1" != "--" ]; do envs+=("$1"); shift; done
  shift
  reset_shim
  local status
  printf 'piped\n' | env "${envs[@]}" "$script" "$@" >/dev/null 2>&1; status=$?
  [ "$status" -eq 3 ] || { fail "$name" "exit $status (want 3)"; return; }
  [ -e "$NODE_SHIM_ARGV" ] || { fail "$name" "node was not invoked"; return; }
  [ "$(cat "$NODE_SHIM_ARGV")" = "$(printf '%s\n' "$want" "$@")" ] ||
    { fail "$name" "argv was: $(tr '\n' ' ' < "$NODE_SHIM_ARGV")"; return; }
  [ "$(cat "$NODE_SHIM_STDIN")" = "piped" ] || { fail "$name" "stdin was: $(cat "$NODE_SHIM_STDIN")"; return; }
  pass "$name"
}

expect_node "newest cache version by version sort" "$cache/1.0.10/scripts/codex-companion.mjs" \
  HOME="$home" -- setup --json
expect_node "arguments with spaces pass through" "$cache/1.0.10/scripts/codex-companion.mjs" \
  HOME="$home" -- adversarial-review --wait -C "/a dir" "focus text with \$dastardly"

root="$tmp/plugin-root"
plugin "$root"
expect_node "CLAUDE_PLUGIN_ROOT wins over the cache" "$root/scripts/codex-companion.mjs" \
  HOME="$home" CLAUDE_PLUGIN_ROOT="$root" -- task
expect_node "CLAUDE_PLUGIN_ROOT without the script falls back to the cache" "$cache/1.0.10/scripts/codex-companion.mjs" \
  HOME="$home" CLAUDE_PLUGIN_ROOT="$tmp/missing" -- task

reset_shim
out="$(HOME="$tmp/empty-home" "$script" setup --json 2>&1 </dev/null)"; status=$?
if [ "$status" -ne 0 ] && [ ! -e "$NODE_SHIM_ARGV" ] &&
   [ "$(wc -l <<< "$out")" -eq 1 ] && grep -q '^codex-companion: no codex-companion.mjs found' <<< "$out"; then
  pass "missing script exits non-zero with one stderr line"
else
  fail "missing script exits non-zero with one stderr line" "exit $status: $out"
fi

if [ "$fails" -ne 0 ]; then
  echo "$fails test(s) failed" >&2
  exit 1
fi
echo "all tests passed"
