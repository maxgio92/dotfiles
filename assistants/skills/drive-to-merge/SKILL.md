---
name: drive-to-merge
description: "Own a pull request on a repository the user controls from the moment it exists until it is merged and cleaned up: watch checks on the exact head, fix red checks, rebase on conflicts, answer review rounds, re-request approval, report merge-ready, then delete branches and worktrees and close the task. Use after publish creates or updates a PR, when the user asks to babysit, watch, or land a PR, or when a PR of theirs is stale, red, or conflicting."
---

# Drive to merge

A pushed pull request is not finished work. Completion is the merge, followed
by local and remote cleanup and the task moved to `done`. This skill owns that
stretch for repositories the user controls; `upstream-contribution` owns it for
repositories they do not.

## Entry

- Input: the PR URL. Read `number`, `headRefOid`, `baseRefName`, `isDraft`,
  `mergeable`, `mergeStateStatus`, `reviewDecision`, `reviewRequests`, and
  `statusCheckRollup` with `gh pr view --json`. Never `gh api`; reads that
  `gh` cannot express go through `gh-api-safe`.
- Confirm the head before every judgement. Checks, reviews, and conflicts
  count only for the current `headRefOid`.
- An open PR with pending or red checks, a conflict, or an unanswered review
  is active work, never an approval queue. Do not park on it.

## Loop

Poll every 2 minutes for the first 10 minutes after a push, then every 5.
Wait inside tool calls of at most 60 seconds; a session cannot wake itself,
so when the runtime ends the turn, say that watching is paused and how to
resume (`/watch-pr <url>` or `/loop /watch-pr <url>`). Report changes only.

Each pass classifies the PR into exactly one state and acts on it:

1. **Merged.** Go to Cleanup.
2. **Conflicting** (`mergeable` CONFLICTING, or a local dry run
   `git merge-tree --write-tree <base> <head>` lists conflicts). Rebase onto
   the base branch in the PR's worktree, resolve, rerun the repository's
   build, test, and lint gates in full (an auto-merge is a code change), and
   re-review the diff against the merge base
   (`git diff $(git merge-base <base> HEAD)...HEAD`), not against HEAD. Push
   with an explicit refspec. A rebase dismisses approvals: re-request each
   dismissed approver and, when the channel thread exists, tell them why in
   one sentence through `publish`.
3. **Red check on the current head.** Read the failing job log. A failure
   caused by the change goes through the implement-and-review loop with the
   log quoted; a flake or an infrastructure failure (rate limit, stale
   reconciler mark, runner loss) is named as such and re-run once with
   `gh run rerun --failed`. Main-side drift is fixed by rebasing, never by a
   re-run, because a re-run reuses the original merge ref.
4. **Review round.** Fetch every review body and inline comment without
   truncation. Classify each ask: fix, decline with a reason, or question.
   Fixes go through the implement-and-review loop, then one push. Replies
   are drafted with `pr-review-message` and posted through `publish`, one
   inline reply per finding, citing the fix commit. Re-request the reviewer.
5. **Pending checks or pending review.** Wait one interval. Nothing to say.
6. **Approved, green, mergeable.** Report `merge-ready` once, with the exact
   command:

   ```
   gh pr merge <number> --repo <owner/repo> --squash --delete-branch
   ```

   The merge is the user's decision unless they said otherwise for this PR.
   Keep watching: main can move and turn the PR conflicting again.
7. **Blocked on a human** (a design question, a required reviewer who has not
   answered, a label only an owner can add). Say who and what, once, and keep
   watching.

## Approval boundary

Once the user approved the PR's creation, fix pushes to that branch are part
of the same work and need no fresh approval. Fresh approval is needed for the
merge itself, each new outward comment or Slack message, a force-push that
rewrites a reviewed branch, a base retarget, and a draft flip either way.
Under a standing blanket approval for pushes and posts, those prompts are
answered by the coordinator; the merge still comes back to the user unless
the blanket approval named merges.

## Cleanup

After the merge, in this order:

1. Delete the remote branch on every remote that carried it (`origin`, the
   fork, `upstream`) when `--delete-branch` did not, with
   `git push <remote> --delete <branch>`.
2. Delete the local branch and any stacked or fold branches that are fully
   merged (`git branch --merged <base>`).
3. Remove the dedicated worktree (`git worktree remove <path>`) unless it is
   the coordinator's own or the user asked to keep it. Never remove a
   worktree with uncommitted changes; report it instead.
4. Delete the plan directory under `${TMPDIR:-/tmp}/agent-plans/<key>` if it
   still exists.
5. Move the task to `done` and post the durable record (what changed, where,
   validated how, what remains) per `task-tracker`. File follow-ups the PR
   left behind as tasks, or name them in the durable record when the user
   has not asked for tasks.
6. Advertise the merge in the team channel only when no earlier post covers
   the same goal (search the channel by ticket and by PR); a post exists for
   most PRs already, so the default is no post.

## State reporting

At every stop, one line per PR: URL, head sha, state from the list above,
approvers and dismissed approvers, unfinished checks by name, and the next
action with its owner. Never report `done` for an open PR.
