#!/usr/bin/env bash
# Tests for gh-review-post. A PATH shim replaces gh: it answers the files
# list and pr view reads from fixtures and records the POST argv and stdin,
# so no network is touched. The test lives outside bin/ because the Makefile
# rsyncs that whole directory into ~/.local/bin.
# Run: bash tests/gh-review-post-tests.sh

# shellcheck disable=SC2016 # backticks in drafts are literal Markdown

set -uo pipefail

here="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
script="$here/../bin/gh-review-post"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

head_sha="0123456789abcdef0123456789abcdef01234567"
other_sha="fedcba9876543210fedcba9876543210fedcba98"

mkdir -p "$tmp/bin"
cat > "$tmp/bin/gh" <<'SHIM'
#!/usr/bin/env bash
# Every call appends its argv to GH_SHIM_CALLS. The files list prints
# GH_SHIM_FILES (concatenated page arrays, as --paginate does); pr view
# prints GH_SHIM_HEAD and GH_SHIM_CHANGED. The POST records argv and stdin.
# GH_SHIM_422=1 fails the POST like GitHub's validation error: the status on
# stderr and the JSON error body on stdout. GH_SHIM_NOISE=1 adds a warning
# on stderr before the URL, as gh does for an update notice.
printf '%s\n' "$*" >> "$GH_SHIM_CALLS"
case " $* " in
  *" --method POST "*)
    printf '%s\n' "$@" > "$GH_SHIM_ARGV"
    cat > "$GH_SHIM_STDIN"
    if [ -n "${GH_SHIM_422:-}" ]; then
      echo 'gh: Validation Failed (HTTP 422)' >&2
      echo '{"message":"Validation Failed","errors":["Line could not be resolved"]}'
      exit 1
    fi
    [ -z "${GH_SHIM_NOISE:-}" ] || echo 'A new release of gh is available' >&2
    echo "https://github.com/octo/repo.js/pull/42#pullrequestreview-777"
    ;;
  " pr view "*)
    printf '{"headRefOid":"%s","changedFiles":%s}\n' "$GH_SHIM_HEAD" "${GH_SHIM_CHANGED:-3}"
    ;;
  *"/files "*)
    cat "$GH_SHIM_FILES"
    ;;
  *)
    echo "gh shim: unexpected call: $*" >&2
    exit 1
    ;;
esac
SHIM
chmod +x "$tmp/bin/gh"
export GH_SHIM_ARGV="$tmp/argv" GH_SHIM_STDIN="$tmp/stdin" GH_SHIM_CALLS="$tmp/calls"
export GH_SHIM_FILES="$tmp/files.json" GH_SHIM_HEAD="$head_sha"
export PATH="$tmp/bin:$PATH"

# src/a.go hunks, numbered (old,new):
#   @@ -3,4 +3,5 @@  ctx (3,3) ctx (4,4) -del (5,-) +add (-,5) +add (-,6) ctx (6,7)
#   @@ -10,3 +11,3 @@ ctx (10,11) -del (11,-) +add (-,12) ctx (12,13)
# The second page holds a binary file with no patch, as GitHub omits it.
cat > "$GH_SHIM_FILES" <<'JSON'
[{"sha":"aa","filename":"src/a.go","status":"modified","additions":3,"deletions":2,
  "patch":"@@ -3,4 +3,5 @@ func x() {\n ctx3\n ctx4\n-del5\n+add5\n+add6\n ctx6\n@@ -10,3 +11,3 @@\n ctx10\n-del11\n+add12\n ctx12"}]
[{"sha":"bb","filename":"img/logo.png","status":"modified","additions":0,"deletions":0}]
JSON

mixed="$tmp/mixed.md"
cat > "$mixed" <<'MD'
Request changes: two blocking findings.

### block: head-side finding

The added call drops the "error".

It also skips the retry.

Reference: `src/a.go:head:12`

### request: base-side finding
The removed check guarded nil.
Reference: `src/a.go:base:5`

