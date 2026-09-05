# Commits, PRs, and issues

All artifacts here are staged locally or drafted verbatim; nothing goes
outward without the approval gate in SKILL.md.

## Commits

- Subjects: Conventional Commits, one line, about 60 characters or
  fewer.
- Bodies describe the behavior change, never "address review".
- No AI trailers or signatures anywhere.
- One logical change per commit; a review-round fixup that the
  maintainer will see as a separate commit gets its own subject.

## PR and issue titles and bodies

- Titles: one line, about 60 characters or fewer.
- Bodies: see `communication.md` for register.
- Code references: commit-pinned permalinks, never branch links or bare
  `file:line` text.
- External artifacts (releases, assets, docs): always linked.

## Staging for approval

Return to the user, in one report:

- the local commit shas and their subjects,
- the drafted PR, issue, or reply body verbatim,
- the exact push or post command to run,
- for trivial edits handled without the review loop: the diff itself.

Mark the report "awaiting human approval". Execute only the writes the
user then approves, exactly as staged.
