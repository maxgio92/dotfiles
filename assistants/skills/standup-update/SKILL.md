---
name: standup-update
description: Draft the Example-Team daily standup reply (Moved, Today, PRs waiting on review, Docs blocked, Ask) from Claude Code session logs and open pull requests. Use when the user asks for a standup, daily update, status for the standup thread, or "what did I do yesterday", or shares a Example-Team Daily Standup Slack link, even if they only say "answer the standup".
---

# Standup Update

Draft the standup thread reply from evidence: session logs, GitHub, and the tracker. This skill drafts and stops; posting goes through `publish` after approval.

## Window

Cover activity since the start of the previous working day (Monday covers Friday through Sunday). Use local time, ISO format, e.g. `2026-10-13T00:00:00`. A date or range in the request overrides this.

## Gather

Run these in parallel.

1. **Sessions.** Run `scripts/sessions-since.sh <window start>`. It prints one block per Claude Code session: `cwd | branch | short id | start -> end`, then `U`/`A` lines (user prompts, assistant replies) and `PR` URLs the session touched. It skips subagent sidecars and any transcript containing `[standup-update]`. If the output exceeds ~200 lines, hand it to one general-purpose subagent and ask for one line per project: what moved and what is in progress.
2. **Session journal.** If `$NOTES_REPO/notes/<date>-sessions.md` exists for days in the window, read it (`NOTES_REPO` comes from `~/.config/notes-repo.env`, default `~/notes`). It covers Codex and Pi sessions too.
3. **Open PRs.** `gh search prs --author=@me --state=open --updated ">=$(date -d '30 days ago' +%F)" --json url,title,isDraft,repository --limit 50`. The `--updated` filter drops stale PRs nobody is working on. For each non-draft PR, `gh pr view <url> --json reviewDecision,reviewRequests,latestReviews`.
4. **Merged PRs.** `gh search prs --author=@me --merged --merged-at ">=<window start date>" --json url,title`.
5. **Tracker.** If Linear is available, list the user's issues updated in the window and the issues they created in it. An issue counts as done only when its `completedAt` falls in the window; `updatedAt` moves on any edit, so a bulk relink makes old issues look fresh.

## Map evidence to fields

- **Moved:** one line per project (repository or Linear project), named by outcome: merged, opened, reviewed, filed, decided. Drive it from later prompts and final assistant replies, not session titles. Fold review-only work into one line.
- **Today:** what the latest sessions left unfinished, plus in-progress tracker issues. One line.
- **PRs waiting on review:** non-draft PRs with `reviewDecision` of `REVIEW_REQUIRED` or empty and no approval. Give the link and who is needed: `reviewRequests` (team or login), else the repository's usual reviewers from `latestReviews`. Skip PRs that are approved or have changes requested; those wait on the user.
- **Docs blocked:** design docs with open review feedback (draft or open `docs(...)` PRs with comments or changes requested, Linear documents) and docs the sessions say must exist but don't. Never invent a doc.
- **Ask:** one concrete need from someone outside the team, only when the sessions show a blocker (access, a decision, another team's review). Otherwise delete the line.

Report work only: `example-org` repositories and Linear. Leave out the user's personal repositories (every `maxgio92/*` repository, such as `xcover`, `dotfiles`, and `cg-notes`) and sessions under `~/.dotfiles` or the notes repo, in every field.

Delete every line with no evidence, as the template asks. Never guess; ask the user when a field depends on intent the logs can't show (often Today and Ask).

## Output

Follow `slack-message` for register. The channel template overrides the Slack sentence budget and the no-lists rule: each field label on its own line, then one `•` bullet per item, with a blank line between sections so Slack renders each one apart, lowercase, no bold. Cite every pull request as its full bare URL each time it appears, including a repeat in the same line; never a bare number like `70016`. Never put punctuation right after a URL; Slack folds it into the link. Cite Linear issues by key only (`ABC-917`), no URL.

```
Moved:
• <project>: <outcome>

Today:
• <what you're on>

PRs waiting on review:
• <url> (<who>)

Docs blocked:
• <doc>: <what is unresolved>

Ask:
• <one need, from whom>
```

Return the draft in one fenced block, then a short `Sources:` line naming the sessions and PRs behind each field so the user can check it. End with the marker `[standup-update]` so this session is skipped next time.

## Anti-patterns

- Listing sessions or commands instead of outcomes.
- Reporting your own drafting session as work.
- Treating a draft PR as waiting on review.
- Posting without approval.
