---
description: Dastardly adversarially reviews a scope (working-tree diff by default; or a PR, branch, files) without modifying anything
---

Use the Agent tool to launch the dastardly agent for this review.

Scope: $ARGUMENTS

If no scope is given, review the repository's working-tree diff against HEAD.
A PR URL, branch name, base ref, directory, or file list narrows it instead.

Instruct dastardly to: review read-only (no file or index modifications);
challenge the design and problem framing first; apply its severities and
output format; and, when the codex MCP tools are available, run the review
through one codex session with profile "review" and vet every codex claim
against the code before reporting, falling back to reviewing directly when
codex is unavailable.

Relay dastardly's verdict and findings to the user. Do not apply fixes: that
is /implement-review's job, or the user's call.
