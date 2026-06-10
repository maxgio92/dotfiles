---
name: wiki
description: >
  Manage a personal LLM Wiki — ingest daily notes, query the knowledge base,
  or lint for health. Implements the LLM Wiki pattern (Karpathy, 2026).
  Usage: /wiki ingest [target] | /wiki query [question] | /wiki lint
---

# LLM Wiki Skill

You are operating as a disciplined wiki maintainer. You manage a persistent,
compounding knowledge base — a structured collection of interlinked markdown
files that synthesizes knowledge from raw daily notes.

## Paths

The wiki and the source notes live in the same repo, in sibling subdirectories.

- **Source notes (immutable, never modify):** `~/src/github.com/maxgio92/cg-notes/notes/` —
  daily notes are files matching `YYYY-MM-DD.md`.
- **Wiki (you own this entirely):** `~/src/github.com/maxgio92/cg-notes/wiki/`
- **Schema:** `~/src/github.com/maxgio92/cg-notes/wiki/CLAUDE.md`

## First: read the schema

Before doing anything, read `~/src/github.com/maxgio92/cg-notes/wiki/CLAUDE.md` to
understand the wiki's structure, conventions, and workflows. Follow it precisely.

## Parse the command

The user invoked: `/wiki $ARGUMENTS`

Parse `$ARGUMENTS` to determine the operation:

- If it starts with **ingest**: proceed to the Ingest workflow
- If it starts with **query**: proceed to the Query workflow
- If it starts with **lint**: proceed to the Lint workflow
- Otherwise: explain the available operations and ask for clarification

---

## Ingest Workflow

The user wants to ingest daily notes into the wiki.

### 1. Identify which notes to ingest

Look at what follows "ingest" in `$ARGUMENTS` to decide scope:

- **"my daily notes"** or **"all"** or no further args: find all `.md` files in
  `~/src/github.com/maxgio92/cg-notes/notes/` that do NOT already have a corresponding
  source summary in `~/src/github.com/maxgio92/cg-notes/wiki/sources/`. These are the
  un-ingested notes. Exclude `*-sessions.md` files: those are the auto-generated
  `session-journal` activity logs that feed `/daily`, not journal entries to ingest.
- **A specific filename or date pattern** (e.g. "2026-04-25" or "meeting-notes.md"):
  find matching files in the notes directory.

If no un-ingested notes are found, tell the user and stop.

### 2. Process each note

For each note to ingest, one at a time:

a. **Read the note** from `~/src/github.com/maxgio92/cg-notes/notes/`

b. **Discuss with the user**: briefly summarize key takeaways from the note —
   decisions made, topics discussed, action items, insights, entities mentioned.
   Ask if the user wants to emphasize or de-emphasize anything before you file it.

c. **Create a source summary** in `~/src/github.com/maxgio92/cg-notes/wiki/sources/`.
   Filename should match the source note name. Include:
   - YAML frontmatter (title, type: source, created, updated, sources, tags)
   - A structured summary of the note's content
   - Links to entity/concept pages

d. **Create or update entity pages** in `~/src/github.com/maxgio92/cg-notes/wiki/entities/`
   for any people, teams, projects, tools, or services mentioned. If a page exists,
   update it with new information from this note. If not, create it.

e. **Create or update concept pages** in `~/src/github.com/maxgio92/cg-notes/wiki/concepts/`
   for any ideas, patterns, processes, or methodologies discussed. Same create-or-update
   logic.

f. **Add cross-references** — every touched page should link to related pages.
   When updating an existing page, check for new connections to add.

g. **Update `index.md`** — add entries for any newly created pages under the
   appropriate section. Each entry: `- [Page Title](path/to/page.md) — one-line summary`

h. **Append to `log.md`** — add an entry like:
   `## [YYYY-MM-DD] ingest | <source note filename>`
   followed by a brief summary of what was created/updated.

### 3. Commit

After processing all notes, commit all wiki changes in the cg-notes repo with a
message like `ingest: <brief description of what was ingested>` and push to
`origin/main`. Source notes themselves are immutable — only `wiki/` files should
be in the commit.

---

## Query Workflow

The user wants to ask a question against the wiki.

### 1. Understand the question

Everything after "query" in `$ARGUMENTS` is the question.

### 2. Search the wiki

- Read `~/src/github.com/maxgio92/cg-notes/wiki/index.md` to find relevant pages
- Read the relevant wiki pages
- If needed, search with grep across the wiki for specific terms

### 3. Synthesize an answer

- Provide a clear answer citing specific wiki pages: `[Page Title](path)`
- If the wiki lacks information to answer, say so and suggest what sources
  might fill the gap

### 4. Optionally file the answer

If the answer involves non-trivial synthesis (comparison, analysis, connection),
offer to file it as a new page in `~/src/github.com/maxgio92/cg-notes/wiki/analyses/`.
If the user agrees, create the page, update index.md, and append to log.md.

---

## Lint Workflow

Health-check the wiki.

### 1. Read the full wiki state

- Read `index.md` and `log.md`
- List and skim all pages across `sources/`, `entities/`, `concepts/`, `analyses/`

### 2. Check for issues

- **Contradictions**: claims in one page that conflict with another
- **Stale content**: information superseded by newer sources
- **Orphan pages**: pages with no inbound links from other pages
- **Missing pages**: entities or concepts mentioned in text but lacking their own page
- **Missing cross-references**: pages that should link to each other but don't
- **Gaps**: areas where more sources would be valuable

### 3. Report and fix

- Present a structured report of findings to the user
- Offer to fix issues (add links, create missing pages, resolve contradictions)
- If the user approves fixes, apply them and commit
- Append a lint entry to `log.md`
