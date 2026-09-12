---
name: codex
description: "Get a second opinion from Codex (OpenAI) on a diff, a design, or a hard problem through the official Codex plugin for Claude Code. Covers the read-only adversarial review, the pushback turn, and the write-capable codex exec fallback for multi-repo work."
---

# codex

Codex is a **second opinion**, not an authority. You are the primary agent; Codex is a consultant. Check every claim against the code, disagree when the evidence says so, and form your own view before reporting. The user wants your judgment informed by Codex, not a pass-through.

## Transport

Codex runs through OpenAI's official Claude Code plugin, `codex@openai-codex` (openai/codex-plugin-cc, pinned at 1.0.6). The plugin drives `codex app-server` from a Node companion script. The removed `codex mcp-server` and the old `mcp__codex__*` tools are gone; do not look for them.

The plugin's slash commands are not model-invocable, so call the script directly:

```bash
COMPANION="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/scripts/codex-companion.mjs}"
[ -f "$COMPANION" ] || COMPANION=$(ls -d "$HOME"/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs | sort -V | tail -1)
```

Check readiness once per session:

```bash
node "$COMPANION" setup --json
```

`ready: false` means Codex is missing or logged out. Report that and continue without Codex; never run `npm install` or `codex login` on the user's behalf.

## When to consult Codex

- A diff review where an independent model is worth a second run.
- A design or migration call you want pressure-tested.
- An unfamiliar codebase you want explored in parallel.

Do not consult Codex for routine edits, small refactors, or anything faster to do directly. In the implement-and-review loop and `/code-review`, Codex is dastardly's default engine; the caller opts out with `reviewer: claude` or "Claude only".

## Adversarial review

Read-only. The plugin picks the diff itself: the working tree by default, or `--base <ref>` for committed work. Untracked files count. Your text travels as focus text inside the plugin's adversarial prompt.

```bash
node "$COMPANION" adversarial-review --wait [--base "$BASE_REF"] "$FOCUS"
```

Build `FOCUS` from, in this order:

1. Skill mentions so Codex loads the shared rubric from its own skills directory: `$dastardly $effective-go $cross-system-rubric`.
2. The task in one or two sentences.
3. The implementer's summary, if any.
4. The repository instruction file path (`AGENTS.md` or `CLAUDE.md`) and any repo-local Go standards skill.
5. The review priorities you want weighted: design fit, trust boundaries, silent failures, test coverage, convention breaks, AI-shaped prose.

Keep it under a few thousand characters. Run from the repository root; the script resolves the git repo from the current directory.

Output is Codex's findings with severity (critical, high, medium, low), file, line range, confidence, and recommendation, plus a verdict of approve or needs-attention. Map into your own scale before reporting: a confirmed reachable failure at critical or high becomes `block`; verified complexity or prose findings become `strong`; the rest become `nit` or are dropped; a needs-attention verdict on design grounds feeds your design verdict. Verify every finding against the code first.

## Pushback turn

Codex's first answer is often a survey. Push back once when it is generic or hedged. The review thread cannot be resumed, so open a fresh read-only task seeded with the review:

`task` takes the prompt as an argument, a file, or piped stdin. It has no `--wait` flag and no `-` marker; anything unrecognised becomes prompt text.

```bash
node "$COMPANION" task <<'EOF'
Earlier adversarial review output:
<paste the findings>

For each finding, either show the concrete code path that triggers it or withdraw it. Add anything you missed on <the area you doubt>. Answer as the dastardly skill.
EOF
```

Never pass `--write` from a review. `task` defaults to read-only.

## Runtime notes

- One shared Codex runtime per Claude session. A second concurrent call fails with a busy error, so run reviews sequentially.
- Model and effort come from `~/.codex/config.toml`. The review commands accept no model, effort, or profile flags. `task` accepts `--model` and `--effort` when the user asks for them.
- Codex reads `AGENTS.md`, not `CLAUDE.md`, unless `project_doc_fallback_filenames = ["CLAUDE.md"]` is set in its config. Name the instruction file in the focus text.
- Background runs exist (`--background`, then `status` and `result`), but use `--wait` inside a review so the output lands in the same call.
- The companion script is the plugin's internal contract. After a plugin upgrade, rerun `setup --json` and one `adversarial-review --wait` before trusting the flags.
- If any call fails (script missing, busy runtime, non-zero exit), report one non-blocking `codex-unavailable` finding and finish the review yourself.

## Write access across repositories

The plugin only knows the current repository. For a task that must edit more than one checkout, fall back to `codex exec`, which supports `--add-dir`, and tell the user before running it:

```bash
codex exec \
  --add-dir /path/to/other-repo \
  -s workspace-write \
  -o /tmp/codex-result.txt \
  "refactor the shared interface in both repos"
```

Each `--add-dir` makes that directory writable alongside the primary workspace. Use `-o` to capture the final message. For read-only cross-repo questions, name the extra paths in the focus text instead; the read-only sandbox can still read them.
