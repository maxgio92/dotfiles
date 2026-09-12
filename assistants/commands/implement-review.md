---
description: Run the implement-and-review loop (peter implements, dastardly reviews, peter fixes) on a coding task
---

Run the `implement-and-review` workflow with the Workflow tool on this task:

Workflow({name: "implement-and-review", args: {task: "$ARGUMENTS"}})

Pass the task text verbatim, including any repository path it names. Optional
modifiers the user may add: a round cap (pass as `maxRounds`), a base ref for
reviewing committed work (`baseRef`), planning mode for large tasks
(`plan: true`), or a Claude-only review (`reviewer: "claude"`; by default
dastardly reviews through Codex and vets its findings). When the
workflow returns, report rounds, convergence, and
findings; commit the result yourself once converged (subagents never commit),
and stage any push for human approval.

If the Workflow tool is unavailable in this session, fall back to the same
loop with the Agent tool: peter implements, dastardly reviews the diff, peter
applies confirmed blocking findings, up to three rounds.