### note: out of hunk
This line is far from the diff.
Reference: `src/a.go:head:400`

### note: bare citation
No side on this one.
Reference: `src/a.go:7`
MD

fails=0
pass() { echo "ok   $1"; }
fail() { echo "FAIL $1: $2"; fails=$((fails + 1)); }

reset_shim() { rm -f "$GH_SHIM_ARGV" "$GH_SHIM_STDIN" "$GH_SHIM_CALLS"; }
post_count() { grep -c -- '--method POST' "$GH_SHIM_CALLS" 2>/dev/null || true; }

good="https://github.com/octo/repo.js/pull/42"

# The mixed draft: two anchored findings inline, the rest in the body.
reset_shim
out="$("$script" "$good" --commit "$head_sha" --body-file "$mixed" 2>"$tmp/stderr")"; status=$?
if [ "$status" -ne 0 ]; then
  fail "mixed draft posts" "exit $status: $(cat "$tmp/stderr")"
else
  want_argv="$(printf '%s\n' api --hostname github.com --method POST repos/octo/repo.js/pulls/42/reviews --input - --jq .html_url)"
  if [ "$(cat "$GH_SHIM_ARGV")" = "$want_argv" ]; then pass "exact POST argv"; else
    fail "exact POST argv" "argv was: $(tr '\n' ' ' < "$GH_SHIM_ARGV")"
  fi
  want_calls="$(printf '%s\n' \
    "api --hostname github.com repos/octo/repo.js/pulls/42/files --paginate" \
    "pr view $good --json headRefOid,changedFiles" \
    "api --hostname github.com --method POST repos/octo/repo.js/pulls/42/reviews --input - --jq .html_url")"
  if [ "$(cat "$GH_SHIM_CALLS")" = "$want_calls" ]; then pass "reads then one POST, in order"; else
    fail "reads then one POST, in order" "calls were: $(cat "$GH_SHIM_CALLS")"
  fi
  want_body="$(printf '%s\n' \
    'Request changes: two blocking findings.' \
    '' \
    '### note: out of hunk' \
    'This line is far from the diff.' \
    'Reference: `src/a.go:head:400`' \
    '' \
    '### note: bare citation' \
    'No side on this one.' \
    'Reference: `src/a.go:7`')"
  want_payload="$(jq -n --arg c "$head_sha" --arg b "$want_body" '{
    commit_id: $c, event: "COMMENT", body: $b,
    comments: [
      {path: "src/a.go", line: 12, side: "RIGHT",
       body: "The added call drops the \"error\".\n\nIt also skips the retry."},
      {path: "src/a.go", line: 5, side: "LEFT", body: "The removed check guarded nil."}
    ]}')"
  if [ "$(jq -S . < "$GH_SHIM_STDIN")" = "$(jq -S . <<< "$want_payload")" ]; then pass "exact payload"; else
    fail "exact payload" "stdin was: $(cat "$GH_SHIM_STDIN")"
  fi
  if jq -e '.event == "COMMENT" and ([.. | objects | has("position")] | any | not)' < "$GH_SHIM_STDIN" >/dev/null; then
    pass "event COMMENT, no position"
  else
    fail "event COMMENT, no position" "stdin was: $(cat "$GH_SHIM_STDIN")"
  fi
  if [ "$out" = "https://github.com/octo/repo.js/pull/42#pullrequestreview-777" ]; then pass "stdout is the review URL"; else
    fail "stdout is the review URL" "stdout was: $out"
  fi
fi

