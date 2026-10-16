---
name: daily-briefing
description: Build a daily briefing of what happened at the employer from the Slack channels the user follows and the pull requests proposed in the repositories they watch - announcements, launches, new features, decisions, incidents. Use when the user asks for a briefing, digest, catch-up, "what happened today", "what did I miss", "what's new at the employer", or wants to add or remove a followed channel or repository, even if they do not say "briefing".
---

# Daily Briefing

Read the followed Slack channels and watched repositories over a time window, keep what matters, and return a short briefing. This skill reads and stops; it never posts, reacts, or replies.

## Config

The followed sources live in `~/.config/daily-briefing/config.yaml`:

```yaml
channels:            # Slack channel names, no leading #
  - announcements
  - eng-announce
repos:               # owner/name; PRs opened here in the window are scanned
  - example-org/monorepo
ignore_authors:      # PR authors to drop (bots)
  - dependabot[bot]
  - renovate[bot]
  - octo-sts[bot]
```

**First run.** If the file is missing, call `slack_list_user_channels` with `exclude_archived: true` and `format: names_only`. Propose the channels whose names suggest company-wide news (`announce`, `general`, `release`, `product`, `eng`, `launch`, `incident`) and ask the user which to follow and which repositories to watch. Write the file with their answer, then continue.

**Edits.** When the user asks to follow or drop a channel or repository, edit the file and confirm in one line. Resolve an unknown channel name with `slack_search_channels` before adding it.

## Window

Read `~/.local/state/daily-briefing/last-run` (an ISO timestamp). Start the window there; if absent, start at 00:00 of the previous working day (Monday reaches back to Friday). A date or range in the request overrides both. Convert the start to Unix seconds with `date -d '<iso>' +%s` for Slack's `oldest`.

## Gather

Run these in parallel.

1. **Channels.** Resolve each channel name to an ID once with `slack_search_channels` and cache the IDs in the config as `name: id` comments. Call `slack_read_channel` with `oldest` set to the window start and `response_format: detailed`; page with `cursor` until the window is covered. Open a thread with `slack_read_thread` when the parent has 5+ replies or 5+ reactions, or when it announces something and the outcome sits in the replies.
2. **PRs.** For each watched repository: `gh search prs "feat in:title" --repo <repo> --created ">=<window start date>" --json url,title,author,isDraft,labels,state,commentsCount --limit 1000`. A monorepo opens hundreds of feature PRs a day, so never list them all: keep the PRs linked from the followed channels, then the 10 with the most comments, and report the rest as a count per top-level area (the scope in `feat(<scope>)`). Also collect every GitHub PR URL found in the channel messages.
3. **Fan-out.** With more than 6 channels, give batches of 3 channels to general-purpose subagents. Each returns candidate items in the item format below, with the Slack permalink for each. Read the channels yourself otherwise.

## Keep

Keep an item when it changes what someone at the employer knows or does:

- **Announcements:** launches, releases, GA or deprecation notices, org or process changes, all-hands notes.
- **New features:** PRs with a `feat` title or a feature label, design docs, RFCs, and demos. Drop chores, dependency bumps, typo fixes, CI tweaks, and authors in `ignore_authors`.
- **Decisions:** a thread that ends in a decision or a new owner.
- **Incidents:** outages, security advisories, CVE responses, and their resolution.
- **Asks of the user:** messages that mention the user or their team; put these first.

Drop greetings, kudos-only posts, bot noise with no human reply, and anything already in the previous briefing. Merge a Slack post and the PR it links into one item.

## Output

Return the briefing as Markdown. Group by section; skip empty sections. One line per item: what happened, then why it matters if not obvious, then the link. Cite Slack items by permalink and PRs by full URL.

```
# Briefing <YYYY-MM-DD> (<window start> to now)

## For you
- <who> asked <what> - <permalink>

## Announcements
- <what changed> - <permalink>

## New features
- <repo>: <feature> (<author>, <draft|open|merged>) - <url>

## Decisions
- <decision> (<channel>) - <permalink>

## Incidents
- <what>, <status> - <permalink>
```

Cap the briefing at 25 items; if more qualify, keep the ones with the most replies and reactions and end with `+N more in <channels>`.

If `~/.config/notes-repo.env` sets `NOTES_REPO` (default `~/notes`) and `$NOTES_REPO/notes/` exists, also write the briefing to `$NOTES_REPO/notes/<YYYY-MM-DD>-briefing.md`, replacing that day's file. Then write the current ISO timestamp to `~/.local/state/daily-briefing/last-run` (create the directory first).

## Anti-patterns

- Listing every message instead of picking the few that matter.
- Summarising a thread's first post when the replies changed the answer.
- Citing a PR by number without its URL.
- Posting, reacting, or marking anything read in Slack.
- Advancing `last-run` when a channel read failed; name the failed channel instead.
