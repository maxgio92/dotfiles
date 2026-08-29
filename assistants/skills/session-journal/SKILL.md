---
name: session-journal
description: >
  Scan local Claude Code, Codex, and Pi session transcripts and maintain an
  auto-generated daily activity note in your notes repo. Each invocation does
  one incremental pass. The note feeds the daily skill as source material.
---

# Session Journal

You maintain an auto-generated summary of today's coding-agent sessions at
`$NOTES_REPO/notes/YYYY-MM-DD-sessions.md`. Each run is
one incremental pass ("tick"): find transcripts with new activity, extract only
the new content, merge bullets into today's note, save state. Stay
context-frugal: never read whole transcripts into context.

## Paths

Read `~/.config/notes-repo.env` if present (`NOTES_REPO=<path to the notes
repo>`); else default `NOTES_REPO` to `~/notes`.

- **Claude transcripts:** `~/.claude/projects/<munged-cwd>/<session-uuid>.jsonl`
- **Codex transcripts:** `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`
- **Pi transcripts:** `~/.pi/agent/sessions/--<path>--/<timestamp>_<uuid>.jsonl`
  (one JSON event per line; fields include `type`, `message`, `timestamp`,
  `sessionId`, `cwd`, `gitBranch`)
- **Output note:** `$NOTES_REPO/notes/YYYY-MM-DD-sessions.md`
- **State file:** `~/.local/state/session-journal/state.json`

If `$NOTES_REPO/notes/` does not exist, stop and tell
the user; do not write anywhere else.

## Per-tick algorithm

### 1. Load state

Read `~/.local/state/session-journal/state.json`:

```json
{
  "lastRun": "<ISO timestamp>",
  "date": "YYYY-MM-DD",
  "perFile": { "/abs/path/<uuid>.jsonl": <byte offset> },
  "selfSessions": ["/abs/path/<uuid>.jsonl"]
}
```

If missing, this is a first run: create the directory
(`mkdir -p ~/.local/state/session-journal`) and treat `lastRun` as today 00:00
with empty `perFile`.

**Date rollover:** if today's date differs from `state.date`, start fresh:
clear `perFile` and `selfSessions`, set `date` to today. Leave yesterday's
note untouched.

### 2. Discover transcripts with new activity

Search all transcript roots that exist:

```bash
find ~/.claude/projects ~/.codex/sessions ~/.pi/agent/sessions \
  -type f -name '*.jsonl' ! -name 'agent-*' -newermt "<lastRun>" 2>/dev/null
```

`-newermt` needs an ISO timestamp, never the bareword `today` — `find` here is
`bfs`, which rejects it. For a first run use `$(date +%Y-%m-%dT00:00:00)`;
otherwise pass the stored ISO `lastRun`.

`agent-*.jsonl` files are subagent sidecars: always skip them.

### 3. Exclude your own session

The session running this skill must not be journaled. Use these mechanisms:

1. **By marker (later passes):** every pass ends by printing the literal marker
   `[session-journal tick]` (see step 7), so your own transcript contains it
   from the second tick on. Check discovered files one at a time (the shell is
   zsh — iterate with `while read -r`, not an unquoted `for $FILES`, which does
   not word-split in zsh):

   ```bash
   find ... | while read -r f; do grep -lF '[session-journal tick]' "$f"; done
   ```

2. **By identity (first pass):** exclude `$PI_SESSION_FILE` when set. For Codex,
   exclude the transcript whose `session_meta.payload.id` matches
   `$CODEX_THREAD_ID` or `$CODEX_SESSION_ID`. For Claude, use the current session
   id when the runtime exposes it. Never exclude every transcript for the current
   working directory.

Add every excluded file to `selfSessions` and skip it now and in future ticks.

### 4. Extract new content per transcript

Select the extraction adapter from the transcript root. All formats use one
JSON object per line.

**Claude:** `.type` is one of
`user`, `assistant`, `system`, `ai-title`, `last-prompt`, and others.
`user`/`assistant` carry `.message.content` (a string OR an array of blocks,
each with `.type` in `text`/`thinking`/`tool_use`). Top-level fields:
`.timestamp`, `.cwd`, `.gitBranch`, `.sessionId`. There is NO `summary` type:
the session title is `type=="ai-title"` with the title in `.aiTitle`.

For each remaining file, read only bytes past the stored offset (0 if new).
Use the following filter for Claude:

