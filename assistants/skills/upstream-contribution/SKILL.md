---
name: upstream-contribution
description: "Drive a contribution to a repository the user does not control: scope maintainer asks, run the implement-and-review loop, gate before commit, stage every outward write for explicit human approval, watch CI to green before replying. Use for any upstream GitHub work: opening an issue or PR, addressing review rounds, rebasing a contribution branch, or replying to a maintainer."
---

# Upstream Contribution

Own the lifecycle of a contribution to a repository the user does not
control. Sequence the work, verify claims, and stage maintainer-facing
artifacts; delegate implementation and review. Do not hand-patch
non-trivial code yourself: route it through the implement-and-review
loop (implementer writes the smallest correct change, adversarial
reviewer vets it, implementer applies confirmed blocking findings) and
relay follow-up findings back through that loop rather than patching
around it.

## Reference files

Read the file for the phase you are in; do not front-load all three.

- Drafting any maintainer-facing text (PR body, review reply, issue):
  read `references/communication.md`.
- Creating commits, PRs, or issues: read `references/tracking.md`.
- After a push: CI watching, review rounds, rebases: read
  `references/progression.md`.

## The loop

For each maintainer review round:

1. Fetch the review in full (body plus inline comments). When a claim
   is checkable in one command (a red build, a missing symbol), check
   it before planning.
2. Classify each ask: trivial edit (handle directly, but include the
   diff in the awaiting-approval report so the human approval doubles
   as review), implementation (run implement-and-review with the ask
   quoted verbatim plus repository context), design disagreement (push
   back once with evidence, then follow the maintainer's call).
3. Rebase onto the target branch when asked or conflicted; a rebase is
   a code change, so re-review and rerun the gate on the result (see
   `references/progression.md`).
4. Run the ordering invariants below, draft the reply, and return
   everything staged (local commit, drafted reply, exact push command)
   marked "awaiting human approval".
5. Once a push is approved and executed, watch CI to green on the
   pushed head before the reply goes out; then watch the PR until the
   next round or merge.

## Hard ordering invariants

Ordered gates. Never skip forward.

1. **Gate before commit.** Run the repository's full check suite,
   including every build flavor CI builds (Go build tags, feature
   flags, CI matrix variants). Trust the implementer's reported gate
   results for code it changed; rerun the gate yourself only for code
   you changed directly (trivial edits, rebase resolutions). A flavor
   that cannot compile locally is a BLOCKED gate: stop and ask the
   user; grep or by-inspection evidence does not substitute for
   compilation.
2. **No outward writes without explicit human approval.** Never push
   commits, create PRs or issues, post comments or replies, or request
   review on your own. There is no standing approval. Stage the
   artifact instead: commit ready locally, reply or issue body drafted
   verbatim, push command stated, marked "awaiting human approval".
   Execute an outward write only when the human approved that specific
   write.
3. **CI green before any maintainer contact.** After a push, poll the
   checks until every non-skipped check passes on the exact pushed
   head. Never reply, request re-review, or claim "done" while CI is
   pending or red. If CI goes red, tell the user first, fix, and
   restart from gate 1.
4. **Verify every claim against the remote, not the local tree.**
   Before a reply cites a sha, a fix, or a test, confirm it exists on
   the pushed head. A reply that promises future work the push already
   contains, or cites an orphaned sha, is wrong: rewrite it.

## Reporting

Report the state machine position (gated, awaiting approval, pushed,
CI pending, CI green, replied), the exact shas involved, and any
blocked gate or unverified claim. Never report success while a gate is
open.
