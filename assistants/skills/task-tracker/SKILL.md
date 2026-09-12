---
name: task-tracker
description: "Use when a command creates, reads, updates, claims, comments on, or closes a tracked task in Linear, a GitHub repository issue, or a local Markdown task file. Use whenever the user names an issue key like FUL-123, a linear.app URL, owner/repo#N, a github.com issue URL, or a task file path, or says 'create a task', 'update the issue', 'mark it in progress', 'move to review', or 'close the ticket'. Resolves which tracker owns the task and names the status, classification, and record roles every task command shares."
source: https://github.com/wimpysworld/nix-config/blob/main/home-manager/_mixins/agentic/assistants/skills/task-tracker/SKILL.md
---

# Task tracker

One vocabulary for task work across three trackers. This file resolves the tracker and names the roles; each reference carries one tracker's mechanics.

## Resolution

Resolve an existing task from the argument alone. Never infer an existing task's tracker from the current repository or its remote; the remote inference below applies to blank creation targets only.

| Argument | Reference |
| --- | --- |
| Linear key such as `FUL-123`, or a `linear.app` URL | `references/linear.md` |
| `owner/repo#N`, or a `github.com` issues URL | `references/github.md` |
| Filesystem path | `references/local.md` |
| Anything else | Ask which tracker before doing anything |

Read exactly one reference per task. Text after the argument is extra context, not a second target.

Creation targets, for commands that file a new task: a Linear team or project name resolves to `references/linear.md`; `owner/repo` with no `#N` resolves to `references/github.md`; a directory resolves to `references/local.md`. An explicit target always wins.

Work organisation: `github.com/chainguard-dev/`. Edit this line to change it. The Linear team key `FUL` also appears in `references/linear.md` and `sizing`.

A blank creation target is the one inference allowed, and it reads the current repository's `origin` remote (`git remote get-url origin`):

- a remote under the work organisation resolves to `references/linear.md` with the work team
- any other GitHub remote resolves to `references/github.md` with `owner/repo` taken from that remote
- any other remote, or no remote, resolves to `references/local.md` with the file in the repository root, or in the current directory outside Git

State the resolved target in the same confirmation as the body, so the run still asks once. Example: `git@github.com:maxgio92/dotfiles.git` resolves to a GitHub issue on `maxgio92/dotfiles`.

Ownership: a task is the user's own when the current user created it or is assigned to it, resolved at run time, or when it is a local file. Commands that write without approval check this before the first write; on someone else's task they stop and ask.

## Roles

Every task command speaks in these roles. The reference maps each role to its tracker.

| Role | Meaning |
| --- | --- |
| `new` | Where a freshly filed task lands |
| `ready` | Reviewed and ready to pick up |
| `started` | Someone is working on it |
| `in review` | Code is up for review; forward-only from `started` |
| `done` | Landed |
| `inactive` | Finished or abandoned; commands report and stop |
| `type` | What kind of work (bug, feature, chore), from the live taxonomy |
| `area` | Which part of the system, from the live taxonomy |
| `priority` | 1 Urgent, 2 High, 3 Medium, 4 Low |
| `estimate` | The `sizing` scale; load that skill before assigning one |
| `parent and order` | The parent body's `Child issues` list, never tracker relations |
| `assignee` | The current user, resolved at run time |
| `durable record` | The comment posted when work lands: what changed, where, and what was verified |
| `long research` | A body over about 6000 characters; goes to the tracker's long-form home |
| `branch link` | How a branch and its commits point back at the task |

## Shared rules

- Gate on the role's recognition rule, never on a status name. Names differ per workspace; recognition rules do not.
- Resolve the user at run time. Never hardcode a name or ID.
- Draw labels from the live taxonomy. Never invent a label; when none fits, say so and leave the field empty.
- Merge body edits into the existing text. Never replace a body wholesale.
- A tracker failure after code lands is one reported line. It never blocks Git work.

## References

- `references/linear.md`: Linear issues.
- `references/github.md`: plain GitHub repository issues.
- `references/local.md`: Markdown task files on disk.