# expect_fallback NAME REFERENCE: the finding stays in the body with its
# Reference line and no inline comment is sent.
expect_fallback() {
  local name="$1" ref="$2" draft="$tmp/fallback.md" status
  printf 'Approve.\n\n### note: t\nProse.\nReference: `%s`\n' "$ref" > "$draft"
  reset_shim
  "$script" "$good" --commit "$head_sha" --body-file "$draft" >/dev/null 2>"$tmp/stderr"; status=$?
  [ "$status" -eq 0 ] || { fail "$name" "exit $status: $(cat "$tmp/stderr")"; return; }
  local want
  want="$(printf 'Approve.\n\n### note: t\nProse.\nReference: `%s`' "$ref")"
  [ "$(jq -r .body < "$GH_SHIM_STDIN")" = "$want" ] || { fail "$name" "body was: $(jq -r .body < "$GH_SHIM_STDIN")"; return; }
  [ "$(jq '.comments | length' < "$GH_SHIM_STDIN")" = 0 ] || { fail "$name" "comments: $(jq -c .comments < "$GH_SHIM_STDIN")"; return; }
  pass "$name"
}

expect_fallback "no-patch file falls back" "img/logo.png:head:1"
expect_fallback "path missing from the list falls back" "src/missing.go:head:12"
expect_fallback "base-side context line falls back" "src/a.go:base:3"
expect_fallback "line past the last hunk falls back" "src/a.go:head:14"

# A context line in new-file numbering is commentable on RIGHT.
draft="$tmp/context.md"
printf 'Approve.\n\n### note: t\nProse.\nReference: `src/a.go:head:7`\n' > "$draft"
reset_shim
if "$script" "$good" --commit "$head_sha" --body-file "$draft" >/dev/null 2>&1 &&
   [ "$(jq -c '.comments' < "$GH_SHIM_STDIN")" = '[{"path":"src/a.go","line":7,"side":"RIGHT","body":"Prose."}]' ] &&
   [ "$(jq -r .body < "$GH_SHIM_STDIN")" = "Approve." ]; then
  pass "head-side context line goes inline"
else
  fail "head-side context line goes inline" "stdin was: $(cat "$GH_SHIM_STDIN" 2>/dev/null)"
fi

# More than 3000 changed files warns on stderr and still posts.
reset_shim
out="$(GH_SHIM_CHANGED=3001 "$script" "$good" --commit "$head_sha" --body-file "$mixed" 2>"$tmp/stderr")"; status=$?
if [ "$status" -eq 0 ] && grep -q -- '3001 files' "$tmp/stderr" && [ "$(post_count)" = 1 ]; then
  pass "changedFiles > 3000 warns"
else
  fail "changedFiles > 3000 warns" "exit $status: $(cat "$tmp/stderr")"
fi

# A moved head exits 64 with both shas and never POSTs.
reset_shim
out="$(GH_SHIM_HEAD="$other_sha" "$script" "$good" --commit "$head_sha" --body-file "$mixed" 2>&1)"; status=$?
if [ "$status" -eq 64 ] && grep -q -- "$other_sha" <<< "$out" && grep -q -- "$head_sha" <<< "$out" &&
   [ ! -e "$GH_SHIM_ARGV" ]; then
  pass "head mismatch exits 64, no POST"
else
  fail "head mismatch exits 64, no POST" "exit $status: $out"
fi

# A 422 is surfaced with GitHub's body, exits non-zero, and is not retried.
reset_shim
out="$(GH_SHIM_422=1 "$script" "$good" --commit "$head_sha" --body-file "$mixed" 2>"$tmp/stderr")"; status=$?
if [ "$status" -ne 0 ] && [ -z "$out" ] && grep -q -- 'HTTP 422' "$tmp/stderr" &&
   grep -q -- 'Line could not be resolved' "$tmp/stderr" && [ "$(post_count)" = 1 ]; then
  pass "422 surfaced, exactly one POST"
else
  fail "422 surfaced, exactly one POST" "exit $status, posts $(post_count): $(cat "$tmp/stderr")"
fi

# gh's stderr noise stays off stdout, so the caller's captured URL is clean.
reset_shim
out="$(GH_SHIM_NOISE=1 "$script" "$good" --commit "$head_sha" --body-file "$mixed" 2>"$tmp/stderr")"; status=$?
if [ "$status" -eq 0 ] && [ "$out" = "https://github.com/octo/repo.js/pull/42#pullrequestreview-777" ] &&
   grep -q -- 'new release' "$tmp/stderr"; then
  pass "stderr noise stays off stdout"
