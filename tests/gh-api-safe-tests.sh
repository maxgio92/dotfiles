#!/usr/bin/env bash
# Tests for gh-api-safe. A PATH shim replaces gh and records its argv, so no
# network is touched. The test lives outside bin/ because the Makefile
# rsyncs that whole directory into ~/.local/bin.
# Run: bash tests/gh-api-safe-tests.sh

set -uo pipefail

here="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
script="$here/../bin/gh-api-safe"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/bin"
cat > "$tmp/bin/gh" <<'SHIM'
#!/usr/bin/env bash
printf '%s\n' "$@" > "$GH_SHIM_ARGV"
echo '{"name":"repo"}'
SHIM
chmod +x "$tmp/bin/gh"
export GH_SHIM_ARGV="$tmp/argv"
export PATH="$tmp/bin:$PATH"

fails=0
pass() { echo "ok   $1"; }
fail() { echo "FAIL $1: $2"; fails=$((fails + 1)); }

reset_shim() { rm -f "$GH_SHIM_ARGV"; }

# expect_pass NAME -- ARGS... -- WANT_ARGV...: exit 0 and gh sees exactly
# WANT_ARGV (after the pinned 'api --hostname github.com').
expect_pass() {
  local name="$1"; shift
  [ "$1" = "--" ] && shift
  local args=()
  while [ $# -gt 0 ] && [ "$1" != "--" ]; do
    args+=("$1"); shift
  done
  shift
  reset_shim
  local out status
  out="$("$script" "${args[@]}" 2>&1)"; status=$?
  [ "$status" -eq 0 ] || { fail "$name" "exit $status: $out"; return; }
  local want_argv
  want_argv="$(printf '%s\n' api --hostname github.com "$@")"
  [ -e "$GH_SHIM_ARGV" ] || { fail "$name" "gh was not invoked"; return; }
  [ "$(cat "$GH_SHIM_ARGV")" = "$want_argv" ] || { fail "$name" "argv was: $(tr '\n' ' ' < "$GH_SHIM_ARGV")"; return; }
  [ "$out" = '{"name":"repo"}' ] || { fail "$name" "stdout was: $out"; return; }
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
  [ ! -e "$GH_SHIM_ARGV" ] || { fail "$name" "gh was invoked: $(tr '\n' ' ' < "$GH_SHIM_ARGV")"; return; }
  if [ -n "$pattern" ] && ! grep -q -- "$pattern" <<< "$out"; then
    fail "$name" "stderr lacks '$pattern': $out"; return
  fi
  pass "$name"
}

repo="repos/o/r"

expect_pass "plain repo read" -- "$repo" -- "$repo"
expect_pass "--jq passes through" -- "$repo" --jq .name -- "$repo" --jq .name
expect_pass "-q attached passes through" -- "$repo" -q.name -- "$repo" --jq .name
expect_pass "-H Accept passes through" -- "$repo" -H 'Accept: application/vnd.github+json' -- "$repo" --header 'Accept: application/vnd.github+json'
expect_pass "--paginate and --slurp pass through" -- "$repo/issues" --paginate --slurp -- "$repo/issues" --paginate --slurp
expect_pass "--cache and --template pass through" -- "$repo" --cache 1h --template '{{.name}}' -- "$repo" --cache 1h --template '{{.name}}'
expect_pass "-X GET accepted" -- "$repo" -X GET -- "$repo" --method GET
expect_pass "--method=get accepted" -- "$repo" --method=get -- "$repo" --method GET
expect_pass "flag before endpoint" -- --jq .name "$repo" -- "$repo" --jq .name
expect_pass "absolute api url" -- "https://api.github.com/$repo/pulls/1" -- "https://api.github.com/$repo/pulls/1"
expect_pass "search with query string" -- 'search/issues?q=repo:o/r+is:open' -- 'search/issues?q=repo:o/r+is:open'
expect_pass "user, notifications, rate_limit" -- user -- user
expect_pass "notifications" -- notifications -- notifications
expect_pass "rate_limit" -- rate_limit -- rate_limit
expect_pass "explicit github.com hostname" -- "$repo" --hostname github.com -- "$repo"

# GH_HOST must not move the read off github.com.
reset_shim
if GH_HOST=ghe.example "$script" "$repo" >/dev/null 2>&1 &&
   [ "$(grep -A1 -x -- '--hostname' "$GH_SHIM_ARGV" | tail -n1)" = "github.com" ]; then
  pass "GH_HOST ignored, hostname pinned"
else
  fail "GH_HOST ignored, hostname pinned" "argv was: $(tr '\n' ' ' < "$GH_SHIM_ARGV" 2>/dev/null)"
fi

expect_policy "-X POST rejected" "not GET" -- "$repo/issues" -X POST
expect_policy "-XPOST rejected" "not GET" -- "$repo/issues" -XPOST
expect_policy "--method=PATCH rejected" "not GET" -- "$repo" --method=PATCH
expect_policy "-X DELETE rejected" "not GET" -- "$repo/issues/comments/1" -X DELETE
expect_policy "-f body=x rejected" "request field" -- "$repo/issues" -f body=x
expect_policy "-fbody=x rejected" "request field" -- "$repo/issues" -fbody=x
expect_policy "-F body=@f rejected" "request field" -- "$repo/issues" -F body=@f
expect_policy "--field=x rejected" "request field" -- "$repo/issues" --field=x
expect_policy "--raw-field rejected" "request field" -- "$repo/issues" --raw-field body=x
expect_policy "--input - rejected" "request body" -- "$repo/issues" --input -
expect_policy "--input=file rejected" "request body" -- "$repo/issues" --input=body.json
expect_policy "query field outside graphql rejected" "only accepted on the graphql" -- "$repo" -f 'query=x'
expect_policy "unknown flag rejected" "unknown flag" -- "$repo" --nope
expect_policy "second endpoint rejected" "extra argument" -- "$repo" "$repo/pulls"

expect_policy "--hostname ghe rejected" "not github.com" -- "$repo" --hostname ghe.example
expect_policy "--hostname=ghe rejected" "not github.com" -- "$repo" --hostname=ghe.example
expect_policy "other absolute url rejected" "not an allowed REST read path" -- "https://ghe.example/api/v3/$repo"
expect_policy "unknown prefix rejected" "not an allowed REST read path" -- "meta"
expect_policy "repo secrets rejected" "secrets" -- "$repo/actions/secrets"
expect_policy "repo secret item rejected" "secrets" -- "$repo/actions/secrets/TOKEN"
expect_policy "org secrets rejected" "secrets" -- "orgs/o/actions/secrets"
expect_policy "encoded secrets path rejected" "secrets" -- "$repo/actions/%73ecrets"
expect_policy "repo hooks rejected" "webhooks" -- "$repo/hooks"
expect_policy "org hooks rejected" "webhooks" -- "orgs/o/hooks/5"
expect_policy "fragment on hooks path rejected" "fragment" -- "$repo/hooks#ignored"
expect_policy "fragment on secrets path rejected" "fragment" -- "$repo/actions/secrets#x"
expect_policy "dot segment rejected" "dot segment" -- "repos/o/../admin/users"
expect_policy "{repo} placeholder rejected" "placeholder" -- "$repo/{repo}"
expect_policy "{owner}/{repo} placeholders rejected" "placeholder" -- "repos/{owner}/{repo}"
expect_policy ":repo placeholder rejected" "placeholder" -- "$repo/:repo"
expect_policy "admin rejected" "not an allowed REST read path" -- "admin/users"
expect_policy "enterprises rejected" "not an allowed REST read path" -- "enterprises/e/audit-log"
expect_policy "app installations rejected" "not an allowed REST read path" -- "app/installations"

q='query { viewer { login } }'
expect_pass "graphql query accepted" -- graphql -f "query=$q" -- graphql --raw-field "query=$q"
expect_pass "graphql --field query forwarded as --raw-field" -- graphql --field "query=$q" -- graphql --raw-field "query=$q"
expect_pass "graphql -fquery attached accepted" -- graphql "-fquery=$q" -- graphql --raw-field "query=$q"
expect_pass "graphql with --jq" -- graphql -f "query=$q" --jq .data.viewer.login -- graphql --jq .data.viewer.login --raw-field "query=$q"
expect_policy "graphql mutation rejected" "mutation" -- graphql -f 'query=mutation { addStar(input: {starrableId: "x"}) { clientMutationId } }'
expect_policy "graphql named mutation rejected" "mutation" -- graphql -f 'query=mutation Star { addStar(input: {starrableId: "x"}) { clientMutationId } }'
expect_policy "graphql subscription rejected" "mutation or subscription" -- graphql -f 'query=subscription { x }'
expect_policy "graphql mutation after comment line rejected" "mutation" -- graphql -f $'query=# only a comment\nmutation { x }'
expect_policy "graphql mutation after CR-terminated comment rejected" "mutation" -- graphql -f $'query=# c\rmutation { addStar(input:{starrableId:"R_1"}) {clientMutationId} }'
expect_policy "graphql mutation after CRLF-terminated comment rejected" "mutation" -- graphql -f $'query=# c\r\nmutation { x }'
escblk='fragment F on Mutation { addStar(input:{starrableId:"R_1",clientMutationId:""" \""" """}) {clientMutationId}} mutation { ...F }'
expect_policy "graphql mutation after escaped block delimiter rejected" "mutation" -- graphql -f "query=$escblk"
# A document longer than the pipe buffer must still be scanned in full.
padded="mutation { addStar(input:{starrableId:\"R_1\"}) {clientMutationId} }$(printf '\n%.0s' {1..70000})"
expect_policy "graphql mutation padded past the pipe buffer rejected" "mutation" -- graphql -f "query=$padded"
expect_policy "graphql without query rejected" "needs" -- graphql
expect_policy "graphql variable field rejected" "request field" -- graphql -f "query=$q" -F owner=o
expect_policy "graphql stdin query rejected" "not stdin" -- graphql -F query=@-

lit='query { search(query: "mutation subscription", type: ISSUE, first: 1) { issueCount } }'
expect_pass "mutation inside string literal accepted" -- graphql -f "query=$lit" -- graphql --raw-field "query=$lit"
com=$'query {\n  # a mutation would go elsewhere\n  viewer { login }\n}'
expect_pass "mutation inside comment accepted" -- graphql -f "query=$com" -- graphql --raw-field "query=$com"
blk=$'query {\n  search(query: """\n  mutation\n  """, type: ISSUE, first: 1) { issueCount }\n}'
expect_pass "mutation inside block string accepted" -- graphql -f "query=$blk" -- graphql --raw-field "query=$blk"
esc='query { search(query: "a\" mutation", type: ISSUE, first: 1) { issueCount } }'
expect_pass "mutation after escaped quote accepted" -- graphql -f "query=$esc" -- graphql --raw-field "query=$esc"
escblk2='query { search(query: """ \""" mutation """, type: ISSUE, first: 1) { issueCount } }'
expect_pass "mutation inside block string after escaped delimiter accepted" -- graphql -f "query=$escblk2" -- graphql --raw-field "query=$escblk2"

printf '%s\n' "$q" > "$tmp/query.graphql"
expect_pass "graphql query from file" -- graphql -F "query=@$tmp/query.graphql" -- graphql --raw-field "query=$(cat "$tmp/query.graphql")"
# A validated file whose text is itself '@file' must reach gh as literal text,
# not as a second file reference that --field would expand unscanned.
printf 'mutation { x }\n' > "$tmp/payload.graphql"
printf '@%s\n' "$tmp/payload.graphql" > "$tmp/pointer.graphql"
expect_pass "graphql nested @file reference not expanded" -- graphql -F "query=@$tmp/pointer.graphql" -- graphql --raw-field "query=@$tmp/payload.graphql"
printf 'mutation { x }\n' > "$tmp/mut.graphql"
expect_policy "graphql mutation from file rejected" "mutation" -- graphql -F "query=@$tmp/mut.graphql"
expect_policy "graphql missing file rejected" "missing or unreadable" -- graphql -F "query=@$tmp/nope.graphql"

# expect_usage NAME -- ARGS...: exit 64 with usage text and gh never called.
expect_usage() {
  local name="$1"; shift
  [ "$1" = "--" ] && shift
  reset_shim
  local out status
  out="$("$script" "$@" 2>&1)"; status=$?
  [ "$status" -eq 64 ] || { fail "$name" "exit $status (want 64)"; return; }
  [ ! -e "$GH_SHIM_ARGV" ] || { fail "$name" "gh was invoked"; return; }
  grep -q -- '^usage: gh-api-safe' <<< "$out" || { fail "$name" "no usage line: $out"; return; }
  pass "$name"
}

expect_usage "bare call exits 64 with usage" --
expect_usage "--help exits 64 with usage" -- --help

if [ "$fails" -ne 0 ]; then
  echo "$fails test(s) failed" >&2
  exit 1
fi
echo "all tests passed"
