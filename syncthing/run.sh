#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.linuxbrew/bin:/home/linuxbrew/.linuxbrew/bin:$PATH"
command=$1
shift
exec syncthing "$command" \
  --config="${XDG_CONFIG_HOME:-$HOME/.config}/syncthing" \
  --data="${XDG_STATE_HOME:-$HOME/.local/state}/syncthing" "$@"
