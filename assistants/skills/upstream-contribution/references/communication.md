# Maintainer communication

## Review replies

If the `pr-review-message` skill is available, apply it; it is the
source of truth for reply voice. Do not restate its rules here. When it
is not available: verdict first, then substance, one reply per finding,
reply in the thread the comment lives in, thank the reviewer when
opening a round.

## Registers

- PR bodies and issue bodies: terse, one line per paragraph (GitHub
  renders newlines), a couple of paragraphs over headed sections. State
  the behavior change and the motivation; skip narration of the work.
- Review replies: shorter still; settle the thread. See above.

## Substance rules

- Restate a sound counterargument once before implementing a review ask
  that contradicts it; then follow the maintainer's call.
- Surface every behavior change the maintainer has not seen (newly
  rejected inputs, spec deviations, shrunken scope after a rebase)
  rather than letting the diff speak.
- When a review reports something checkable in one command (a red
  build, a missing symbol), check it before drafting anything.
- Every claim in a reply must hold on the pushed head, not the local
  tree (invariant 4 in SKILL.md).
