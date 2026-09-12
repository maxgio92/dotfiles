#!/usr/bin/env bash
# Tests for gh-review-reply. A PATH shim replaces gh and records its argv
# and stdin, so no network is touched. The test lives outside bin/ because
# the Makefile rsyncs that whole directory into ~/.local/bin.
# Run: bash tests/gh-review-reply-tests.sh

set -uo pipefail

here="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
script="$here/../bin/gh-review-reply"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/bin"
cat > "$tmp/bin/gh" <<'SHIM'
#!/usr/bin/env bash
# GH_SHIM_NESTED=<root id> makes the POST fail like GitHub does for a reply
# to a reply, and answers the follow-up comment GET with that root id.
if [ -n "${GH_SHIM_NESTED:-}" ]; then
  case " $* " in
    *" --method POST "*)
      printf '%s\n' "$@" > "$GH_SHIM_ARGV"
      cat > "$GH_SHIM_STDIN"
      echo 'gh: Validation Failed (HTTP 422)' >&2
      echo '{"message":"Validation Failed","errors":[{"resource":"PullRequestReviewComment","field":"in_reply_to_id","code":"custom"}]}' >&2
      exit 1
      ;;
    *)
      echo "$GH_SHIM_NESTED"
      exit 0
      ;;
  esac
fi
printf '%s\n' "$@" > "$GH_SHIM_ARGV"
cat > "$GH_SHIM_STDIN"
echo "https://github.com/o/r/pull/7#discussion_r999"
SHIM
chmod +x "$tmp/bin/gh"
export GH_SHIM_ARGV="$tmp/argv" GH_SHIM_STDIN="$tmp/stdin"
export PATH="$tmp/bin:$PATH"

body="$tmp/body.md"
printf 'Fixed in a1b2c3d.\n\nIt said "done" and it\x27s done.\n' > "$body"

fails=0
pass() { echo "ok   $1"; }
fail() { echo "FAIL $1: $2"; fails=$((fails + 1)); }

reset_shim() { rm -f "$GH_SHIM_ARGV" "$GH_SHIM_STDIN"; }

# expect_post NAME URL: the reply lands on the exact endpoint with the file body.
expect_post() {
  local name="$1" url="$2" out status
  reset_shim
  out="$("$script" "$url" --body-file "$body" 2>&1)"; status=$?
  [ "$status" -eq 0 ] || { fail "$name" "exit $status: $out"; return; }
  local want_argv
  want_argv="$(printf '%s\n' api --hostname github.com --method POST repos/octo/repo.js/pulls/42/comments/123456/replies --input - --jq .html_url)"
  [ "$(cat "$GH_SHIM_ARGV")" = "$want_argv" ] || { fail "$name" "argv was: $(tr '\n' ' ' < "$GH_SHIM_ARGV")"; return; }
  local want_body
  want_body="$(jq -Rs '{body: .}' < "$body")"
  [ "$(cat "$GH_SHIM_STDIN")" = "$want_body" ] || { fail "$name" "stdin was: $(cat "$GH_SHIM_STDIN")"; return; }
  [ "$(jq -r .body < "$GH_SHIM_STDIN")" = "$(cat "$body")" ] || { fail "$name" "body did not round-trip"; return; }
  [ "$out" = "https://github.com/o/r/pull/7#discussion_r999" ] || { fail "$name" "stdout was: $out"; return; }
  pass "$name"
}

# expect_policy NAME [GREP] -- ARGS...: exit 64, gh never called, stderr matches GREP.
expect_policy() {
  local name="$1" pattern="$2"; shift 2
  [ "$1" = "--" ] && shift
  reset_shim
  local out status
  out="$("$script" "$@" 2>&1)"; status=$?
  [ "$status" -eq 64 ] || { fail "$name" "exit $status (want 64): $out"; return; }
  [ ! -e "$GH_SHIM_ARGV" ] || { fail "$name" "gh was invoked"; return; }
  if [ -n "$pattern" ] && ! grep -q -- "$pattern" <<< "$out"; then
    fail "$name" "stderr lacks '$pattern': $out"; return
  fi
  pass "$name"
}

good="https://github.com/octo/repo.js/pull/42"

expect_post "discussion_r fragment" "$good#discussion_r123456"
expect_post "short r fragment" "$good#r123456"
expect_post "files view url" "$good/files#discussion_r123456"

# GH_HOST must not move the write off the host the URL was validated against.
reset_shim
if GH_HOST=other.example "$script" "$good#r123456" --body-file "$body" >/dev/null 2>&1 &&
   [ "$(grep -A1 -x -- '--hostname' "$GH_SHIM_ARGV" | tail -n1)" = "github.com" ]; then
  pass "GH_HOST ignored, hostname pinned"
else
  fail "GH_HOST ignored, hostname pinned" "argv was: $(tr '\n' ' ' < "$GH_SHIM_ARGV" 2>/dev/null)"
fi

expect_policy "issuecomment rejected" "gh pr comment" -- "$good#issuecomment-123456" --body-file "$body"
expect_policy "--body-file=PATH rejected" "--body-file PATH" -- "$good#r1" "--body-file=$body"
expect_policy "stdin body rejected" "not stdin" -- "$good#r1" --body-file -
expect_policy "unknown flag rejected" "unknown flag" -- "$good#r1" --body-file "$body" --draft
expect_policy "non-github host rejected" "not a review comment URL" -- "https://gitlab.com/octo/repo/pull/42#r1" --body-file "$body"
expect_policy "missing body file" "missing or unreadable" -- "$good#r1" --body-file "$tmp/nope.md"
: > "$tmp/empty.md"
expect_policy "empty body file" "is empty" -- "$good#r1" --body-file "$tmp/empty.md"

# A reply to a nested reply fails at the API with 422; the script names the
# thread root URL and exits 64.
reset_shim
out="$(GH_SHIM_NESTED=555 "$script" "$good#discussion_r123456" --body-file "$body" 2>&1)"; status=$?
if [ "$status" -eq 64 ] && grep -q -- "root comment: $good#discussion_r555" <<< "$out"; then
  pass "nested reply names the thread root"
else
  fail "nested reply names the thread root" "exit $status: $out"
fi
expect_policy "missing --body-file" "missing --body-file" -- "$good#r1"
expect_policy "extra argument" "extra argument" -- "$good#r1" "$good#r2" --body-file "$body"
expect_policy "no fragment" "not a review comment URL" -- "$good" --body-file "$body"
expect_policy "path traversal in repo" "not a review comment URL" -- "https://github.com/octo/../pull/42#r1" --body-file "$body"

# expect_usage NAME -- ARGS...: exit 2 and gh never called.
expect_usage() {
  local name="$1"; shift
  [ "$1" = "--" ] && shift
  reset_shim
  local status
  "$script" "$@" >/dev/null 2>&1; status=$?
  [ "$status" -eq 2 ] || { fail "$name" "exit $status (want 2)"; return; }
  [ ! -e "$GH_SHIM_ARGV" ] || { fail "$name" "gh was invoked"; return; }
  pass "$name"
}

expect_usage "bare call exits 2" --
expect_usage "--help exits 2" -- --help

if [ "$fails" -ne 0 ]; then
  echo "$fails test(s) failed" >&2
  exit 1
fi
echo "all tests passed"
