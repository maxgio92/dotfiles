---
description: Dastardly adversarially reviews a scope (working-tree diff by default; or a PR, branch, files) without modifying anything
---

Use the Agent tool to launch the dastardly agent for this review.

Scope: $ARGUMENTS

If no scope is given, review the repository's working-tree diff against HEAD.
A PR URL, branch name, base ref, directory, or file list narrows it instead.

Instruct dastardly to: review read-only (no file or index modifications);
challenge the design and problem framing first; and apply its severities and
output format.

Dastardly reviews through Codex by default: tell it to follow its "Second
Opinion via Codex" section (one adversarial review through the Codex plugin
with its rubric loaded as a Codex skill, one pushback turn, every Codex claim
vetted against the code, and a `codex-unavailable` nit instead of a failure
when Codex cannot run). Only when the scope text says "Claude only" does
dastardly review in Claude alone.

Relay dastardly's verdict and findings to the user. Do not apply fixes: that
is /implement-review's job, or the user's call.
