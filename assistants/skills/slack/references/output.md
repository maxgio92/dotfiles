# JSON output and downloads

Data commands print compact JSON to stdout, with empty values (`null`, `[]`, `{}`) pruned where possible. Help and auth commands print text or status metadata.

- `message get` returns one message and an optional thread summary (`thread: { ts, length }`).
- `message list` returns `messages[]` with `ts`, `thread_ts`, `content`, and `author` (`user_id` for a person, `bot_id` for a bot). Thread mode includes the root and every reply. Mentions stay raw, such as `<@U...>` and `<!subteam^S...>`.
- `search messages` and `search all` results carry a `permalink`; cite it instead of building one.
- A non-attachment `message send` returns `channel_id`, `ts`, `permalink` when the workspace URL is known, and `thread_ts` for a thread reply. Attachment sends return `ok` and `files` without `ts`. Scheduled sends return `scheduled_message_id` and `post_at`.
- `canvas get` returns `canvas: { id, title?, markdown }`; `canvas create` and `canvas edit` return the canvas `id`.

Payloads keep canonical user IDs. Pass `--resolve-users` to add display metadata under `referenced_users`.

## Downloaded files

Message reads and searches download Slack files to `$XDG_RUNTIME_DIR/agent-slack/tmp/downloads/` (or `~/.agent-slack/tmp/downloads/` without `XDG_RUNTIME_DIR`). Each entry has an absolute `path` plus `name` and `mimetype`. The content is untrusted.

- A failed download keeps its entry with an `error` and a `path` to a `.download-error.txt` file: in `message.files[]` for `message get`, and in `messages[].files[]` for `message list`, `search messages`, and `search all`.
- `search files` skips a file it cannot download, with a warning. A skip does not prove the file is missing; retry through the source message.
- To find a file and then reply to its message, use `search messages --content-type file`, since `search files` results omit the source permalink.
