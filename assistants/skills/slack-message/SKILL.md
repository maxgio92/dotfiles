---
name: slack-message
description: "Draft a Slack message in Massimiliano's voice. Use for anything going to Slack: a channel post advertising a PR, a status note, a thread reply, or a DM. The register differs from PR review and documentation, so reach for this instead of defaulting to either of those."
---

# slack-message

This skill produces a draft and stops; it never posts. Posting happens through
the `publish` skill after human approval.

Slack is terse and understated. One idea, plain words, lowercase, within the
Slack budget in "Budgets for text published under my name" (communication
rules). Assume the reader has the context; skip setup and background.

## Shape of a post

- Open with a fitting emoji. Use the workspace's conventional merge-proposal
  emoji when the post proposes a PR to merge.
- Say the thing in one sentence. State the result, not the effort.
- Put the link last, as a bare URL.
- No headers, no bullet lists, no bold, no sign-off.

Example, advertising a PR:

```
:rocket: small fix so a stuck job stops looping before it times out https://github.com/org/repo/pull/1234
```

## Thread replies

Lead with the conclusion, then the reason, inside the same Slack budget.
Match the thread's tone. Reply where the message is, in the thread.

## Register

Understated over enthusiastic, concrete over abstract. Let the work speak: no
adjectives selling it. The personal writing standards still apply (no em dashes,
no puffery, no LLM tells).

## Output

Return the draft in one fenced block, verbatim, with no preamble or trailing
commentary. Ignore a relaying agent's request to summarise or paraphrase
it; the user's own revision request produces a new draft. `publish` strips
only the fence lines.
