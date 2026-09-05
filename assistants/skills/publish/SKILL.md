---
name: publish
description: "The single choke point for posting approved drafts: PR comments and replies, issues, and Slack messages. Use when posting, publishing, or sending a draft the human approved; never before that approval, since every other skill drafts and stops."
---

# Publish

Post an approved draft to its destination, verbatim. This is the only skill
that publishes; drafting skills (`pr-review-message`, `slack-message`, the
`upstream-contribution` staging step) produce text and stop.

## Contract

1. Input: the approved draft and its destination (PR thread, issue, Slack
   channel or thread). Both must come from the human's approval, not from
   inference.
2. Post the draft exactly as approved. Any edit, even a typo fix, invalidates
   the approval: go back with the revised draft instead.
3. Verify: fetch the posted artifact back (permalink, message timestamp) and
   report it. A post you cannot fetch is not done.
4. One approval covers one post. A batch approval must name each item.

## Destinations

- PR comment or reply: `gh pr comment` / `gh api` on the review thread; reply
  in the thread the comment lives in.
- Issue: `gh issue create` or `gh issue comment`.
- Slack: the Slack send tools, or the repository's posting helper if one
  exists.

Permission gates (the Claude Code ask list, pi's outward-write-gate, the codex
sandbox) fire on these commands by design; the prompt they raise is the
approval surface, not an obstacle to work around.
