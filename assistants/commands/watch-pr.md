---
description: Drive one of the user's own pull requests to merge and cleanup
---

Load the `drive-to-merge` skill and run one pass of its loop on `$ARGUMENTS`,
a PR URL or number. Blank means the PR of the current branch, resolved with
`gh pr view --json url`.
Classify the PR into one state, act on it, and report one line per PR in the
skill's State reporting format.
Under `/loop`, each firing is one pass; do not wait for the next interval
inside the command.
