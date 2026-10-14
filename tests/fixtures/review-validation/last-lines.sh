#!/usr/bin/env bash
# Print the last N lines of a file, numbered from 1.
set -euo pipefail

[ $# -lt 1 ] && echo "usage: last-lines.sh FILE [N]" >&2
file=$1
count=${2:-5}

mapfile -t lines < "$file"
start=$(( ${#lines[@]} - count ))
for (( i = start; i < ${#lines[@]}; i++ )); do
  printf '%d %s\n' "$(( i - start + 1 ))" "${lines[i]}"
done