else
  fail "stderr noise stays off stdout" "exit $status: stdout '$out', stderr '$(cat "$tmp/stderr")'"
fi

# GH_HOST must not move the calls off the host the URL was validated against.
reset_shim
if GH_HOST=other.example "$script" "$good" --commit "$head_sha" --body-file "$mixed" >/dev/null 2>&1 &&
   [ "$(grep -A1 -x -- '--hostname' "$GH_SHIM_ARGV" | tail -n1)" = "github.com" ]; then
  pass "GH_HOST ignored, hostname pinned"
else
  fail "GH_HOST ignored, hostname pinned" "argv was: $(tr '\n' ' ' < "$GH_SHIM_ARGV" 2>/dev/null)"
fi

# expect_policy NAME [GREP] -- ARGS...: exit 64, gh never called, stderr matches GREP.
expect_policy() {
  local name="$1" pattern="$2"; shift 2
  [ "$1" = "--" ] && shift
  reset_shim
  local out status
  out="$("$script" "$@" 2>&1)"; status=$?
  [ "$status" -eq 64 ] || { fail "$name" "exit $status (want 64): $out"; return; }
  [ ! -e "$GH_SHIM_CALLS" ] || { fail "$name" "gh was invoked: $(cat "$GH_SHIM_CALLS")"; return; }
  if [ -n "$pattern" ] && ! grep -q -- "$pattern" <<< "$out"; then
    fail "$name" "stderr lacks '$pattern': $out"; return
  fi
  pass "$name"
}

c=(--commit "$head_sha")
b=(--body-file "$mixed")

expect_policy "non-github host" "not a pull request URL" -- "https://gitlab.com/octo/repo/pull/42" "${c[@]}" "${b[@]}"
expect_policy "url with a fragment" "not a pull request URL" -- "$good#discussion_r1" "${c[@]}" "${b[@]}"
expect_policy "url with /files" "not a pull request URL" -- "$good/files" "${c[@]}" "${b[@]}"
expect_policy "repo named ." "repository name" -- "https://github.com/octo/./pull/42" "${c[@]}" "${b[@]}"
expect_policy "repo named .." "repository name" -- "https://github.com/octo/../pull/42" "${c[@]}" "${b[@]}"
expect_policy "bad owner" "not a pull request URL" -- "https://github.com/oc_to/repo/pull/42" "${c[@]}" "${b[@]}"
expect_policy "missing url" "missing pull request URL" -- "${c[@]}" "${b[@]}"
expect_policy "short commit" "40-character" -- "$good" --commit abc123 "${b[@]}"
expect_policy "uppercase commit" "40-character" -- "$good" --commit "${head_sha^^}" "${b[@]}"
expect_policy "missing --commit" "missing --commit" -- "$good" "${b[@]}"
expect_policy "--commit without value" "needs a sha" -- "$good" "${b[@]}" --commit
expect_policy "--commit twice" "given twice" -- "$good" "${c[@]}" "${c[@]}" "${b[@]}"
expect_policy "--commit=SHA" "--commit SHA" -- "$good" "--commit=$head_sha" "${b[@]}"
expect_policy "missing --body-file" "missing --body-file" -- "$good" "${c[@]}"
expect_policy "--body-file without value" "needs a path" -- "$good" "${c[@]}" --body-file
expect_policy "--body-file twice" "given twice" -- "$good" "${c[@]}" "${b[@]}" "${b[@]}"
expect_policy "--body-file=PATH" "--body-file PATH" -- "$good" "${c[@]}" "--body-file=$mixed"
expect_policy "unknown flag" "unknown flag" -- "$good" "${c[@]}" "${b[@]}" --event
expect_policy "extra argument" "extra argument" -- "$good" "$good" "${c[@]}" "${b[@]}"
expect_policy "stdin body" "not stdin" -- "$good" "${c[@]}" --body-file -
expect_policy "empty body path" "path is empty" -- "$good" "${c[@]}" --body-file ''
expect_policy "missing body file" "missing or unreadable" -- "$good" "${c[@]}" --body-file "$tmp/nope.md"
: > "$tmp/empty.md"
expect_policy "empty body file" "is empty" -- "$good" "${c[@]}" --body-file "$tmp/empty.md"
if [ "$(id -u)" -ne 0 ]; then
  printf 'Approve.\n' > "$tmp/unreadable.md"; chmod 000 "$tmp/unreadable.md"
  expect_policy "unreadable body file" "missing or unreadable" -- "$good" "${c[@]}" --body-file "$tmp/unreadable.md"
