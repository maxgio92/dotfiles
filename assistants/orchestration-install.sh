#!/usr/bin/env bash
set -euo pipefail

dotfiles_root=$(cd "$(dirname "$0")/.." && pwd)
install -Dm755 "$dotfiles_root/bin/agent-work" "$HOME/.local/bin/agent-work"

link_file() {
    local source=$1 target=$2
    mkdir -p "$(dirname "$target")"
    if [[ -L "$target" ]]; then
        [[ $(readlink "$target") == "$source" ]] || {
            echo "Refusing to replace $target" >&2
            return 1
        }
    elif [[ -e "$target" ]]; then
        echo "Refusing to replace $target" >&2
        return 1
    else
        ln -s "$source" "$target"
    fi
}

for skill_root in "$HOME/.claude/skills" "$HOME/.agents/skills" "$HOME/.pi/agent/skills"; do
    link_file "$dotfiles_root/assistants/skills/orchestrating-work" "$skill_root/orchestrating-work"
done

for name in orchestrate spawn-work check-work steer-work; do
    for command_root in "$HOME/.claude/commands" "$HOME/.codex/prompts" "$HOME/.pi/agent/prompts"; do
        link_file "$dotfiles_root/assistants/commands/$name.md" "$command_root/$name.md"
    done
done
echo "Installed orchestration skill, commands, and agent-work"
