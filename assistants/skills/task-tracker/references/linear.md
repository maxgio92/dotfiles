# Linear

Mechanics for the `task-tracker` roles on Linear. Section order matches `github.md` and `local.md`.

## Resolution

A key such as `FUL-123` or a `linear.app` URL resolves here. Linear tools exist only when the harness provides them (Claude Code today); otherwise report the source as unreachable and ask the user for the issue body.

Workspace guard: write only when `get_team` resolves the key `FUL` (`list_teams` returns names, not keys). A blank creation target resolves here only when the repository's `origin` remote is under the work organisation named in SKILL.md; an explicit Linear target (a team name, a key, a URL) is honoured anywhere. Do not use an email-domain check; the Git identity in this repository is a personal address. When the team is not visible, report that and stop.

Links: use `https://linear.app/<workspace>/issue/<KEY>`. Never use the slugged URL that carries the title.

Fetch the team's statuses with `list_issue_statuses` once per run and match on the `type` field: `triage`, `backlog`, `unstarted`, `started`, `completed`, `canceled`, `duplicate`. Never match on a status name unless a rule below says so.

## New

`save_issue` with `team` set to `FUL`, `assignee: "me"`, `title`, `description`, and `state` set to the `triage`-type status. Add `parentId` for a child issue.

## Ready

A `backlog`-type status, `Backlog` by name when it exists. Move with `save_issue` carrying only `id` and `state`.

## Started

The first `started`-type status, or the one named `In Progress` when present. Move with `save_issue` carrying `id`, `state`, and `assignee: "me"`.

## In review

The `started`-type status named `In Review`. Forward-only: move from `started`, never back from `completed`. When no such status exists, skip the move and say so.

## Done

The `completed`-type status. Move with `save_issue` carrying only `id` and `state`.

## Inactive

Any `completed`, `canceled`, or `duplicate`-type status. Report the status and stop; do not edit, comment, or reassign.

## Classification

- `type` and `area`: labels from `list_issue_labels` for the team, applied with `addLabels`. Never create a label.
- `priority`: `save_issue` with `priority` 1 to 4.
- `estimate`: `save_issue` with `estimate` on the `sizing` scale. Parents carry none.

## Parent and order

Set `parentId` on each child. Order lives in the parent body's `Child issues` list, one line per child with `Depends on <KEY>` where needed.

Partial body edits always use `patch` operations, never a full `description` rewrite. This is what makes merge-never-replace hold mechanically.

## Durable record and long research

Durable record: `save_comment` with `issueId` and the record as Markdown with real newlines. One comment per landing.

Long research (the `long research` role in SKILL.md): `save_document` linked to the issue, then a one-line comment pointing at it. Never paste it into the description.

## Branch link

Branch name: the bare lowercased key, for example `ful-123`. Commit trailer: `Refs: <KEY>` with the uppercase key. Linear can close the issue when the merged pull request's branch contains the key, depending on the workspace's GitHub automation; check the issue state after merge before moving it to `done` by hand.
