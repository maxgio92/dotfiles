---
description: "Create a tracked task (Linear issue, GitHub issue, or local file) from an outcome, with taxonomy, sizing, and a grounded body"
---

## Create Task

Turn an outcome into one tracked task, or a parent with ordered children, and file it.

### Input

`$ARGUMENTS` is an outcome plus an optional target. The target is one of:

- a Linear team or project name
- `owner/repo` for a GitHub issue
- a filesystem path for a local task file

A blank target means infer the target from the session (the repository, the tracker mentioned, the team visible in Linear) and state it in the same confirmation as the body, so the run still asks once.

### Setup

1. Load the `task-tracker` and `sizing` skills before doing anything else.
2. Apply the personal writing standards from the global instructions to every title and body.
3. Resolve the tracker from the target with `task-tracker`. Its reference for that tracker owns every write mechanic used below.

### Process

1. Decide the shape. File a single task by default. Split into a parent with children when the outcome has independently shippable parts; each child must land on its own and leave the repository working.
2. Query the live taxonomy: teams, projects, labels, statuses. Pick from what exists. Never invent a label; when nothing fits, leave the field unset and say so in the report.
3. Classify each task: status (default `new`), type, area, priority (1 Urgent to 4 Low), and estimate on the `sizing` scale. Parents carry no estimate.
4. Order a cohort in the parent body's `Child issues` list. Mark ordering with a `Depends on` marker in the form the tracker reference gives (`<KEY>` for Linear, `#N` for GitHub, the filename for a local file). Never use tracker relations for order.
5. Ground the body with what the session already knows: file paths, permalinks, command output, decisions taken. Prefer a path or link over a description of it.
6. Show the full body once for confirmation. Apply the reply, then file immediately. Do not ask a second time.
7. Report the key (Linear, GitHub) or the path (local file) for each created task.

### Body

Use these headings in this order for every task. A parent adds `Shared decisions` and `Child issues` at the end.

```markdown
## Outcome
What is true once the work lands.

## Why
The pain or opportunity this removes.

## Problem
The gap between today and the outcome.

## Context
Where the work sits: repository, packages, owners, prior work.

## Scope
### In scope
### Out of scope

## Requirements
Behaviour the change must have.

## Success Criteria
Checks a reviewer can run or observe.

## Validation
How to prove the criteria: commands, tests, manual steps.

## Dependencies
Tasks, decisions, or access this needs first.

## Evidence
File paths, permalinks, and session output that ground the sections above.

## Shared decisions
(parent only) Choices every child inherits.

## Child issues
(parent only) Ordered list, one child per line in the tracker reference's form, with its `Depends on` marker where needed.
```

### Local Files

When the target is a directory:

- the parent is `00-<slug>.md`, children are `NN-<slug>.md` in dependency order (`01-`, `02-`, ...)
- a single task is `00-<slug>.md`
- each file starts with YAML frontmatter holding `title`, `labels`, `priority`, and `estimate`; there is no status field
- the body follows the template above

### Tracker Writes

Follow the `task-tracker` reference for the resolved tracker; it owns every write mechanic. Create the parent first so children get its id.

### Constraints

- One confirmation, then file. No further prompts.
- Never invent a label, status, team, or project.
- Parents carry no estimate.
- Order lives in the parent body, never in tracker relations.
- A tracker failure is one reported line; report what was filed and what was not.
