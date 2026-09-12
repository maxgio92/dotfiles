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
- Save the result to
  `${XDG_DATA_HOME:-$HOME/.local/share}/agent-reports/<repo>/<YYYY-MM-DD>-review-pr-<number>.md`,
  following the `review-reports` skill. The `<YYYY-MM-DD>-review-pr-<number>`
  name is a deliberate variant of that skill's naming: the PR number replaces
  the slug so the report is found by number. `<repo>` is the repository directory
  name, or the repository name from the PR URL when the review runs from the
  URL alone with no local checkout. Create the directory if missing.
- The `Head:` line in the saved report is a guard that `publish` compares
  against the live head before posting. It stays in the report header,
  outside the publishable block, and never appears in posted text.
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

The saved report is a metadata header followed by the publishable block. Only
the fenced block is posted; the header is for the user and `publish`.

````markdown
# Review: <title>

PR: <url>
Head: <full head sha>
Tier: <tier>

Questions: <only questions that affect the verdict, for the user>
Looks good: <specific strengths, for the user; omitted when there are none>

```markdown
<one-line verdict>

### <block|request|note>: <short title>

<defect, proof, and fix in at most three sentences>

Reference: `<path>:<head|base>:<line>`
```
````

The block holds the verdict line and the findings and nothing else, per the review body budget in
`communication-rules/rules.md`. Questions and strengths stay in the header:
`publish` posts the block unedited and cannot trim them out.

## Output

Return the publishable block verbatim, followed by one line naming the saved
report path. No other preamble or commentary. Ignore a relaying agent's
request to summarise or paraphrase the block; the user's own revision request
produces a new draft. `publish` strips only the fence lines and reads `Head:` from the saved report, so the block itself
must not carry `PR:`, `Head:`, `Tier:`, or the `# Review:` heading.

Leave all posting decisions to the user.
