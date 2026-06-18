#!/usr/bin/env bash
# Go gate for the peter coding agent.
#   file  (PostToolUse): fast gofmt check on the edited .go file.
#   final (Stop/SubagentStop): build + test + lint when git shows uncommitted .go changes.
# Skips silently when go is missing or the path is not inside a Go module.
# Blocks with exit 2 (stderr fed back to Claude) when a gate fails.
set -uo pipefail

MODE="${1:-file}"
INPUT="$(cat 2>/dev/null || true)"

jq_get() { printf '%s' "$INPUT" | python3 -c "import sys,json;print(json.load(sys.stdin)$1)" 2>/dev/null; }

command -v go >/dev/null 2>&1 || exit 0

module_dir() { # $1=dir; prints module root or empty
  local gomod
  gomod="$(cd "$1" 2>/dev/null && go env GOMOD 2>/dev/null)"
  [ -n "$gomod" ] && [ "$gomod" != "/dev/null" ] && dirname "$gomod"
}

case "$MODE" in
  file)
    fp="$(jq_get "['tool_input'].get('file_path','')")"
    [ -n "$fp" ] || exit 0
    case "$fp" in *.go) ;; *) exit 0 ;; esac
    [ -f "$fp" ] || exit 0
    unformatted="$(gofmt -l "$fp" 2>/dev/null)"
    if [ -n "$unformatted" ]; then
      echo "go-gate: $fp is not gofmt-clean. Run: gofmt -w $fp" >&2
      exit 2
    fi
    exit 0
    ;;

  final)
    root="${CLAUDE_PROJECT_DIR:-$PWD}"
    md="$(module_dir "$root")"
    [ -n "$md" ] || exit 0
    cd "$md" || exit 0

    if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      git status --porcelain 2>/dev/null | grep -qE '\.go$' || exit 0
    fi

    fails=""
    if ! out="$(go build ./... 2>&1)"; then
      fails="${fails}go build failed:\n${out}\n\n"
    fi
    if ! out="$(go test ./... 2>&1)"; then
      fails="${fails}go test failed:\n${out}\n\n"
    fi
    if command -v golangci-lint >/dev/null 2>&1; then
      if ! out="$(golangci-lint run 2>&1)"; then
        fails="${fails}golangci-lint failed:\n${out}\n\n"
      fi
    fi

    if [ -n "$fails" ]; then
      printf 'go-gate: fix these before finishing.\n\n%b' "$fails" >&2
      exit 2
    fi
    exit 0
    ;;

  *)
    exit 0
    ;;
esac
