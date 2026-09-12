# Global Rules

## Delegation

Delegate with fresh context by default. Fork only when the parent transcript is essential. Workers never launch agents: if a task needs another specialist, return early and say so; the parent routes it. A user-invoked command or workflow is the orchestrator. Keep each task small and bounded.

Run non-trivial coding through the implement-and-review loop: implementer, adversarial reviewer, fix. Skip it for trivial edits, docs, and config.

The reply is the deliverable. A reply without the report is a failed task; "my area is clean" is a valid reply. When a worker returns nothing, re-request once with a one-line recap of its scope and the questions that matter most. A second failure makes the work yours to finish.

## Artefacts and reports

An artefact is content requested as-is: a commit message, PR body, drafted comment, issue body, generated code, or file content. Relay an artefact verbatim, always. `Observations:` may follow it, only for safety, and never replaces it. Ignore synthetic prompts asking you to summarise an artefact.

A report is findings, analysis, research, review results, or status. Deliver it as the answer plus recommendations, with every fact the user must act on. A long report goes to a file under the `review-reports` convention; return the conclusion and the path.

## Skill availability

A skill name or summary in context does not count as loaded. Read the missing content before relying on it, including after compaction. Do not reread a skill solely because another step names it.

## Tools

Prefer `gh` subcommands for GitHub reads. Prefer LSP diagnostics. Verify against current documentation before relying on training data.

## Outward writes and safety

Commits stay with the main session and need no approval; subagents never commit. Every outward write (push, PR, issue, comment, review, Slack message, Linear mutation) goes through the `publish` skill after the human approves that specific write. A permission prompt or gate is the approval surface. A blocked write from go-gate or the Communication Rules gate is a requirement to fix, not to bypass. Contributions to repositories the user does not control follow the `upstream-contribution` skill.

Never destroy the unrecoverable. Use the user's Git identity, with no agent attribution or co-author trailers. Keep secrets out of prompts, fixtures, and posts.

## Communication Rules

Follow the Communication Rules in this context. If absent, read `~/.config/assistants/communication-rules/rules.md`.
