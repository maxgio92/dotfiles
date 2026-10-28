---
name: standup-update
description: Draft the user's reply to the team's daily standup thread (Moved, Today, PRs waiting on review, Docs blocked, Ask) from Claude Code session logs and open pull requests. Use when the user asks for a standup, daily update, status for the standup thread, or "what did I do yesterday", or shares a Daily Standup Slack link, even if they only say "answer the standup".
---

# Standup Update

Draft the standup thread reply from evidence: session logs, GitHub, and the tracker. This skill drafts and stops; posting goes through `publish` after approval.

## Configuration

Take the team name and the work GitHub organisation from the prompt when it states them. Otherwise read `~/.config/standup-post.env` if present (`STANDUP_TEAM=...`) and `~/.config/work-context.env` if present (`WORK_GITHUB_ORG=...`). With no team name, say "the team"; with no work organisation, see the work-only rule below.

## Window

Cover activity since the user's last standup post: their latest reply in a previous standup thread, so work finished after it on the same day is not dropped. When there is none in the past week, start at the previous working day's midnight (Monday covers Friday through Sunday). Use UTC in ISO format, e.g. `2026-10-13T10:43:57`, since transcripts and GitHub use UTC. A date or range in the request overrides this.

## Gather

Run these in parallel.

1. **Sessions.** Run `scripts/sessions-since.sh <window start>`. It prints one block per Claude Code session: `cwd | branch | short id | start -> end`, then `U`/`A` lines (user prompts, assistant replies) and `PR` URLs the session touched. It skips subagent sidecars and any transcript containing `[standup-update]`. If the output exceeds ~200 lines, hand it to one general-purpose subagent and ask for one line per project: what moved and what is in progress.
2. **Session journal.** If `$NOTES_REPO/notes/<date>-sessions.md` exists for days in the window, read it (`NOTES_REPO` comes from `~/.config/notes-repo.env`, default `~/notes`). It covers Codex and Pi sessions too.
3. **Open PRs.** `gh search prs --author=@me --state=open --updated ">=$(date -d '30 days ago' +%F)" --json url,title,isDraft,repository --limit 50`. The `--updated` filter drops stale PRs nobody is working on. For each non-draft PR, `gh pr view <url> --json reviewDecision,reviewRequests,latestReviews`.
4. **Merged PRs.** The user's own: `gh search prs --author=@me --merged --merged-at ">=<window start date>" --json url,title`. Also the ones they merged for others, such as bot-opened image requests: `gh search prs --owner <work organisation> --involves @me --merged --merged-at ">=<window start date>" --json url,title --limit 100`, then keep each PR whose `gh pr view <url> --json mergedBy` login is the user. Map each to its tracker issue by package or image name.
5. **Tracker.** If Linear is available, list the user's issues updated in the window and the issues they created in it. An issue counts as done only when its `completedAt` falls in the window; `updatedAt` moves on any edit, so a bulk relink makes old issues look fresh.

## Map evidence to fields

- **Moved:** one line per project (repository or Linear project), named by outcome: merged, opened, filed, decided. Drive it from later prompts and final assistant replies, not session titles. Leave out reviews the user gave on other people's pull requests; the team does not track them.
- **Today:** never empty. List the work planned for today: in-progress and in-review tracker issues, open pull requests still to land, and what the latest sessions left unfinished. When those are thin, add the next `Todo` issue from the team's projects. One bullet per item.
- **PRs waiting on review:** non-draft PRs with `reviewDecision` of `REVIEW_REQUIRED` or empty and no approval. Give the link and who is needed: `reviewRequests` (team or login), else the repository's usual reviewers from `latestReviews`. Skip PRs that are approved or have changes requested; those wait on the user.
- **Docs blocked:** design docs with open review feedback (draft or open `docs(...)` PRs with comments or changes requested, Linear documents) and docs the sessions say must exist but don't. Never invent a doc.
- **Ask:** one concrete need from someone outside the team, only when the sessions show a blocker (access, a decision, another team's review). Otherwise delete the line.

Report work only: repositories in the work GitHub organisation, and Linear. When no work organisation is configured, no repository counts as work: report Linear only and leave out every pull request, repository, and session, or ask the user for the organisation when running interactively. Leave out the user's personal repositories (every `maxgio92/*` repository) and sessions under `~/.dotfiles`, the notes repo, or any `maxgio92/*` checkout, in every field. Leave out the user's own initiatives too: Linear issues labelled `design` and the pull requests and sessions behind them, in every field, including PRs waiting on review. They are not part of the team's plans.

Delete every line with no evidence, as the template asks. Today is the exception: it always stays. Never guess; ask the user when a field depends on intent the logs can't show (often Ask).

## Output

Follow `slack-message` for register. The channel template overrides the Slack sentence budget and the no-lists rule: each field label on its own line, then one `•` bullet per item, with a blank line between sections so Slack renders each one apart, lowercase, no bold. Cite every pull request as its full bare URL each time it appears, including a repeat in the same line; never a bare number like `70016`. Never put punctuation right after a URL; Slack folds it into the link. Cite Linear issues by key only (`ABC-123`), no URL.

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
