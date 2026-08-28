# Retrospective: what a human reviewer caught that the agent loop missed

A change built and reviewed by the peter + dastardly loop went through six
rounds of human review before approval; a sibling change from the same loop
passed in one. The delta was not style or tests, both of which the loop
already polices, but a family of boundary questions the loop never asked.
This records the gap classes and the rules added to close them. Specifics of
the codebase are intentionally omitted.

## Root-cause classes

1. **No grounding in production artifacts.** A parser for text produced by an
   external system was built from an assumed format; the real artifacts had a
   different shape, so the feature could never fire in production. One test
   fixture used an invented log prefix that no real system emits.
2. **Untrusted-text boundaries.** Text that the subject under automation could
   influence was allowed to select the target of a write and supply values for
   a policy decision, with no walk of who can write each trusted byte.
3. **Cross-system boundary semantics.** Values validated in Go but consumed by
   another system (a shell arithmetic tool, a config engine) were checked with
   Go's semantics: an equality case failed the consumer's strict comparison, a
   maximum value could never pass, and number grammars Go accepts made the
   consumer error out.
4. **Guard asymmetry and path parity.** An invariant was enforced on one write
   path but not another, in one direction of change but not the other, and on
   one representation of the value (literal) but not another (indirected). One
   fix regressed the representation it did not consider.
5. **Singular assumptions.** "Exactly one entity per input" assumptions broke
   on the first real aggregate; the N>1 case always arrived from the reviewer.
6. **Downstream consumer contracts.** Result fields were left zero-valued or
   derived from a different candidate than the one actually selected, breaking
   consumers nobody had read.

## Orchestration failures (the operator's, not the agents')

- A review body was fetched truncated, so a third of its findings were never
  dispatched and the reviewer had to re-raise them. Rule: fetch review bodies
  unabridged before scoping fixes.
- A corner the in-loop reviewer had flagged as non-blocking was deferred; the
  human reviewer escalated the same corner next round. Rule: on actively
  reviewed changes, fix reachable-correctness corners in the same push.

## Changes made

- `agents/peter.md`: new "External Inputs and Cross-System Boundaries" section
  (artifact-grounded parsers, taint treatment of parsed text, consumer-grammar
  validation, guard parity at every writer and direction, N>1 first,
  one-selected-source results with the consumer read, representation re-check
  after guard fixes).
- `agents/dastardly.md`: new top-priority "Trust boundaries and cross-system
  semantics" review-target block (unverified input shape, taint walk, foreign
  semantics, guard parity, singular assumptions, consumer contracts; all
  blocking, reachable corners are blocking even when unlikely), plus a tool
  rule to verify parsers against a real captured artifact.

## Expected effect

Classes 1-3 become pre-coding checks and blocking review targets; classes 4-6
become named review questions. Replayed against the six-round history, the
loop converges in about two rounds: one genuine design discussion and one
iteration on a guard.
