# Target selection

Prefer a Slack message URL whenever one is available:

```text
https://<workspace>.slack.com/archives/<channel-id>/p<digits>[?thread_ts=...]
```

A URL supplies the workspace, channel, and message timestamp. Pass it unchanged. With a URL target:

- `message get`, `edit`, `delete`, and `react` act on that message.
- `message list` returns the thread root and all replies.
- `message send` replies in that message's thread.
- `channel mark` marks through that message; `--ts` overrides the timestamp.

Use a channel name (`#general` or `general`) or a `C...`, `G...`, or `D...` channel ID only when no URL is available:

- `message get`, `edit`, `delete`, and `react` need `--ts`.
- `message list` reads channel history unless `--thread-ts` or `--ts` selects a thread.
- `message send` posts at the top of the channel unless `--thread-ts` selects a thread.

Name lookup goes through search and `conversations.list`, so it can miss a quiet or private channel. Resolve its ID with `agent-slack channel list` first.

`message send` also takes a `U...` or `W...` user ID and opens or reuses that user's DM. `user dm-open <users...>` returns a DM or group-DM channel ID for one to eight users; it is a write, so it goes through `publish`.

Channel, user, and canvas targets carry no workspace. With more than one workspace configured, pass `--workspace <url-or-name>` or set `SLACK_WORKSPACE_URL`.
