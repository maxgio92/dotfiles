---
name: codex
description: "Delegate to GPT-5 via the codex CLI for code review, deep exploration, or a second opinion. Uses the codex MCP server with named profiles (review, deep) and supports multi-turn conversations."
---

# codex

Codex is a **second opinion**, not an authority. You are the primary agent; codex is a consultant you can talk to. Evaluate its output critically — check claims against the actual code, disagree when warranted, and form your own view before presenting to the user. The user wants your judgment informed by codex's perspective, not a pass-through.

Back-and-forth with codex is encouraged. Debate, push back, ask it to justify claims, or challenge its suggestions with context it may not have. A two- or three-turn conversation that stress-tests an idea is more valuable than a single unchallenged answer.

## When to delegate

- **Code / diff review** — independent second set of eyes on a change.
- **Hard architecture or migration problems** — genuinely stuck, or a call worth validating.
- **Second opinion on a plan** — before committing to an approach.
- **Exploring an unfamiliar codebase** — "figure out how X works and report back."

Do not delegate routine edits, small refactors, or anything faster to do directly.

## Tools

Two MCP tools from the `codex` server:

- **`codex`** — start a new session. Required: `prompt`. Returns `{threadId, content}`.
- **`codex-reply`** — continue an existing thread. Required: `threadId`, `prompt`. Returns `{threadId, content}`.

`content` is codex's final answer, not its internal reasoning or tool use. Present codex's key points to the user alongside your own assessment — where you agree, where you disagree, and why.

## Calling convention

Every `codex` call needs two params:

- **`profile`** — `"review"` or `"deep"` (see below). Profiles handle model, effort, sandbox, and approval policy. No need to pass those separately.
- **`cwd`** — the user's current project directory.

That's it. Do not pass `sandbox`, `approval-policy`, or `model` — the profile covers them.

To escalate to writable sandbox, pass `sandbox: "workspace-write"` explicitly and tell the user before calling.

## Profile

- **`review`** — code review, diff review, plan critique. gpt-5.5 at high effort, read-only sandbox.
- **`deep`** — hard problems (architecture, migrations, stuck debugging). gpt-5.5 at max effort, read-only sandbox.

Profile is locked at thread start. `codex-reply` cannot change model or effort. If a conversation may get harder, start with `deep`.

## Thread reuse

Before each call, state your intent in one line:

- *"Starting new thread — reviewing auth.go."*
- *"Continuing thread abc123 — pushing back on the middleware suggestion."*

**Default: new thread per invocation.**

**Continue (`codex-reply`) when:**
- Directly iterating on what codex just said (refining, pushing back, applying its suggestion to adjacent code).
- A follow-up where codex's prior context makes the answer better.

**Start fresh when:**
- The topic changed.
- You moved to different code or a different question.
- Codex's last answer was off-track.
- Many unrelated tool calls have happened since the last codex exchange.

When in doubt: new thread. Cheaper to restart than to poison an ongoing one.

## Push past the first answer

Codex's first response is usually a survey — competent but surface-level. The real value comes from follow-ups. After the initial response, always consider a `codex-reply` that pushes for specifics: edge cases codex missed, things it hedged on, or applying its general suggestion to the concrete code at hand. Two or three focused replies on the same thread almost always converge on a better answer than a single elaborate prompt.

If codex's first answer is already sharp and specific, a follow-up isn't needed. But when the response reads like a checklist or stays generic, push back — that's when conversation beats single-shot.

## Additional directories

When this Claude session has additional directories (via `/add-dir` or similar), codex needs to know about them — otherwise it only sees `cwd`.

**For reviews and read-only tasks (MCP tools):**
The read-only sandbox can read from any path on disk, so the issue is awareness, not access. Include the additional directory paths and their purpose in the prompt:

```
Review this change. The main project is at /path/to/repo, but it depends on
a shared library at /path/to/shared-lib — check for breaking interface changes
across both.
```

Set `cwd` to the primary project root. Codex can navigate to and read the other directories as long as you tell it they exist and why they matter.

**For tasks needing write access to additional directories:**
The MCP `codex` tool only supports a single `cwd` and its `sandbox` field is a simple mode string — it cannot express additional writable roots. Use `codex exec` via Bash instead, which supports `--add-dir`:

```bash
codex exec \
  -p review \
  --add-dir /path/to/other-repo \
  -s workspace-write \
  -o /tmp/codex-result.txt \
  "refactor the shared interface in both repos"
```

Each `--add-dir` makes that directory writable alongside the primary workspace. Use `-o` to capture the final message for follow-up.

**Gathering the directory list:**
Before delegating to codex, check what additional directories are loaded in the current agent session. Mention each one in the prompt for read-only tasks, or pass it via `--add-dir` for writable tasks, so codex sees the full working set, not just `cwd`.
