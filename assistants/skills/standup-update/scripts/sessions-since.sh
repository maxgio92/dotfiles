#!/usr/bin/env bash
# Print a compact digest of Claude Code sessions active since a timestamp.
# Usage: sessions-since.sh <ISO-8601 start, e.g. 2026-10-13T00:00:00>
set -eu

since="${1:?usage: sessions-since.sh <ISO start>}"
root="${CLAUDE_PROJECTS_DIR:-$HOME/.claude/projects}"

find "$root" -mindepth 2 -maxdepth 2 -type f -name '*.jsonl' ! -name 'agent-*' \
  -newermt "$since" 2>/dev/null |
while read -r f; do
  # Skip the session drafting the standup.
  grep -qF '[standup-update]' "$f" && continue

  meta=$(jq -rc --arg s "$since" 'select(.cwd and .timestamp >= $s)
    | "\(.cwd) | \(.gitBranch // "-") | \(.sessionId[0:8]) | \(.timestamp[0:16])"' "$f" 2>/dev/null | head -1)
  [ -n "$meta" ] || continue
  end=$(jq -r 'select(.timestamp) | .timestamp[0:16]' "$f" 2>/dev/null | tail -1)

  echo "=== $meta -> $end"
  jq -r --arg s "$since" '
    select(.timestamp >= $s and (.type == "user" or .type == "assistant"))
    | (.message.content | if type == "string" then .
        else (map(select(.type? == "text") | .text) | join(" ")) end) as $t
    | select(($t | length) > 0 and ($t | test("^(<|Base directory for this skill|Another Claude session sent a message)") | not))
    | "\(.type | ascii_upcase[0:1]) \($t | gsub("\\s+"; " ") | .[0:200])"' "$f" 2>/dev/null |
    awk 'NR <= 15 { print; next } { tail[NR % 10] = $0 } END { if (NR > 15) { print "  ..."; for (i = NR - 9; i <= NR; i++) if (i > 15) print tail[i % 10] } }'
  grep -oE 'https://github\.com/[^/" ]+/[^/" ]+/pull/[0-9]+' "$f" | sort -u | sed 's/^/PR /' || true
done
