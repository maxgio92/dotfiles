---
name: self-review
description: Draft the user's quarterly performance self-review (outcomes, cultural contribution, one thing to do differently, next-quarter goals) from the notes wiki, daily notes, Slack, and GitHub, with every claim traced to evidence. Use when the user asks for a self-review, self-assessment, performance review, quarterly review, Culture Amp review, or wants to map their quarter's achievements to review questions, even if they only say "help me with my review".
---

# Self Review

Draft a first-person self-review from evidence, iterate it with the user, and keep the answers short and human. This skill drafts and stops; the user submits the form.

## 1. Frame before gathering

Settle these with the user before drafting; the framing changes which work counts.

- **Period.** Default to the quarter that is ending. Read the dates of the last review from the notes if the boundary is unclear.
- **Frame.** The story the user wants told (for example, "staff engineer on loan to a new team and domain"). Ask for it.
- **Exclusions.** Work the user wants left out, even if it is large.
- **Questions.** Use the user's pasted form questions verbatim. Otherwise use `references/form.md`.

## 2. Gather evidence

Read `~/.config/notes-repo.env` for `NOTES_REPO` (default `~/notes`). Gather in this order; stop a source when it adds nothing new.

1. **Wiki.** `wiki/index.md`, then the entity and concept pages for the period's main projects, then `wiki/sources/<date>.md` for key days. Entity pages hold the dated story of each project.
2. **Daily notes.** `notes/YYYY-MM-DD.md` for detail the wiki compressed. List the weekdays with no note as gaps.
3. **Slack.** Search the user's own messages in the period for work the notes lack (demos, estimates, product threads). Load the Slack search tool first.
4. **GitHub.** Count merged PRs and reviews with `gh pr list --author @me --state merged --search "merged:<start>..<end>"` and `gh search prs --reviewed-by @me`. Never call `gh api`.
5. **Drive.** Only for docs the user names. If the token lacks the Drive scope, ask the user to run `! gcloud auth login --enable-gdrive-access`.

For a quarter of notes, fan out one read-only agent per month over the wiki sources; each returns candidate outcomes with source paths.

## 3. Draft

Write all answers in first person, in the user's voice. Each answer is two or three sentences; each bullet the same.

- **Outcomes.** Lead each bullet with the result delivered, then one sentence of context. Vary the openings. The outcome is what was built or changed; the user's role (lead, owner) is context.
- **Credit.** Name collaborators exactly. Ask who "we" is before writing it.
- **Cultural contribution.** How the user enabled other people or teams, with one or two concrete artefacts as support.
- **Do differently.** The user's own lesson, framed as staff-level collaboration. Never describe another team's way of working as a failure.
- **Goals.** Only work that ends next quarter, each with a success measure. State the end state (for example, enforcing in production) and name interim phases as steps. Leave out what finishes this quarter and starting conditions (a handoff, returning to a team). Check each goal's feasibility against the wiki and say when part of it will not fit in one quarter.

Drop any claim the evidence does not confirm, rather than hedging it.

## 4. Save and show

Save the draft to `${XDG_DATA_HOME:-$HOME/.local/share}/agent-reports/<notes-repo-dir>/<YYYY-MM-DD>-self-review-<period>.md` with these sections: the frame and exclusions, the answers, an evidence table (claim to source path), items dropped from the answers, and caveats (note gaps, unconfirmed claims). The draft is a living file: rewrite the answers in place on each revision.

After every revision, show all answers in full in the reply, then one or two lines on what changed and any claim the user must confirm.

## Anti-patterns

- Contrast clauses: "X, not Y", "instead of", "rather than". State the positive part only.
- Repeated openers ("I delivered X. I delivered Y.").
- Second person ("you") in the answers.
- Dates, PR numbers, and counts in the answers when a plain sentence carries the point; keep them in the evidence table.
- Attributing shared work to the user alone, or crediting someone the user did not name.
- Puffery and filler. The Communication Rules apply to every answer.
