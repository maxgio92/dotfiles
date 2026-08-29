# Personal Writing Standards

Applies to all output: chat responses, code comments, commit messages, PR
descriptions, and docs.

## Punctuation

- No em dashes. Use colons, periods, semicolons, or parentheses.

## Vocabulary to Avoid

LLM-tell words: leverage, seamless, pivotal, comprehensive, robust, ensure,
delve, foster, embark, journey, landscape, realm, intricate, meticulous,
holistic, paramount, transformative, ships (as in "ships with"), wires
(as in "wires up"), complementary.

Puffery and disclaimers: "it's important to note", "it's worth mentioning",
"in essence", "fundamentally", "ultimately".

## Voice

- Use active voice and concrete language. State one fact per sentence.
- Put conclusions before reasoning.
- Do not add a preamble, restate the task, or close with a redundant summary.

## Structure

- Keep simple answers short. Do not use headers or bullets when a sentence is enough.
- State the result directly. Do not use a "good news / bad news" sandwich.

# Coding Workflow

For non-trivial coding tasks, run `/implement-review` with the task as its
argument. Peter implements, Dastardly reviews, Peter vets and applies confirmed
blocking findings, and Dastardly verifies the result.

Skip the workflow for trivial edits, docs, and config changes. This is a strong
default, not an absolute rule. Run the repository's deterministic checks for
every change.
