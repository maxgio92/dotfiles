---
description: Create a task from an outcome, then research, update, and review it for readiness (create-task, research-task, update-task, review-task) in one run
---

Run the task lifecycle up to the readiness verdict for this outcome:

$ARGUMENTS

The arguments are the outcome and the optional target, exactly as
`create-task` takes them (a Linear team, `owner/repo` for a GitHub issue, or a
path for a local task file). Blank means stop and ask for the outcome.

This command runs in the main session and sequences the step commands. What
it adds: passing the key and the fixes table between steps, keeping the
research report on disk per `review-reports`, the destination-dependent
approval rule below, and the pass cap. Each step stays usable alone through
its own command. Follow each step's procedure as written there; do not
paraphrase it here.

## Steps

1. `create-task`: run its procedure with `$ARGUMENTS`. It confirms the body
   once with the user, then files the task. Record the key it returns. This
   command handles a single task: when create-task splits the outcome into a
   parent with children, run steps 2 to 4 once per child and report `Ready`
   only when every child is `Ready`. On the user's own tracker this
   confirmation is the only prompt in the run. On a repository the user does
   not own, create-task's Tracker Writes rule applies and every later write
   goes through `publish` after approval.
2. `research-task`: run the skill on the new key. Keep the report on disk per
   the `review-reports` skill and record its path.
3. `update-task`: run its procedure on the key with the research report as
   the session decisions to fold in.
4. `review-task`: run its procedure on the key. Read the verdict: `Ready`,
   `Ready with fixes`, or `Not ready`, plus the P0/P1/P2 fixes table.

## Verdict handling

- `Ready`: stop. Report the key, the verdict, and the research report path.
- `Ready with fixes` or `Not ready`: run steps 2 to 4 again, scoped to the
  fixes table only (research the gaps it names, fold the answers in, review
  again). At most two more passes. Later passes append a dated follow-up
  section to the first report rather than writing a new file, so the report
  path stays the same. After three verdicts without `Ready`, halt and show
  the last fixes table with the key and the report path.

`implement-task` is not chained; take the key to it by hand once the verdict
is `Ready`. A later `--implement` flag may add that step.

## Delegation

The global rules apply: any worker launched for a step does its assigned
work, returns directly here, and launches no agent. If a step needs another
specialist, the worker says so and this command routes it.
