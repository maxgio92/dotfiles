---
description: "Implement a tracked task (Linear issue, GitHub issue, or local file) end to end: branch, claim, run implement-and-review per child, record, commit with a Refs trailer"
---

## Implement Task

Take one tracked task, or a parent with children, from `ready` to committed code on a branch. This command runs in the caller's context and drives the work itself.

### Input

`$ARGUMENTS` is one of:

- a Linear issue key or URL
- `owner/repo#N` or a GitHub issue URL
- a filesystem path to a local task file

When it is blank, ask once which task to implement, then ask nothing further.

### Plan Key

`<key>` identifies the task on disk and in Git:

- Linear: the lowercased issue key (`ful-123`)
- GitHub: `owner-repo-N` with `/` and `#` flattened to `-`
- Local file: the current branch name with `/` flattened to `-`

The plan lives at `${TMPDIR:-/tmp}/agent-plans/<key>/plan.md`. It is never inside the repository and never committed.

### Steps

1. Load the `task-tracker` skill. Resolve the argument to a tracker. Read the task and its children: body, status, assignee, parent, comments, linked research report.
2. Order the cohort from the parent body's `Child issues` list and its `Depends on <n>` markers. A child runs only after every child it depends on has a commit. A single task is a cohort of one.
3. Branch and claim.
   - Reuse the current checkout when its branch is not `main` or `master`.
   - Otherwise create one: `git switch -c <lowercased key>` for Linear, `gh issue develop <n> --checkout` for GitHub.
   - A local task needs an existing branch that is not `main` or `master`. When there is none, stop and say so.
4. Per task, first check it is the user's own or unassigned per `task-tracker` Ownership (stop and ask otherwise), then claim it: assign it to the current user and move it to `started`, using the mechanics the `task-tracker` reference for that tracker describes. Then run the loop. Call:

   ```
   Workflow({name: "implement-and-review", args: {task: "<repository path first, then the task body: Outcome, Requirements, Scope, Success Criteria, Validation, Evidence, and the parent's Shared decisions when it has one>", plan: true, research: "<the task's research report text when one exists>", planPath: "<resolved absolute plan path>", repoRoot: "<absolute repository root>"}})
   ```

   `planPath` is the resolved absolute path: expand `${TMPDIR:-/tmp}` before calling, since Workflow args are JSON and not shell. `repoRoot` is the absolute path of the checkout from step 3; the workflow uses it to refuse a `planPath` inside the repository. Omit `research` when the task has no report. When the Workflow tool is absent, fall back to the Agent-tool loop described in `implement-review`: peter implements, dastardly reviews the diff, peter applies confirmed blocking findings, up to three rounds. Worker rule for that path: every agent this command launches does its own assigned work, returns directly here, and launches no agent.
5. Validate in this context. First check the review gate: the Workflow result must have `converged: true` and `unverified: false`; on the Agent fallback, the final dastardly round must report no blocking findings. Then compare the changed files against the task's `Success Criteria` and `Scope`. Treat a failed gate like a gap: run one more `implement-and-review` round whose task text is the original task text (repository path first) followed by the open blocking findings or the gap, so the diff capture still finds the repository. If the gate or the comparison still fails after that round, stop, leave the working tree uncommitted, and report what is open. Do not commit before both pass.
6. Write the durable record: 2 to 4 sentences on what changed, where, how it was validated, and what remains. Post it as the `task-tracker` reference for that tracker says: a comment on Linear or GitHub, a section appended to a local file.
7. Commit here. Stage each changed file with a path-limited `git add -- <path>`. Use a conventional commit message with a `Refs:` trailer in the form the tracker reference's Branch link section gives. The main session commits without approval; subagents never commit.
8. Delete `${TMPDIR:-/tmp}/agent-plans/<key>` after the commit.
9. Leave the issue in `started`. Return to step 4 for the next child in the order from step 2. Stop after the final commit.

### Constraints

- Never push and never open a PR. Point the user at the `open-pr` skill for repositories they own, or `upstream-contribution` for repositories they do not control.
- `git status` must show no plan files at any point.

### Output

Per task: the key, the branch, the commit hash, and where the durable record was posted (comment URL or file path). Close with the skill to use for the PR.
