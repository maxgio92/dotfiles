---
name: publish
description: "The single choke point for posting approved drafts: pull requests, PR comments and replies, issues, and Slack messages. Use when posting, publishing, or sending a draft the human approved; never before that approval, since every other skill drafts and stops."
---

# Publish

Post an approved draft to its destination, verbatim. This is the only skill
that publishes; drafting skills (`draft-pr`, `draft-issue`, `pr-review-message`,
`slack-message`, the `upstream-contribution` staging step) produce text and stop.

## Contract

1. Input: the approved draft and its destination (PR thread, issue, Slack
   channel or thread). Both must come from the human's approval, not from
   inference.
2. Post the draft exactly as approved. Any edit, even a typo fix, invalidates
   the approval: go back with the revised draft instead. Never append AI
   attribution (Co-Authored-By trailers, "Generated with" lines, signatures).
3. Verify: fetch the posted artifact back (permalink, message timestamp) and
   report it. A post you cannot fetch is not done.
4. Hand off. A created or updated pull request is not finished work: load
   `drive-to-merge` and continue there until the PR is merged and cleaned up.
5. One approval covers one post. A batch approval must name each item.
6. SHA guard. For a PR comment drafted from a `review-pr` report, read the
   `Head:` line from the saved report file's header (the `review-pr` skill
   keeps it outside the publishable block) and compare it with `gh pr view
   <pr> --json headRefOid`. If they differ, the author pushed during the review: stop,
   report both shas, and do not post. For a reply that cites a commit sha,
   confirm that sha is in `gh pr view <pr> --json commits` on the pushed head.
   The reviewed head sha never goes into a review body; an approved reply
   that cites a fix commit (`fixed in <sha>`) keeps that citation.

## Not publishing

Bookkeeping on the user's own task record is not publishing and does not pass
through this skill: creating the task, editing its body, assignee, status,
estimate, or labels, and posting the durable-record comment on it. The
`task-tracker` skill owns those writes and they need no per-write approval.
Anything that reaches other people stays here: a PR, a review, a comment on
another person's thread, a Slack message, or an issue on a repository the
user does not own goes through this skill after the human approves it.

## Destinations

- PR review-thread reply: `gh-review-reply <review-comment-url> --body-file
  <file>`, so the reply lands in the thread the comment lives in.
- Top-level PR comment: `gh pr comment --body-file <file>`.
- Never a raw `gh api` call for a write, and reads go through `gh-api-safe`;
  the two commands above are the only paths for PR comments and replies.
- Issue: `gh issue create --title <line one> --body-file <rest>` for a
  `draft-issue` block, whose first line is the title and whose remaining
  lines are the body; `gh issue comment --body-file <file>` for a comment.
- Pull request, from a `draft-pr` block (title on line one, body after the
  blank line): push the branch with an explicit refspec, `git push origin
  <branch>`, never a bare `git push` and never `-u`; verify with `git fetch
  origin <branch>` and confirm `git rev-parse HEAD` equals `git rev-parse
  FETCH_HEAD`; then `gh pr create --base <base> --head <head> --title
  <line one> --body-file <rest>`, where `<base>` is the `Base:` line
  `draft-pr` reports before its block, never the repository default by omission. A bare
  `--head <branch>` means the branch on the base repository, so when `origin`
  is a fork of the base repository (an `upstream` remote, or `gh repo view
  --json isFork,parent`), set `<head>` to `<fork-owner>:<branch>` with the
  owner from `gh repo view --json owner`; a bare `<branch>` only when
  `origin` is the base repository itself. Fetch it back with `gh pr view
  --json url,baseRefName,headRepositoryOwner,headRefName,headRefOid`, confirm
  the base, the head owner, and that `headRefOid` equals `git rev-parse
  HEAD`, and report the URL. `gh pr create --web` with the same `--base`,
  `--head`, title, and body is the alternative when the user wants to finish
  in the browser. Then continue under `drive-to-merge`; the URL is a
  checkpoint, not the end.
- Another person's Linear issue: `save_comment`, or `save_issue` for a body or status change the owner asked for.
- Slack: the Slack send tools, or the repository's posting helper if one
  exists.

Permission gates (the Claude Code ask list, pi's outward-write-gate, the codex
sandbox) fire on these commands by design; the prompt they raise is the
approval surface, not an obstacle to work around.
