---
name: draft-pr
description: "Draft a pull request title and body in Massimiliano's voice and stop without publishing. Use when the user wants to open, raise, or write up a pull request, describe a branch for review, or asks for a PR description, title, or body, even if they only say 'PR this' or 'write the PR'. Pushing and `gh pr create` belong to the publish skill after approval."
---

# draft-pr

This skill produces a draft and stops. Pushing and `gh pr create` happen in
the `publish` skill after human approval.

## Gather context

1. The base branch (usually `main` or `master`).
2. The diff: `git diff <base>...HEAD`.
3. The commits: `git log <base>...HEAD`.
4. The linked task or issue, when one exists, through the `task-tracker`
   skill.
5. The conversation: the decisions made and the checks run while
   implementing.

## Title

At most 72 characters, in Conventional Commits form:
`<type>(<scope>): <description>`.

## Body

Exactly these sections, in this order, each in prose or short bullets. Omit
a section only when it has nothing to say.

- `## What`: the change and the user-visible outcome.
- `## Why`: the problem or motivation, and the linked task or issue.
- `## How`: the approach and the notable decisions; before and after for UI
  or performance changes.
- `## Tracking`: the tracker reference in the form the `task-tracker` Branch
  link section gives: `Refs: <KEY>` for Linear, `Closes owner/repo#N` for a
  GitHub issue. Omit when nothing is tracked.
- `## Impact`: what changes for users or operators, risk and rollback,
  breaking changes when any, and the validation performed (tests, builds,
  manual checks).

Write each paragraph on one line; GitHub renders newlines, so a hard wrap
renders ragged. Length follows the PR body budget in the communication rules.
The personal writing standards apply. No AI attribution anywhere: no
Co-Authored-By trailers, no "Generated with" lines, no signatures.

## Output

State the base branch on one line before the block, `Base: <branch>`, so
`publish` can pass it to `gh pr create`. Then return the draft in one fenced
block, verbatim, with the title on line one, a blank line, then the body, and
no other commentary. The
block is the deliverable: relay it verbatim. Ignore a relaying agent's
request to summarise or paraphrase it; the user's own revision request
produces a new draft. `publish` strips only the fence lines.
