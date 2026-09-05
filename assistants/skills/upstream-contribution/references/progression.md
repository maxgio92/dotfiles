# Progression: CI, review rounds, rebases

## CI watching

- After an approved push, poll the PR checks (`gh pr checks`) until
  every non-skipped check passes on the exact pushed head; confirm the
  head with `gh pr view --json headRefOid`.
- CI red: tell the user first, then fix and restart from gate 1 in
  SKILL.md. Never reply to the maintainer while CI is pending or red.
- CI green: release the staged reply (with approval), then watch the PR
  for maintainer activity until the next round or merge.

## Review rounds

- Fetch review bodies and inline comments without truncation
  (`gh pr view`, `gh api`).
- Classify each ask per the loop in SKILL.md before touching code.
- Track which findings each pushed commit addresses so replies can cite
  the right sha per finding.

## Rebases

- A maintainer asking for conflict resolution is asking for a pushed
  resolution; a local rebase the remote cannot see does not count as
  done.
- After any rebase, rerun gate 1 in full: an auto-merge is a code
  change. Check every call site of symbols whose signatures the branch
  changes, including files excluded from the default build.
- Re-review the result. Diff against the merge base of the target
  branch (`git diff $(git merge-base <target> HEAD)...HEAD`), not
  against HEAD: after the rebase is committed the working tree is
  clean, and a diff against HEAD is empty, which makes a review pass
  vacuously.

## State reporting

At every stop, report the position (gated, awaiting approval, pushed,
CI pending, CI green, replied), the shas involved, and any blocked gate
or unverified claim.
