# GitHub

Mechanics for the `task-tracker` roles on plain GitHub repository issues. Section order matches `linear.md` and `local.md`.

## Resolution

`owner/repo#N` or a `github.com/<owner>/<repo>/issues/<N>` URL resolves here. Work through `gh issue view`, `create`, `edit`, `comment`, and `develop` with `--repo owner/repo`. Never call `gh project`: the local token lacks the `project` scope, so GitHub Projects is out of reach.

Status roles map to labels only when the repository has status-style labels (for example `status: in progress`, `in-review`). Check once per run with `gh label list --repo owner/repo`. When no such labels exist, skip the status move and say so; the issue's open or closed state is the only status GitHub keeps.

## New

`gh issue create --repo owner/repo --title <title> --body-file <path> --assignee @me`. Add a new-style label only when the repository has one.

## Ready

Swap the status label for the ready-style one with `gh issue edit <N> --remove-label <old> --add-label <new>`. Without such labels, skip and say so.

## Started

Assign with `gh issue edit <N> --add-assignee @me`. Swap to the started-style label when one exists; otherwise the assignment is the whole move.

## In review

Swap to the review-style label when one exists. Forward-only: never move back from a closed issue. Without such a label, skip and say so.

## Done

`gh issue close <N>`. A pull request merged into the default branch of the same repository with `Closes owner/repo#N` in its body does this on its own; confirm the issue closed before skipping the manual close.

## Inactive

A closed issue, whatever the reason. Report the state and stop; do not edit, comment, or reassign.

## Classification

- `type` and `area`: existing labels from `gh label list`, applied with `gh issue edit <N> --add-label`. Never create a label.
- `priority` and `estimate`: existing labels only, when the repository has them (for example `priority: high`, `size: M`). Without them, say so and leave the fields empty. Parents carry no estimate.

## Parent and order

GitHub has no parent field here. The parent body's `Child issues` list is the only link and the only order: one line per child as `owner/repo#N`, with `Depends on #N` where needed.

Edit the parent body by reading it with `gh issue view <N> --json body`, changing only the `Child issues` block, and writing the merged text back with `gh issue edit <N> --body-file <path>`. Never write a body composed from scratch.

## Durable record and long research

Durable record: `gh issue comment <N> --body-file <path>` with the record as Markdown. One comment per landing.

Long research (the `long research` role in SKILL.md): a comment when it fits GitHub's comment limit, otherwise a Markdown file committed on the task branch with a one-line comment linking to it. Never paste it into the issue body.

## Branch link

Branch: `gh issue develop <N> --checkout`, which links the branch to the issue. Commit trailer: `Refs: owner/repo#N`. Pull request body: `Closes owner/repo#N`, which closes the issue when the pull request merges into the default branch.
