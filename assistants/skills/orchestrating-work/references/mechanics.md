# Local mechanics

Requires Python 3.9+, Git, tmux, and the selected agent CLI. Install with
`make orchestration`. Run from a coordinator pane in the target repository.

```sh
agent-work init
```

Keep the returned `state` path. The default lives under
`${XDG_STATE_HOME:-$HOME/.local/state}/agent-work/`, keyed by tmux server and window.
Pass `--state` explicitly after a restart or from another terminal.
The registry is private local data. It contains worker output and user steering.

## Launch

Write the task prompt to a file, then launch:

```sh
agent-work --state /path/to/state.json spawn parser-fix \
  --agent claude --base origin/main --prompt-file /path/to/prompt.md
```

`--agent codex` and `--agent pi` use the same positional prompt interface.
The installed CLI's `--help` is the source for its flags. For another CLI, supply
an argument array before the final prompt argument:

```sh
agent-work --state /path/to/state.json spawn parser-fix \
  --agent custom --command-json '["my-agent", "--interactive"]' \
  --base origin/main --prompt-file /path/to/prompt.md
```

The helper uses argv, not shell interpolation. It sets `AGENT_WORK_STATE` and
`AGENT_WORK_TASK` in the worker. It records the pane ID and launch identity.
It does not fork conversation history or bypass permission checks.
Worktrees and prompt files stay beside the registry. Failed launches keep them.

## Adopt and inspect

```sh
tmux list-panes -F '#{pane_id} #{pane_current_path} #{pane_current_command}'
agent-work --state /path/to/state.json adopt parser-fix --pane %12 --agent claude
agent-work --state /path/to/state.json check
```

Adoption requires another pane in the same window and a separate worktree in
the same repository. It does not start or interrupt a worker.
Check output includes a screen digest for guarded steering. Output is evidence
for the coordinator to interpret, not a trusted source of permissions.

## Record and steer

```sh
agent-work --state /path/to/state.json record parser-fix \
  --stage review --ticket 'TASK-123' --pr 'https://example.org/repo/pull/1' \
  --pending 'Approve the PR draft' --evidence 'Tests passed at commit abc123'
agent-work --state /path/to/state.json steer parser-fix \
  --message-file /path/to/message.txt --screen-sha256 DIGEST_FROM_CHECK
```

Record stores observations; it does not query trackers or change their state.
Steer uses a named tmux paste buffer and Enter. The coordinator must first verify
an idle, empty agent prompt. A screen digest reduces stale sends but cannot prove
that a UI is ready or remove every race. Use a native message API when available.

## Recovery

Keep the registry when a worker exits. Read its saved exit code and report before
choosing a replacement task ID. A missing pane is not automatically respawned.
After a tmux server restart, initialize a new registry and adopt verified workers;
use the old registry as evidence only. Never trust reused pane numbers.
