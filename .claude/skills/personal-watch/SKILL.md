---
name: personal-watch
description: Watch one person's Slack threads, GitHub PRs (opened, mentioned, and review-requested), and assigned Linear tickets. Two modes producer/consumer over a file queue. Use when asked to watch my notifications, set up a personal inbox or notification loop, drain the watch inbox, or keep an eye on replies, reviews, mentions, or ticket activity. Producer runs headless on a timer; consumer runs in a session or via the pw alias.
---

# personal-watch

Single producer, single consumer, filesystem queue. The producer polls and
enqueues; the consumer drains to the terminal. Only the producer touches Slack,
GitHub, or Linear.

Mode is the first arg: `produce` (default, headless/timer) or `consume`
(in-session `/loop` or the `pw` alias).

## Paths

State root: `${XDG_STATE_HOME:-$HOME/.local/state}/personal-watch/`

- `since`: ISO-8601 UTC instant the producer last polled through. Producer owns
  it; consumer never touches it.
- `inbox/`: one file per unread hit. Presence means unread.
- `archive/`: drained hits.

## Identity (config)

Read `~/.config/personal-watch.env` if present, else these defaults:

```
SLACK_USER_ID=U0000000000   # your Slack user id
GH_LOGIN=your-gh-login      # your GitHub login; gh @me must resolve to it
LINEAR_ASSIGNEE=me
REPO=owner/repo             # GitHub repo to scope PR searches to
```

`gh @me` must resolve to `GH_LOGIN`; Linear `me` to the same person.

## produce (headless, the only API caller)

1. Read `since`. If absent, write `now`, create `inbox/` and `archive/`, and
   stop (baseline; no history replayed).
2. Run the four watches for activity strictly after `since`, from someone other
   than the watched person. For each hit, write
   `inbox/<UTC>-<source>-<slug>.md` with this body:
   ```
   [<source>] <who>: <one-line summary>
   <link>
   seen <produce-run-time>
   ```
   `<UTC>` is `YYYYMMDDTHHMMSSZ` so files sort by time.
3. Write `since = now` (the run's start).

Watches:

- A. Slack: `slack_search_public` `from:<@$SLACK_USER_ID> is:thread`. For each
  thread root he authored, `slack_read_thread`, enqueue replies by others with
  ts after `since`. Slack `after:` is date-granular, so filter ts precisely.
- B. PRs opened: `gh search prs --repo $REPO --author @me --json number,title,url,updatedAt`.
  For each updated after `since`, read `gh pr view <n> --json reviews,comments`
  and `gh api repos/$REPO/pulls/<n>/comments`; enqueue reviews and comments by
  anyone other than `$GH_LOGIN` created after `since`.
- C. PRs mentioning him: `gh search prs --repo $REPO --mentions @me --json number,title,url,updatedAt`.
  Enqueue PRs newly mentioning him or with mention-activity after `since`.
- E. PRs review-requested: `gh search prs --repo $REPO --review-requested @me --json number,title,url,updatedAt,author`.
  A review request via the reviewers field does not always create a mention, so
  this is distinct from watch C. Enqueue PRs newly requesting his review after
  `since`. Skip bot authors (login ending in `[bot]`, or the automation accounts
  `dependabot`, `chainguard-factory`, `octo-sts*`, `poiana`); a human review
  request is the signal, the dependency and `[skillup]` bot flood is not.
- D. Linear assigned: `list_issues assignee $LINEAR_ASSIGNEE orderBy updatedAt`.
  Enqueue tickets created or assigned after `since`, and new comments after
  `since` (`list_comments issueId=...` per assigned ticket updated after
  `since`) by someone other than the watched person.

Headless caveat: GitHub uses the `gh` CLI (token auth, always works). Slack and
Linear are MCP servers; if a headless run lacks their auth, run those watches
best-effort and enqueue a `[personal-watch] degraded` entry naming the gap
rather than failing silently.

## consume (in-session or `pw`, no API, no auth)

1. List `inbox/*` (skip `archive/`). If empty, say "inbox empty" and stop.
2. Print each entry to the terminal, oldest first.
3. `mkdir -p archive/` and `mv inbox/* archive/`.

The consumer only reads, shows, and archives. It never calls Slack, GitHub, or
Linear, and never advances `since`.

## Driving it

- Producer: a systemd user timer runs `claude -p "/personal-watch produce"`
  every ~30 min (durable across sessions).
- Consumer: `/loop /personal-watch consume` in a session, or the `pw` shell
  alias when no session is open.

## Guardrails

Read-only against Slack, GitHub, and Linear. The producer writes only the local
queue; the consumer only moves files. Never merge, comment, or post anywhere
without an explicit go-ahead in a live turn.
