#!/usr/bin/env bash
# Tests for the gh-api-gate PreToolUse hook: it asks on a visible gh api
# write and stays silent otherwise. Nothing is executed but the hook.
# Run: bash tests/gh-api-gate-tests.sh

set -uo pipefail

here="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
hook="$here/../.claude/hooks/gh-api-gate.py"

fails=0
pass() { echo "ok   $1"; }
fail() { echo "FAIL $1: $2"; fails=$((fails + 1)); }

payload() {
  python3 -c 'import json,sys; print(json.dumps({"tool_name": sys.argv[1], "tool_input": {"command": sys.argv[2]}}))' "$1" "$2"
}

decision() {
  python3 -c 'import json,sys; d=sys.stdin.read(); print(json.loads(d)["hookSpecificOutput"]["permissionDecision"] if d.strip() else "none")'
}

# expect NAME WANT COMMAND: exit 0 and WANT is ask, or none for empty stdout.
expect() {
  local name="$1" want="$2" cmd="$3" out status got
  out="$(payload Bash "$cmd" | "$hook" 2>&1)"; status=$?
  [ "$status" -eq 0 ] || { fail "$name" "exit $status: $out"; return; }
  got="$(printf '%s' "$out" | decision)"
  [ "$got" = "$want" ] || { fail "$name" "decided $got, want $want: $out"; return; }
  pass "$name"
}

# Reads and everything around them: no decision.
expect "plain read" none "gh api repos/o/r"
expect "read with jq and paginate" none "gh api 'repos/o/r/releases?per_page=10' --jq '.[] | \"\\(.tag_name) \\(.name)\"' --paginate"
expect "several reads with echo" none "gh api repos/o/r --jq .stars; echo ---; gh api repos/o/r/tags --jq '.[].name'"
expect "read in a loop with variables" none "set -e; R=repos/o/r; for f in a b; do gh api \"\$R/contents/\$f.mdx\" --jq .content | base64 -d | sed -e 's/<[^>]*>//g' | head -140; done"
expect "read in command substitution" none "n=\$(gh api repos/o/r --jq .stargazers_count); echo \$n"
expect "explicit GET" none "gh api repos/o/r -X GET"
expect "attached GET" none "gh api repos/o/r -XGET"
expect "--method=get" none "gh api repos/o/r --method=get"
expect "graphql query" none "gh api graphql -f query='query { viewer { login } }'"
expect "graphql query with variables" none "gh api graphql -f query='query(\$n:String!){ repository(name:\$n){ id } }' -F n=r"
expect "graphql query from file" none "gh api graphql --field query=@q.graphql"
expect "header and cache flags" none "gh api repos/o/r -H 'Accept: application/vnd.github+json' --cache 1h"
expect "header before graphql endpoint" none "gh api -H 'Accept: application/vnd.github+json' graphql -f query='query { viewer { login } }'"
expect "hostname before graphql endpoint" none "gh api --hostname github.com graphql -f query='{ viewer { login } }'"
expect "explicit GET with query fields" none "gh api search/issues -X GET -f q='is:pr' -f per_page=5"
expect "--method GET with field" none "gh api repos/o/r/commits --method GET -F per_page=1"
expect "read with stderr redirect" none "gh api repos/o/r 2>/dev/null --jq .name"
expect "grep for gh api text" none "rg 'gh api -X' assistants/"
expect "echo quoting a write then a read" none "echo \"gh api -X POST\" && gh api repos/o/r"
expect "no gh api" none "ls; gh pr view 1; gh issue list"
expect "wrapper" none "gh-api-safe repos/o/r"
expect "gh apix" none "gh apix repos/o/r"

