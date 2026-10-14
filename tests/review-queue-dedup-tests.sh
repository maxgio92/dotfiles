#!/usr/bin/env bash
# Tests for review-queue-dedup. Fixture reports live in a temporary reports
# root, so no real report is read. The test lives outside bin/ because the
# Makefile rsyncs that whole directory into ~/.local/bin.
# Run: bash tests/review-queue-dedup-tests.sh

set -uo pipefail

here="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
script="$here/../bin/review-queue-dedup"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

root="$tmp/agent-reports"
mkdir -p "$root/example" "$root/api" "$root/other-name"

sha_a="$(printf 'a%.0s' {1..40})"
sha_b="$(printf 'b%.0s' {1..40})"
sha_c="$(printf 'c%.0s' {1..40})"
sha_d="$(printf 'd%.0s' {1..40})"

example="https://github.com/maxgio92/example/pull"
fence="\`\`\`"

# report PATH URL HEAD...: a review-pr style header; each extra HEAD is a
# follow-up section with its own Head: line, in order.
report() {
  local path="$1" url="$2" first="$3"; shift 3
  {
    printf '# Review: fixture\n\nPR: %s\nHead: %s\nTier: standard\n\n' "$url" "$first"
    printf '%smarkdown\nNo findings.\n%s\n' "$fence" "$fence"
    local h
    for h in "$@"; do
      printf '\n## Follow-up\n\nHead: %s\nBase-head: %s\n' "$h" "$first"
    done
  } > "$path"
}

report "$root/example/2026-10-14-review-pr-1.md" "$example/1" "$sha_a"
# Head moved after this draft; the current head is sha_b.
report "$root/example/2026-10-14-review-pr-2.md" "$example/2" "$sha_a"
# Follow-up section with a later Head: wins over the header.
report "$root/example/2026-10-14-review-pr-3.md" "$example/3" "$sha_a" "$sha_b"
# No Head: line at all, as after a crash mid-write.
printf '# Review: fixture\n\nPR: %s/4\nTier: standard\n' "$example" > "$root/example/2026-10-14-review-pr-4.md"
# Same number and repo name under two owners share one subdirectory.
report "$root/api/2026-10-14-review-pr-7.md" "https://github.com/org-a/api/pull/7" "$sha_a"
# Prefix number: a report for /pull/55 must not satisfy /pull/5.
report "$root/example/2026-10-14-review-pr-55.md" "$example/55" "$sha_a"
# Drafted yesterday; today's file name differs but the report still counts.
report "$root/example/2026-10-13-review-pr-8.md" "$example/8" "$sha_c"
# Skip verdict for the current head counts as drafted.
{
  printf '# Review: fixture\n\nPR: %s/9\nHead: %s\nTier: standard\n' "$example" "$sha_d"
  printf 'Verdict: skip\nSkip-reason: generated\n'
} > "$root/example/2026-10-14-review-pr-9.md"
# Report saved under a different repo subdirectory than the repo name.
report "$root/other-name/2026-10-14-review-pr-10.md" "$example/10" "$sha_a"
# Two reports at the same head; the newest file name is printed.
report "$root/example/2026-10-12-review-pr-11.md" "$example/11" "$sha_a"
report "$root/example/2026-10-14-review-pr-11.md" "$example/11" "$sha_a"
# The other owner's report the same day takes the collision suffix.
report "$root/api/2026-10-14-review-pr-7-2.md" "https://github.com/org-b/api/pull/7" "$sha_b"
# Head moved the same day; the redraft at the current head has the suffix.
report "$root/example/2026-10-14-review-pr-13.md" "$example/13" "$sha_a"
report "$root/example/2026-10-14-review-pr-13-2.md" "$example/13" "$sha_b"
# Same head in every file: the date prefix wins, then the numeric suffix.
report "$root/example/2026-10-13-review-pr-14-3.md" "$example/14" "$sha_a"
report "$root/example/2026-10-14-review-pr-14.md" "$example/14" "$sha_a"
report "$root/example/2026-10-14-review-pr-14-2.md" "$example/14" "$sha_a"
report "$root/example/2026-10-14-review-pr-14-10.md" "$example/14" "$sha_a"
# A suffix that is not a number is not a review-reports collision name.
report "$root/example/2026-10-14-review-pr-15-2x.md" "$example/15" "$sha_a"

