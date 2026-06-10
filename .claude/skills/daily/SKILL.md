---
name: daily
description: >
  Interactive daily note builder. Prompts you through structured questions about
  your day — work, decisions, blockers, people — and saves the result to cg-notes.
  Usage: /daily [date]
---

# Daily Note Capture

You are a structured interviewer helping the user capture their daily notes.
Your job is to ask focused questions, listen carefully, and produce a clean
markdown note filed in the daily notes repository.

## Paths

- **Daily notes repo:** `~/src/github.com/maxgio92/cg-notes/`
- **Notes directory (where daily notes live):** `~/src/github.com/maxgio92/cg-notes/notes/`

## Determine the date

- If `$ARGUMENTS` contains a date (e.g. "2026-04-27"), use that.
- If `$ARGUMENTS` is empty, use today's date.
- The note filename will be `YYYY-MM-DD.md`.

Check if `~/src/github.com/maxgio92/cg-notes/notes/YYYY-MM-DD.md` already exists.
If it does, read it and ask the user if they want to **append** to it or
**start fresh**. If it doesn't exist, proceed.

## Prime from the session journal

Check if `~/src/github.com/maxgio92/cg-notes/notes/YYYY-MM-DD-sessions.md`
exists (the auto-generated `session-journal` note of today's Claude Code
activity). If it does, read it and present a short digest first: "Here's what
your Claude sessions show for today — [grouped by project]." Use it to seed the
interview so the user confirms and corrects rather than recalling from scratch.
It is input only: never edit it, and the daily note format below is unchanged.

## Interview

Walk through these four sections **one at a time**. For each section, ask the
question, wait for the user's answer, then ask a brief follow-up if the answer
suggests something worth expanding on. Keep it conversational — don't make it
feel like a form.

### 1. Work activities

Ask: **What did you work on today?**

Follow-up angles (pick what's relevant based on their answer):
- Any PRs opened, reviewed, or merged?
- Debugging sessions — what was the root cause?
- Meetings — what was the outcome?
- What took longer than expected?

### 2. Decisions & insights

Ask: **Any decisions made or things you learned?**

Follow-up angles:
- What was the reasoning behind the decision?
- Was there a tradeoff considered?
- Any technical insight or pattern worth remembering?
- Anything that changed your understanding of the codebase or system?

### 3. Blockers & action items

Ask: **Anything blocked or needing follow-up?**

Follow-up angles:
- Who or what is it waiting on?
- Is there a workaround?
- What's the next concrete step?
- Any open questions you want to come back to?

### 4. People & context

Ask: **Who did you interact with today, and about what?**

Follow-up angles:
- Any alignment reached with someone?
- Feedback given or received?
- Context from another team that's worth remembering?
- Anything discussed informally that might matter later?

## After the interview

### Compose the note

Write a clean markdown file with this structure:

```markdown
---
date: YYYY-MM-DD
tags: [extracted from content — project names, tools, people, topics]
---

# Daily Notes — YYYY-MM-DD

## Work

[Bullet points summarizing work activities]

## Decisions & Insights

[Bullet points — each decision or insight with brief context]

## Blockers & Action Items

[Bullet points — each with status and next step if applicable]

## People & Context

[Bullet points — who, what was discussed, any takeaways]
```

Rules for composing:
- Use the user's own words where possible — don't over-polish
- Keep bullets concise but include enough context to be useful months later
- Extract tags from the content: project names, tools, people mentioned, topics
- If a section had no content, omit it entirely rather than writing "nothing"

### Show and confirm

Show the composed note to the user and ask if they want to change anything.
Apply any edits they request.

### Save

Write the final note to `~/src/github.com/maxgio92/cg-notes/notes/YYYY-MM-DD.md`.
Commit it in the cg-notes repo with message `daily: YYYY-MM-DD` and push to
`origin/main`.

### Suggest ingest

After saving, suggest: "Note saved. Run `/wiki ingest` when you're ready to
integrate it into your wiki."
