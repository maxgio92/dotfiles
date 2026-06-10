---
name: session-journal
description: >
  Scan local Claude Code session transcripts and maintain an auto-generated
  daily activity note in cg-notes. Designed to run under /loop (self-paced),
  but a single invocation does one full pass. The note feeds /daily as source
  material. Usage: /session-journal (or /loop /session-journal)
---

# Session Journal

You maintain an auto-generated summary of today's Claude Code sessions at
`~/src/github.com/maxgio92/cg-notes/notes/YYYY-MM-DD-sessions.md`. Each run is
one incremental pass ("tick"): find transcripts with new activity, extract only
the new content, merge bullets into today's note, save state. Stay
context-frugal: never read whole transcripts into context.

## Paths

- **Transcripts:** `~/.claude/projects/<munged-cwd>/<session-uuid>.jsonl`
  (one JSON event per line; fields include `type`, `message`, `timestamp`,
  `sessionId`, `cwd`, `gitBranch`)
- **Output note:** `~/src/github.com/maxgio92/cg-notes/notes/YYYY-MM-DD-sessions.md`
- **State file:** `~/.local/state/session-journal/state.json`

If `~/src/github.com/maxgio92/cg-notes/notes/` does not exist, stop and tell
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

```bash
find ~/.claude/projects -maxdepth 2 -name '*.jsonl' ! -name 'agent-*' -newermt "<lastRun>"
```

`-newermt` needs an ISO timestamp, never the bareword `today` — `find` here is
`bfs`, which rejects it. For a first run use `$(date +%Y-%m-%dT00:00:00)`;
otherwise pass the stored ISO `lastRun`.

`agent-*.jsonl` files are subagent sidecars: always skip them.

### 3. Exclude your own session

Your own loop conversation must not be journaled. Two mechanisms:

1. **By marker (later ticks):** every tick ends by printing the literal marker
   `[session-journal tick]` (see step 7), so your own transcript contains it
   from the second tick on. Check discovered files one at a time (the shell is
   zsh — iterate with `while read -r`, not an unquoted `for $FILES`, which does
   not word-split in zsh):

   ```bash
   find ... | while read -r f; do grep -lF '[session-journal tick]' "$f"; done
   ```

2. **By identity (first tick):** on the very first tick the marker is not yet
   flushed to your own transcript on disk, so the grep misses it. You know your
   own working directory — exclude the transcript whose `cwd` matches it (the
   `<munged-cwd>` directory name encodes the path). Confirm via the visible
   session id if available.

Add every excluded file to `selfSessions` and skip it now and in future ticks.

### 4. Extract new content per transcript

Event schema (confirmed): one JSON object per line. `.type` is one of
`user`, `assistant`, `system`, `ai-title`, `last-prompt`, and others.
`user`/`assistant` carry `.message.content` (a string OR an array of blocks,
each with `.type` in `text`/`thinking`/`tool_use`). Top-level fields:
`.timestamp`, `.cwd`, `.gitBranch`, `.sessionId`. There is NO `summary` type:
the session title is `type=="ai-title"` with the title in `.aiTitle`.

For each remaining file, read only bytes past the stored offset (0 if new):

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
work — e.g. a session titled "Enable Fable" whose actual substance was a Linear
FUL-311 coverage-metric analysis. So:

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

# Claude sessions — YYYY-MM-DD

## <project>

- **HH:MM–HH:MM** `<branch>` (<short-id>): what was worked on; decisions; blockers
```

If there was no new activity this tick, only refresh the `updated:` field
(or, if the note doesn't exist yet, write nothing).

### 7. Save state and report

Write the updated state file (new `lastRun`, advanced `perFile` offsets,
`date`, `selfSessions`). Do NOT commit or push anything in cg-notes.

End your output with a one-line status and the self-exclusion marker, e.g.:

```
3 sessions, 2 updated, 1 new. [session-journal tick]
```

## Loop behavior

When running under /loop in dynamic (self-paced) mode, schedule the next
wakeup 1200-1800 seconds out with the same prompt after finishing the tick.
A quiet tick (no new activity) can stretch toward 1800s; a busy one can use
1200s. Only end the loop if the user asks or cg-notes is missing.

A bare `/session-journal` invocation (no loop) is a single pass: run the tick
and stop.
