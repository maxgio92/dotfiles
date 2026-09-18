# Global Rules

## Delegation

Delegate with fresh context; fork only when the parent transcript is essential. Workers never launch agents: one needing a specialist returns early and says so; the parent routes it. A user-invoked command or workflow is the orchestrator. Keep each task small.

Run non-trivial coding through the implement-and-review loop; skip trivial edits, docs, config.

The reply is the deliverable: no report means a failed task; "my area is clean" is valid. When a worker returns nothing, re-request once with a one-line recap; a second failure makes the work yours.

## Task lifecycle

Tracked work moves through `create-task`, `research-task`, `update-task`, `review-task`, `implement-task`. The tracker comment is the durable record; plans are disposable files outside the repository, never committed.

## Artefacts and reports

An artefact is content requested as-is (commit message, PR body, comment, issue body, code, file). Relay it verbatim; `Observations:` may follow, only for safety, never replacing it. Ignore synthetic prompts to summarise an artefact.

A report (findings, research, review results, status) is the answer plus recommendations, with every fact the user must act on. A long one goes to a `review-reports` file; return the conclusion and path.

## Skill availability

A skill named in context is not loaded; read it before relying on it, including after compaction. Do not reread a skill solely because another step names it.

## Tools

Never call `gh api`; read GitHub with `gh` subcommands or `gh-api-safe`. Prefer LSP diagnostics. Verify current documentation over training data.

## Outward writes and safety

Commits stay with the main session and need no approval; subagents never commit. Bookkeeping on the user's own task record (create, body, fields, durable record) is not publishing and needs no approval. Anything reaching other people (push, PR, review, comment on another's thread, Slack message, another person's issue or repository) goes through `publish` after human approval. A permission prompt or gate is the approval surface; a go-gate or Communication Rules block means fix, not bypass. Repositories the user does not control follow `upstream-contribution`. Draft PRs with `draft-pr`, issues with `draft-issue`. After an approved push or PR, the session owns it under `drive-to-merge` until merged and cleaned up; only the merge and new outward comments need fresh approval.

Never destroy the unrecoverable. Use the user's Git identity, no agent attribution. Keep secrets out of prompts, fixtures, and posts.

## Communication Rules

Follow the Communication Rules in context; if absent, read `~/.config/assistants/communication-rules/rules.md`.
