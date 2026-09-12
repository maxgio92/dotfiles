---
description: "Update a tracked task (Linear issue, GitHub issue, or local file) in place: fold in session decisions and research, resolve open markers, re-check classification, merge never replace"
---

## Update Task

Bring one tracked task up to date with what the session has learned, without losing what the task already says.

### Input

`$ARGUMENTS` is a task reference plus optional context. The reference is one of:

- a Linear issue key or URL
- `owner/repo#N` or a GitHub issue URL
- a filesystem path to a local task file

Anything after the reference is context to fold in: decisions, links, a research report path, a correction.

### Setup

1. Load the `task-tracker` and `sizing` skills before doing anything else.
2. Apply the personal writing standards from the global instructions to every edit.
3. Resolve the tracker from the reference with `task-tracker`. Its reference for that tracker owns every read and write mechanic used below.

### Process

1. Read the task first: body, status, type, area, priority, estimate, assignee, parent, children, comments, and linked documents.
2. Gate on status and ownership. When the status maps to `inactive` per the tracker reference, say so, name the status, and stop. When the task is not the user's own per `task-tracker` Ownership, stop and ask before any write.
3. Promote `new` to `ready`. Leave any other status as it is.
4. Fold in decisions from the current session and from the context in `$ARGUMENTS`. Place each one under the heading it belongs to (`Context`, `Requirements`, `Dependencies`, `Evidence`, `Shared decisions`).
5. Fold in research. Take any research report the session produced or the task links. Summarise its findings under the headings they inform and add the source under `Evidence`. A long report becomes the tracker's long-research artefact per `task-tracker` (a Linear document, a linked file, or an appended section), linked from `Evidence`.
6. Resolve markers. For each `Open questions` entry, `TBD`, and `TODO` in the body: run bounded research (read-only, a few lookups per marker: the repository, the tracker, the linked reports), pick the conservative choice (the smallest change, the existing convention, the option that needs no new access), and record the choice with one line of reasoning under the heading it resolves. Remove the marker. When no lookup settles it, keep the marker and add what was checked.
7. Re-check classification against the live taxonomy: type, area, priority (1 Urgent to 4 Low), and estimate on the `sizing` scale. Change a field only when the body now supports a different value. Never invent a label. Parents carry no estimate.
8. Write without asking for approval: bookkeeping on the user's own task record (step 2) is not publishing under the global rules.
9. Report what changed, one line per section touched, plus one line for each metadata field changed and one for each marker resolved or kept.

### Merge Rules

Merge, never replace. Untouched sections stay byte-identical.

- Linear: use `save_issue` `patch` operations that edit only the affected sections. Do not send a full `description` when a patch can express the change. Follow the reference for the resolved tracker for every other field.
- GitHub: read the body with `gh issue view`, edit only the changed sections, write it back with `gh issue edit --body-file`. Labels and assignee go through their own flags.
- Local file: rewrite only the changed sections and frontmatter fields. Keep the file order and the rest of the text as it was.

Keep headings in the order the `create-task` template uses. Add a missing heading rather than folding its content into another one.

### Constraints

- Never remove a section, a link, or an evidence line the task already had; correct it in place and say why.
- Research for markers is read-only and bounded; it does not open a `deep-research` run. Point the user at `research-task` when a marker needs more.
- Report what was written and what was not.