# Writes: ask.
expect "POST" ask "gh api -X POST repos/o/r/issues -f title=x"
expect "POST after endpoint" ask "gh api repos/o/r/issues/1/comments -X POST -f body=hi"
expect "attached method" ask "gh api repos/o/r -XDELETE"
expect "--method=PATCH" ask "gh api repos/o/r --method=PATCH -f name=x"
expect "field alone implies POST" ask "gh api repos/o/r/issues/1/comments -f body=hi"
expect "attached field" ask "gh api repos/o/r/issues -fbody=hi"
expect "--field=" ask "gh api repos/o/r/issues --field=title=x"
expect "--raw-field" ask "gh api repos/o/r/issues --raw-field body=x"
expect "--input" ask "gh api repos/o/r/issues --input body.json"
expect "--input=" ask "gh api repos/o/r/issues --input=-"
expect "graphql mutation" ask "gh api graphql -f query='mutation { addComment(input:{}) { clientMutationId } }'"
expect "graphql mutation in raw field" ask "gh api graphql --raw-field 'query=mutation{x}'"
expect "write after reads" ask "gh api repos/o/r; echo ok; gh api -X DELETE repos/o/r/issues/comments/1"
expect "write in a loop" ask "for i in 1 2; do gh api repos/o/r/issues/\$i/comments -f body=hi; done"
expect "write in command substitution" ask "out=\$(gh api -X POST repos/o/r/issues -f title=x)"
expect "write in a nested shell" ask "bash -c 'gh api -X POST repos/o/r/issues -f title=x'"
expect "write after pipe" ask "cat body.md | gh api repos/o/r/issues/1/comments -X POST --input -"
expect "write on the second line" ask "$(printf 'echo a\ngh api -X PUT repos/o/r/topics -f names=x')"
expect "write with env prefix" ask "GH_TOKEN=x gh api -X POST repos/o/r/issues -f title=x"
expect "write with unterminated quote" ask "gh api -X POST repos/o/r/issues -f title='x"
expect "method after stderr redirect" ask "gh api repos/o/r 2>/dev/null -X POST"
expect "method after stdout redirect" ask "gh api repos/o/r >out.json -X DELETE"
expect "method after merged stderr" ask "gh api repos/o/r 2>&1 -X POST"
expect "--input after stdin redirect" ask "gh api repos/o/r <in.json --input -"
expect "field after redirect" ask "gh api repos/o/r >f -f a=b"
expect "continued lines" ask "$(printf 'gh api \\\n  -X POST \\\n  repos/o/r')"
expect "continuation between gh and api" ask "$(printf 'gh \\\napi -X POST repos/o/r')"
expect "path-qualified gh" ask "/usr/bin/gh api -X POST repos/o/r"
# shellcheck disable=SC2088  # the literal tilde is the point
expect "tilde path gh" ask "~/.local/bin/gh api repos/o/r -f a=b"
expect "backtick substitution" ask "echo \`gh api -X POST repos/o/r\`"
expect "eval script" ask "eval 'gh api -X POST repos/o/r'"
expect "header value that looks like a field" none "gh api -H '-f' repos/o/r"

# Other tools and unreadable input: silent.
out="$(payload Edit "gh api -X POST x" | "$hook")"; status=$?
if [ "$status" -eq 0 ] && [ -z "$out" ]; then pass "Edit tool ignored"; else fail "Edit tool ignored" "exit $status: $out"; fi
out="$(echo 'not json' | "$hook")"; status=$?
if [ "$status" -eq 0 ] && [ -z "$out" ]; then pass "malformed stdin ignored"; else fail "malformed stdin ignored" "exit $status: $out"; fi

# Decision shape.
out="$(payload Bash "gh api -X POST repos/o/r" | "$hook")"
if printf '%s' "$out" | python3 -c 'import json,sys; d=json.load(sys.stdin)["hookSpecificOutput"]; assert d["hookEventName"]=="PreToolUse"; assert d["permissionDecision"]=="ask"; assert d["permissionDecisionReason"].startswith("gh-api-gate")'; then pass "decision shape"; else fail "decision shape" "$out"; fi

if [ "$fails" -eq 0 ]; then echo "all passed"; else echo "$fails failed"; exit 1; fi
