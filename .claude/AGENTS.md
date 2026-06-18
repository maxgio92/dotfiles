# Personal Writing Standards

Applies to all output: chat responses, code comments, commit messages, PR
descriptions, docs.

## Punctuation
- No em dashes. Use colons, periods, semicolons, or parentheses.

## Vocabulary to avoid
LLM-tell words: leverage, seamless, pivotal, comprehensive, robust, ensure,
delve, foster, embark, journey, landscape, realm, intricate, meticulous,
holistic, paramount, transformative, ships (as in "ships with"), wires
(as in "wires up"), complementary.

Puffery and disclaimers: "it's important to note", "it's worth mentioning",
"in essence", "fundamentally", "ultimately".

## Voice
- Active voice. Concrete language. One statement per fact.
- Conclusions before reasoning.
- No preamble, no restating the task, no closing summary that just
  rephrases what was already said.

## Structure
- Short responses for simple questions. No headers or bullets when a
  sentence will do.
- State the result directly. No "good news / bad news" sandwich.

# Coding Workflow

For non-trivial coding tasks (anything beyond a one-line or trivial fix), run
the `implement-and-review` workflow: @peter implements the change, @dastardly
reviews it, then @peter applies the confirmed blocking findings. Invoke it with
the task as args.

Skip the workflow for trivial edits, docs, and config tweaks; handle those
directly. This is a strong default, not an absolute rule. The go-gate hook
stays the deterministic check that runs on every change.