# Fixtures for --latest and --list live in their own root, so the list
# output stays small.
lroot="$tmp/list-reports"
mkdir -p "$lroot/example" "$lroot/other" "$tmp/empty-reports/example"
# Latest across two dates: the newer date wins whatever its head.
report "$lroot/example/2026-10-12-review-pr-20.md" "$example/20" "$sha_a"
report "$lroot/example/2026-10-14-review-pr-20.md" "$example/20" "$sha_b"
# Same date: the collision suffix beats no suffix.
report "$lroot/example/2026-10-14-review-pr-21.md" "$example/21" "$sha_a"
report "$lroot/example/2026-10-14-review-pr-21-2.md" "$example/21" "$sha_c"
# A follow-up Head: supersedes the header's.
report "$lroot/example/2026-10-14-review-pr-22.md" "$example/22" "$sha_a" "$sha_d"
# PR: and Head: lines inside a fence are ignored; the real PR: is another URL.
{
  printf '# Review: fixture\n\nPR: %s/23\nHead: %s\nTier: standard\n\n' "$example" "$sha_a"
  printf '%smarkdown\nPR: %s/23\nHead: %s\n%s\n' "$fence" "https://github.com/evil/repo/pull/23" "$sha_b" "$fence"
} > "$lroot/example/2026-10-14-review-pr-23.md"
# PR: number does not match the file name number.
report "$lroot/other/2026-10-14-review-pr-24.md" "$example/25" "$sha_a"
# No Head: line: --list still lists it, --latest has nothing.
printf '# Review: fixture\n\nPR: %s/26\nTier: standard\n' "$example" > "$lroot/example/2026-10-14-review-pr-26.md"
# Invalid PR: value is not listed.
printf '# Review: fixture\n\nPR: %s/27/\nHead: %s\n' "$example" "$sha_a" > "$lroot/example/2026-10-14-review-pr-27.md"

sums_before="$(cd "$tmp" && find . -type f -print0 | sort -z | xargs -0 sha256sum; find . | sort)"

fails=0
pass() { echo "ok   $1"; }
fail() { echo "FAIL $1: $2"; fails=$((fails + 1)); }

# expect NAME STATUS WANT_STDOUT -- ARGS...: exact exit status and stdout.
expect() {
  local name="$1" want_status="$2" want_out="$3"; shift 3
  [ "$1" = "--" ] && shift
  local out status
  out="$("$script" "$@" 2>/dev/null)"; status=$?
  [ "$status" -eq "$want_status" ] || { fail "$name" "exit $status (want $want_status), stdout: $out"; return; }
  [ "$out" = "$want_out" ] || { fail "$name" "stdout was: $out"; return; }
  pass "$name"
}

# expect_usage NAME -- ARGS...: exit 2, nothing on stdout, usage on stderr.
expect_usage() {
  local name="$1"; shift
  [ "$1" = "--" ] && shift
  local out err status
  err="$("$script" "$@" 2>&1 >/dev/null)"; status=$?
  out="$("$script" "$@" 2>/dev/null)"
  [ "$status" -eq 2 ] || { fail "$name" "exit $status (want 2)"; return; }
  [ -z "$out" ] || { fail "$name" "stdout was: $out"; return; }
  grep -q -- '^usage: review-queue-dedup' <<< "$err" || { fail "$name" "no usage line: $err"; return; }
  pass "$name"
}

expect "match on current head" 0 "$root/example/2026-10-14-review-pr-1.md" -- "$root" "$example/1" "$sha_a"
expect "head changed is not drafted" 1 "" -- "$root" "$example/2" "$sha_b"
expect "follow-up Head: wins (later head matches)" 0 "$root/example/2026-10-14-review-pr-3.md" -- "$root" "$example/3" "$sha_b"
expect "follow-up Head: wins (header head no longer matches)" 1 "" -- "$root" "$example/3" "$sha_a"
expect "no Head: line is not drafted" 1 "" -- "$root" "$example/4" "$sha_a"
expect "same owner matches" 0 "$root/api/2026-10-14-review-pr-7.md" -- "$root" "https://github.com/org-a/api/pull/7" "$sha_a"
expect "other owner with same repo and number does not match" 1 "" -- "$root" "https://github.com/org-b/api/pull/7" "$sha_a"
expect "prefix number 5 does not match 55" 1 "" -- "$root" "$example/5" "$sha_a"
expect "number 55 matches itself" 0 "$root/example/2026-10-14-review-pr-55.md" -- "$root" "$example/55" "$sha_a"
expect "yesterday's file still matches" 0 "$root/example/2026-10-13-review-pr-8.md" -- "$root" "$example/8" "$sha_c"
expect "skip report counts as drafted" 0 "$root/example/2026-10-14-review-pr-9.md" -- "$root" "$example/9" "$sha_d"
expect "report under another repo subdirectory" 0 "$root/other-name/2026-10-14-review-pr-10.md" -- "$root" "$example/10" "$sha_a"
expect "newest file name wins among matches" 0 "$root/example/2026-10-14-review-pr-11.md" -- "$root" "$example/11" "$sha_a"
expect "other owner's suffixed report matches" 0 "$root/api/2026-10-14-review-pr-7-2.md" -- "$root" "https://github.com/org-b/api/pull/7" "$sha_b"
expect "suffixed report at the current head matches" 0 "$root/example/2026-10-14-review-pr-13-2.md" -- "$root" "$example/13" "$sha_b"
expect "unsuffixed report at the old head still matches" 0 "$root/example/2026-10-14-review-pr-13.md" -- "$root" "$example/13" "$sha_a"
expect "newest date then numeric suffix wins" 0 "$root/example/2026-10-14-review-pr-14-10.md" -- "$root" "$example/14" "$sha_a"
expect "non-numeric suffix is not a candidate" 1 "" -- "$root" "$example/15" "$sha_a"
expect "no report for the number" 1 "" -- "$root" "$example/12" "$sha_a"
expect "missing root" 1 "" -- "$tmp/nope" "$example/1" "$sha_a"

