#!/usr/bin/env bash
# Claude Code status line. Reads the session JSON on stdin.
# Layout: [model] place branch* | ctx 42% | in 120k (cache 91%) out 3k | $3.40 | auto
# Token counts come from the last API call; cost is per session.
set -u
input=$(cat)

# Tab-separated so names with spaces (model display names, paths) stay whole.
IFS=$'\t' read -r model cwd worktree pct in_tok cache_tok out_tok cost mode < <(
  printf '%s' "$input" | jq -r '
    .context_window.current_usage as $u
    | (($u.input_tokens // 0) + ($u.cache_creation_input_tokens // 0) + ($u.cache_read_input_tokens // 0)) as $in
    | [
        (.model.display_name // "?"),
        (.workspace.current_dir // "."),
        (.workspace.git_worktree // "-"),
        ((.context_window.used_percentage // 0) | floor),
        $in,
        ($u.cache_read_input_tokens // 0),
        ($u.output_tokens // 0),
        (.cost.total_cost_usd // 0),
        (.permission_mode // "-")
      ] | map(tostring) | join("\t")'
)

k() { # tokens -> compact "12k" / "1.2M"
  local n=$1
  if [ "$n" -ge 1000000 ]; then awk -v n="$n" 'BEGIN{printf "%.1fM", n/1000000}'
  elif [ "$n" -ge 1000 ]; then printf '%dk' $((n / 1000))
  else printf '%d' "$n"; fi
}

place=$worktree
[ "$place" = "-" ] && place=$(basename "$cwd")

branch=""
dirty=""
if git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch=$(git -C "$cwd" symbolic-ref --short -q HEAD 2>/dev/null || git -C "$cwd" rev-parse --short HEAD 2>/dev/null)
  [ -n "$(git -C "$cwd" status --porcelain 2>/dev/null | head -1)" ] && dirty="*"
fi

# Drop the branch when it repeats the worktree name; keep the dirty marker.
if [ "$branch" = "$place" ]; then
  place="${place}${dirty}"
  branch=""
else
  branch="${branch}${dirty}"
fi

cache_pct=0
[ "$in_tok" -gt 0 ] && cache_pct=$((cache_tok * 100 / in_tok))

# Colour the context percentage: green < 50, yellow < 80, red after.
if [ "$pct" -ge 80 ]; then c=$'\033[31m'; elif [ "$pct" -ge 50 ]; then c=$'\033[33m'; else c=$'\033[32m'; fi
dim=$'\033[2m'; rst=$'\033[0m'

printf '%s[%s]%s %s%s | ctx %s%d%%%s | in %s (cache %d%%) out %s | $%.2f | %s\n' \
  "$dim" "$model" "$rst" "$place" "${branch:+ ${dim}${branch}${rst}}" \
  "$c" "$pct" "$rst" "$(k "$in_tok")" "$cache_pct" "$(k "$out_tok")" "$cost" "$mode"
