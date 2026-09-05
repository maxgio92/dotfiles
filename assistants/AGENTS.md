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

For non-trivial coding tasks (anything beyond a one-line or trivial fix), run
the implement-and-review loop: Peter implements, Dastardly reviews, Peter vets
and applies the confirmed blocking findings. Use the harness's implementation:
the `implement-and-review` workflow in Claude Code (task as args),
`/implement-review` in pi.

Skip the loop for trivial edits, docs, and config changes; handle those
directly. This is a strong default, not an absolute rule. The repository's
deterministic checks (the go-gate hook) run on every change regardless.

Commit boundaries: subagents (peter included) never commit; the main session
commits once the implementation converges, without asking the human. Only
publishing needs human approval: push, PR, issue, comment, reply.

For contributions to repositories I do not control (upstream issues, PRs,
review rounds), apply the `upstream-contribution` skill. It sequences the
loop above and gates every outward write (push, comment, PR, issue) on my
explicit approval.