expect_usage "no arguments" --
expect_usage "two arguments" -- "$root" "$example/1"
expect_usage "four arguments" -- "$root" "$example/1" "$sha_a" extra
expect_usage "issue url rejected" -- "$root" "https://github.com/maxgio92/example/issues/1" "$sha_a"
expect_usage "trailing slash rejected" -- "$root" "$example/1/" "$sha_a"
expect_usage "url with fragment rejected" -- "$root" "$example/1#discussion_r1" "$sha_a"
expect_usage "other host rejected" -- "$root" "https://ghe.example/maxgio92/example/pull/1" "$sha_a"
expect_usage "http scheme rejected" -- "$root" "http://github.com/maxgio92/example/pull/1" "$sha_a"
expect_usage "non-numeric number rejected" -- "$root" "$example/x" "$sha_a"
expect_usage "leading zero number rejected" -- "$root" "$example/01" "$sha_a"
expect_usage "short sha rejected" -- "$root" "$example/1" "abc123"
expect_usage "uppercase sha rejected" -- "$root" "$example/1" "$(printf 'A%.0s' {1..40})"
expect_usage "41-char sha rejected" -- "$root" "$example/1" "${sha_a}a"

expect "latest across two dates" 0 "$lroot/example/2026-10-14-review-pr-20.md $sha_b" -- --latest "$lroot" "$example/20"
expect "latest: collision suffix beats no suffix" 0 "$lroot/example/2026-10-14-review-pr-21-2.md $sha_c" -- --latest "$lroot" "$example/21"
expect "latest: follow-up Head: supersedes header" 0 "$lroot/example/2026-10-14-review-pr-22.md $sha_d" -- --latest "$lroot" "$example/22"
expect "latest: fenced Head: ignored" 0 "$lroot/example/2026-10-14-review-pr-23.md $sha_a" -- --latest "$lroot" "$example/23"
expect "latest: fenced PR: ignored" 1 "" -- --latest "$lroot" "https://github.com/evil/repo/pull/23"
expect "latest: no Head: line" 1 "" -- --latest "$lroot" "$example/26"
expect "latest: no report" 1 "" -- --latest "$lroot" "$example/99"
expect "latest: missing root" 1 "" -- --latest "$tmp/nope" "$example/20"
expect "list: distinct sorted URLs, fenced and mismatched ignored" 0 "$(printf '%s\n' "$example/20" "$example/21" "$example/22" "$example/23" "$example/26")" -- --list "$lroot"
expect "list: missing root is empty" 0 "" -- --list "$tmp/nope"
expect "list: empty root is empty" 0 "" -- --list "$tmp/empty-reports"

expect_usage "latest: no arguments" -- --latest
expect_usage "latest: one argument" -- --latest "$lroot"
expect_usage "latest: three arguments" -- --latest "$lroot" "$example/20" "$sha_a"
expect_usage "latest: bad url" -- --latest "$lroot" "$example/20/"
expect_usage "list: no arguments" -- --list
expect_usage "list: two arguments" -- --list "$lroot" "$example/20"

sums_after="$(cd "$tmp" && find . -type f -print0 | sort -z | xargs -0 sha256sum; find . | sort)"
if [ "$sums_before" = "$sums_after" ]; then
  pass "fixtures unchanged after all runs"
else
  fail "fixtures unchanged after all runs" "checksums or file list changed"
fi

if [ "$fails" -ne 0 ]; then
  echo "$fails test(s) failed" >&2
  exit 1
fi
echo "all tests passed"
