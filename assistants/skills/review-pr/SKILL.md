---
name: review-pr
description: Review a peer pull request at junior, senior, or staff depth and save a draft without posting it.
disable-model-invocation: true
allowed-tools: Read, Bash, Glob, Grep
---

# Review Pull Request

Review the requested pull request. Accept a URL,
`owner/repository#number`, or a bare number for the current repository.

Options:

- `--tier junior|senior|staff`: review depth. Default to `senior`.
- `--with-senior`: add a senior pass to a staff review.

## Safety

- Draft only. Never post comments, approve, request changes, merge, or change
  the pull request.
- Save the result to `~/Code/reviews/<number>.md`. Create the directory if
  needed.
- Stop if `gh` is missing, authentication fails, or the repository cannot be
  reached. Report the cause.
- Never include credentials, tokens, or unrelated private data in the draft.

## Gather Evidence

1. Resolve the target and fetch its title, body, author, base branch, head SHA,
   commits, changed files, additions, and deletions with `gh pr view`.
2. Read the full diff and the exact files at the base and head revisions.
   Derive line references from those files, not from diff hunk arithmetic.
3. Read linked issues, tests, public contracts, and nearby code when they affect
   the change.
4. State the goal, scope, and commit structure before judging the change.
5. If the change is too large for a reliable pass, name the parts that still
   need review.

## Review Depth

### Junior

Act as a teacher. Check local correctness, error handling, naming, tests, and
project conventions. Explain why each finding matters and give a concrete fix
or example.

### Senior

Act as a peer. Check correctness, contracts, edge cases, coverage changes,
concurrency, state transitions, migrations, rollback, observability, and scope
drift. Look for duplicated or generated-looking code that bypasses existing
helpers or conventions.

### Staff

Check the precedent set by the change. Trace affected APIs, consumers,
migrations, rollout order, rollback coordination, compatibility, and removal
of old paths. Use `--with-senior` when the request needs both code and system
review.

## Findings

Report only findings supported by the code or pull request evidence. Cite each
one as `path:head:<line>` or `path:base:<line>` after verifying the line in the
exact revision.

Use these labels:

- `block`: reachable correctness, data loss, security, compatibility, or
  rollback failure.
- `request`: a test, observability, maintainability, or design issue that
  should be fixed before merge.
- `note`: a preference or follow-up that does not block the pull request.

For every finding, state the failure case, evidence, impact, and smallest useful
fix. Do not invent concerns to fill a section.

## Draft Format

```markdown
# Review: <title>

PR: <url>
Tier: <tier>

## Summary

<intent, scope, and verdict>

## Findings

### <block|request|note>: <short title>

<evidence, impact, and suggested fix>

Reference: `<path>:<head|base>:<line>`

## Questions

<only questions that affect the verdict>

## What Looks Good

<specific strengths, omitted when there are none>
```

Write the draft, report its path, and leave all posting decisions to the user.