fi

# expect_draft_policy NAME GREP CONTENT: a body file shaped CONTENT exits 64
# before any gh call.
expect_draft_policy() {
  printf '%s' "$3" > "$tmp/draft.md"
  expect_policy "$1" "$2" -- "$good" "${c[@]}" --body-file "$tmp/draft.md"
}

expect_draft_policy "Verdict: skip refused" "skip report" $'Verdict: skip\nSkip-reason: too-large\n'
expect_draft_policy "Skip-reason: refused" "skip report" $'Approve.\n\nSkip-reason: too-large\n'
expect_draft_policy "missing preamble" "no verdict" $'### note: t\nProse.\nReference: `src/a.go:head:5`\n'
expect_draft_policy "blank preamble" "no verdict" $'\n  \n### note: t\nProse.\nReference: `src/a.go:head:5`\n'
expect_draft_policy "finding without Reference at EOF" "no Reference line" $'Approve.\n\n### note: t\nProse.\n'
expect_draft_policy "finding without Reference before next heading" "no Reference line" \
  $'Approve.\n\n### note: a\nProse.\n\n### note: b\nProse.\nReference: `src/a.go:head:5`\n'
expect_draft_policy "text after a Reference line" "follows a Reference line" \
  $'Approve.\n\n### note: t\nProse.\nReference: `src/a.go:head:5`\nStray text.\n'

# Missing tools: a PATH with bash and only one of gh or jq.
mkdir -p "$tmp/nogh" "$tmp/nojq"
ln -s "$(command -v bash)" "$tmp/nogh/bash"
ln -s "$(command -v jq)" "$tmp/nogh/jq"
ln -s "$(command -v bash)" "$tmp/nojq/bash"
ln -s "$tmp/bin/gh" "$tmp/nojq/gh"
expect_tool_policy() {
  local name="$1" dir="$2" pattern="$3" out status
  reset_shim
  out="$(PATH="$dir" "$script" "$good" "${c[@]}" "${b[@]}" 2>&1)"; status=$?
  if [ "$status" -eq 64 ] && grep -q -- "$pattern" <<< "$out" && [ ! -e "$GH_SHIM_CALLS" ]; then
    pass "$name"
  else
    fail "$name" "exit $status: $out"
  fi
}
expect_tool_policy "gh missing" "$tmp/nogh" "gh is required"
expect_tool_policy "jq missing" "$tmp/nojq" "jq is required"

# expect_usage NAME -- ARGS...: exit 2 and gh never called.
expect_usage() {
  local name="$1"; shift
  [ "$1" = "--" ] && shift
  reset_shim
  local status
  "$script" "$@" >/dev/null 2>&1; status=$?
  [ "$status" -eq 2 ] || { fail "$name" "exit $status (want 2)"; return; }
  [ ! -e "$GH_SHIM_CALLS" ] || { fail "$name" "gh was invoked"; return; }
  pass "$name"
}

expect_usage "bare call exits 2" --
expect_usage "--help exits 2" -- --help
expect_usage "-h exits 2" -- "$good" -h

if [ "$fails" -ne 0 ]; then
  echo "$fails test(s) failed" >&2
  exit 1
fi
echo "all tests passed"
