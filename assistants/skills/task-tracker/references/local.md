# Local file

Mechanics for the `task-tracker` roles on Markdown task files on disk. Section order matches `linear.md` and `github.md`.

## Resolution

A filesystem path resolves here. There is no tracker: the file is the body template and the record. Read it in full before any edit and write it back with the existing text intact.

Cohort layout: the parent is `00-<slug>.md` and each child is `NN-<slug>.md` (`01-`, `02-`, and so on) in the same directory. Frontmatter carries `title`, `labels`, `priority`, and `estimate`. It never carries a status.

## New

Create the file with the frontmatter above and the task body template that the `create-task` command defines (Outcome, Why, Problem, Context, Scope, Requirements, Success Criteria, Validation, Dependencies, Evidence). Pick the next free `NN-` prefix for a child.

## Ready

No-op. Say that a local file has no status and continue.

## Started

No-op. Say that a local file has no status and continue.

## In review

No-op. Say that a local file has no status and continue.

## Done

No-op. Say that a local file has no status and continue.

## Inactive

Never. A local file is always active; commands proceed.

## Classification

- `type` and `area`: entries in the `labels` frontmatter list. Use the words the directory's other files already use; when none fits, leave the list as it is and say so.
- `priority`: the `priority` frontmatter field, 1 to 4.
- `estimate`: the `estimate` frontmatter field on the `sizing` scale. Parents carry none.

## Parent and order

Order comes from the filename prefix and from the parent's `Child issues` list, one line per child as the child's filename with `Depends on <filename>` where needed. Keep both in agreement. Edit only the `Child issues` block; leave the rest of the parent body untouched.

## Durable record and long research

Durable record: append a `## Record` section to the task file with the record as Markdown. One section per landing, newest last.

Long research (the `long research` role in SKILL.md): a sibling file `NN-<slug>.research.md` next to the task, plus a one-line link under `Evidence` in the task body. Never paste it into the task body.

## Branch link

A local file creates no branch. Use the branch the user already has checked out; when it is the default branch, stop and ask for one. Commit trailer: `Refs: <filename>`.
