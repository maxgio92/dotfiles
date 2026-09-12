---
description: "Judge whether a tracked task (Linear issue, GitHub issue, or local file) is ready to implement: verdict, P0/P1/P2 fixes table, metadata check, gaps; read-only"
---

## Review Task

Judge one tracked task for implementation readiness and report what would have to change. This command reads; it never writes.

### Input

`$ARGUMENTS` is a task reference. It is one of:

- a Linear issue key or URL
- `owner/repo#N` or a GitHub issue URL
- a filesystem path to a local task file

### Setup

1. Load the `task-tracker` skill to resolve the tracker and read the task, and the `sizing` skill for the Metadata check.
2. Read the task in full: body, status, type, area, priority, estimate, assignee, parent, children, comments, and linked documents. For a parent, read each child's title and status.

### Process

Judge each body heading for three things: presence, specificity (names files, commands, values, or owners rather than describing them), and testability (a reviewer could check it without asking the author).

Headings to judge: `Outcome`, `Why`, `Problem`, `Context`, `Scope` (both `In scope` and `Out of scope`), `Requirements`, `Success Criteria`, `Validation`, `Dependencies`, `Evidence`. A parent adds `Shared decisions` and `Child issues`.

Assign each finding a priority:

- P0 blocks implementation: a missing or untestable `Outcome`, `Scope`, or `Success Criteria`; a `Dependencies` entry that is not met; a child order that cannot be satisfied.
- P1 misleads or leaves ambiguity: a `Requirements` line that admits two readings, `Validation` with no command, `Evidence` that does not support the section it grounds, a `TBD` or `TODO` in a section that drives implementation.
- P2 polish: wording, ordering, a duplicated fact, a link that could be a permalink.

Derive the verdict from the table:

- `Not ready` when any P0 exists
- `Ready with fixes` when only P1 or P2 findings exist
- `Ready` when the table is empty

### Output

Output these sections in this order; the verdict appears once, in its section.

```markdown
## Verdict
Ready | Ready with fixes | Not ready

## Fixes
| Priority | Heading | Finding | Suggested fix |
|----------|---------|---------|---------------|

## Metadata
- Status: <current status and whether it fits the body>
- Type: <value or missing>
- Area: <value or missing>
- Priority: <1 Urgent to 4 Low, and whether the Why supports it>
- Estimate: <value on the `sizing` scale, and whether the Scope supports it; parents carry none>
- Assignee: <value or unassigned>
- Parent order: <position in the parent's `Child issues` list and its `Depends on <n>` marker, or n/a>

## Gaps
- Missing evidence: <sections with claims and no path, link, or output>
- Unresolved markers: <`Open questions`, `TBD`, `TODO` entries>
- Unlisted dependencies: <tasks, access, or decisions the body relies on but does not list>
```

Keep the `Fixes` table sorted P0 first. Write `None` under a `Gaps` bullet with nothing to report. Suggest a fix the author can apply with `update-task`.

### Constraints

- Read-only. Never edit the body, add a comment, change status, labels, assignee, or estimate, or touch a child.
- Never invent a label, status, or estimate in the Metadata section; report what the tracker holds and what the body supports.
- Judge the text as it stands. Session knowledge may inform a suggested fix but does not excuse a missing section.
- A tracker read failure is one reported line and ends the review.