```bash
tail -c +$((offset + 1)) "$file" | jq -r '
  select(.type == "user" or .type == "assistant" or .type == "ai-title") |
  if .type == "ai-title" then "TITLE: \(.aiTitle // "")"
  elif .type == "user" then
    (.message.content | if type == "string" then . else (map(select(.type? == "text") | .text) | join(" ")) end) as $t
    | select(($t | length) > 0) | "USER \(.timestamp // ""): \($t[0:200])"
  else
    (.message.content | if type == "string" then . else (map(select(.type? == "text") | .text) | join(" ")) end) as $t
    | select(($t | length) > 0) | "ASSISTANT \(.timestamp // ""): \($t[0:150])"
  end' 2>/dev/null | head -40
```

**Pi:** select `type == "message"` entries whose `message.role` is `user` or
`assistant`. Extract strings and `text` content blocks from `message.content`.
Read `cwd`, session id, and start time from the `type == "session"` header.

**Codex:** extract user text from `event_msg` entries whose `payload.type` is
`user_message`. Extract assistant text from `response_item` entries whose
`payload.type` is `message` and `payload.role` is `assistant`; join text from its
content blocks. Read `cwd`, session id, and start time from the `session_meta`
payload.

Also grab metadata once per file. The first physical line is often a
`permission-mode` or `file-history-snapshot` record with no `cwd`, so take the
first line that actually carries it:

```bash
jq -rc 'select(.cwd) | "\(.cwd) | \(.gitBranch // "-") | \(.sessionId)"' "$file" 2>/dev/null | head -1
```

Rules:
- Cap at ~40 extracted lines per session. If `wc -l` on the untruncated
  extraction exceeds that, keep the first 20 and last 20 lines and note the
  session as high-activity.
- If the total extraction across all sessions would exceed ~150 lines, do the
  small sessions inline and delegate the large ones to ONE general-purpose
  subagent: give it the file paths and byte offsets, ask it to run the same
  extraction and return 1-3 summary bullets per session (nothing else).
- **Schema tolerance:** if the jq filter yields nothing for a file that
  clearly grew, fall back to
  `tail -c +$((offset+1)) "$file" | grep -o '"text":"[^"]\{1,160\}' | head -30`
  and work from that. Never fail the whole tick over one file.
- Record the new byte offset for each processed file: its current size
  (`stat -c %s "$file"`).

### 5. Summarize

From the extracted material, write 1-3 bullets per session: what was worked
on, notable decisions or fixes, blockers hit. Skip filler (greetings, retries,
permission chatter). Group sessions by project (basename of `cwd`).

**Weight substantive content over the title.** The `ai-title` is generated from
the opening exchange and often names a throwaway first question, not the real
work: e.g. a session titled after a one-line config tweak whose actual
substance was a ticket's coverage-metric analysis. So:

- Drive the summary from the `USER` prompts and `ASSISTANT` outcomes, not the
  `TITLE`. A long session usually shifts topic after the first prompt; the later
  prompts and final assistant texts carry the real work.
- Prefer the prompt that named a concrete artifact (a PR, a Linear ticket, a
  file, a metric) and the outcome that resolved it over the first prompt.
- When prompts span multiple distinct topics, give each its own bullet rather
  than collapsing everything under the title's framing.
- Use the `TITLE` only as a fallback label when the prompts are too thin to
  characterize the work.

### 6. Merge into today's note

Read `notes/YYYY-MM-DD-sessions.md` if it exists, merge, and rewrite. Sessions
are keyed by short session id (first 8 chars of the uuid): update an existing
session's entry in place (extend its time range, refine bullets with the new
activity); add new sessions under their project heading. Never duplicate a
session entry.

```markdown
---
date: YYYY-MM-DD
generated-by: session-journal
updated: <ISO timestamp>
---

# Agent sessions - YYYY-MM-DD

## <project>

- **HH:MM–HH:MM** `<branch>` (<short-id>): what was worked on; decisions; blockers
```

If there was no new activity this tick, only refresh the `updated:` field
(or, if the note doesn't exist yet, write nothing).

### 7. Save state and report

Write the updated state file (new `lastRun`, advanced `perFile` offsets,
`date`, `selfSessions`). Do NOT commit or push anything in the notes repo.

End your output with a one-line status and the self-exclusion marker, e.g.:

```
3 sessions, 2 updated, 1 new. [session-journal tick]
```

## Repeated operation

A direct invocation performs one pass and stops. When the current agent exposes
a scheduler or repeat command, it may schedule another pass 1200-1800 seconds
later. Do not assume a platform-specific repeat feature exists.
