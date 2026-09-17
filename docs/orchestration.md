# Agent orchestration

Keep one coordinator in a tmux window. Launch each worker in a new pane and
Git worktree. The coordinator maintains the task table and routes your instructions.

## Install

```sh
git pull --ff-only
make orchestration
```

This installs `agent-work`, the shared skill, and command templates for Claude,
Codex, and Pi. It needs Python 3.9+, Git, tmux, and the selected agent CLI.
Keep `~/.local/bin` on PATH. Restart an agent if it caches its command list.

## Commands

Run these in the coordinator pane:

```text
/orchestrate <plan or path>
/spawn-work <task or outcome> [agent] [base ref]
/check-work
/steer-work <task ID> <instruction>
```

Claude and Pi use these command names. Codex uses `/prompts:orchestrate`,
`/prompts:spawn-work`, `/prompts:check-work`, and `/prompts:steer-work`.
You can also invoke the `orchestrating-work` skill by name in another agent.

The coordinator checks a pane's task and worktree before adopting it.
Each launch starts a fresh process. More than four new workers need approval.

`/orchestrate` repeats checks while work is active. It reads worker output,
checks ticket and PR state, and reports changes or decisions needed.
`/check-work` performs one pass. No daemon or vendor scheduler is installed.
Monitoring pauses if the coordinator stops or the agent runtime ends its turn.

## State and approvals

The registry lives under `${XDG_STATE_HOME:-$HOME/.local/state}/agent-work`.
It holds task IDs, pane identities, worktrees, links, observations, and messages.
Keep it private and out of Git. The coordinator is its only writer.

The task table separates agent activity from ticket, review, and CI state.
An idle worker is not a finished task. A posted PR is not a completed task.
The coordinator checks CI against the current commit and flags missing workers.

Steering uses an agent's message API when available. The tmux fallback checks
pane identity and a recent screen digest before pasting into an idle prompt.
It does not press approval buttons. Some permissions still need your input in
the worker's UI. Approvals apply to the shown action and revision only.

`/work-on` remains a separate task-readiness command. Ask for implementation,
PR drafting, or publication as later stages when needed.

## Checks

```sh
python3 -m unittest discover -s tests -p 'test_agent_work.py' -v
```

Tests use temporary repositories, a private tmux server, and a fake worker.
They do not launch model sessions or post to trackers.

Skill trigger cases:

| Request | Expected behavior |
| --- | --- |
| Coordinate this plan in separate agent panes | Load the skill and start the coordinator flow |
| Spawn one task using another agent | Load the skill and create a fresh worktree and pane |
| Refresh the worker table | Load the skill and check evidence once |
| Tell task parser-fix to use the existing API | Load the skill and verify delivery to that worker |
| Review this one function | Use the code review workflow, not orchestration |
