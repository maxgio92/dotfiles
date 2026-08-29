# Pi Parity Plan

Claude and Codex provide extension mechanisms such as agents, skills, hooks,
plugins, MCP, and configuration. The behavior layered onto those mechanisms is
mostly custom to this setup.

| Custom capability | Current implementation | Pi status |
|---|---|---|
| Peter to Dastardly review loop | Custom JavaScript workflow with structured findings, bounded retries, and conditional approval in `.claude/workflows/implement-and-review.js` | Ported; Peter uses Fable and Dastardly uses Sol |
| Independent cross-model review | Peter implements on Fable; Dastardly reviews on Sol; Peter fixes confirmed blocking findings; Dastardly rechecks | Ported |
| Deterministic communication rules | Shared Python scanner blocks banned wording and punctuation across prompts, tools, final responses, and subagents | Ported for Claude Code, Codex, and Pi; also loaded by Peter and Dastardly child runs |
| Go quality gate | Automatically checks `gofmt` after edits and build, test, lint checks before an agent finishes | Ported through the shared checker and Pi lifecycle events |
| Workmux state reporting | Claude and Codex hooks set tmux window state | Ported for Pi with `working` and `done`; Pi exposes no matching permission-wait event |
| Clorch lifecycle integration | Notifications and events for tool calls, permissions, compaction, sessions, tasks, and subagents | Missing in Pi |
| Specialized agent library | 16 authored personas in `assistants/agents` for implementation, review, testing, docs, performance, naming, Nix, OpenSCAD, and other work | Shared source; installed as native agents in Claude and Pi, and as persona skills in Codex |
| Prompt command library | 24 authored commands for planning, implementation, reviews, commits, onboarding, documentation, and instruction maintenance | Three agent-neutral templates ported; the rest depend on Claude-specific agents or the Task tool |
| Worktree orchestration | `worktree`, `workmux`, and `coordinator` skills spawn, monitor, message, and merge parallel agents | Shared and installed in Claude, Codex, and Pi |
| Git lifecycle workflows | Custom merge, rebase, commit, PR creation, and review-response flows | Shared Git and PR skills installed in Claude, Codex, and Pi; Garfield is not required by implement-review |
| Writing personas | Separate Slack, PR-review, documentation, blog, and video-writing behavior | Slack and PR-review skills are shared; command-only blog and video flows remain unported |
| Session knowledge flows | `daily`, `session-journal`, `wiki`, onboarding, offboarding, and orientation prompts | Daily, wiki, and a three-format session journal are shared; command-only flows remain unported |
| OpenSCAD pipeline | Agent plus preview, comparison, STL export, and geometry validation skills | Shared skills and persona installed in Claude, Codex, and Pi |
| Claude-to-Codex consultation | Custom consultation skill with `review` and `deep` profiles, multi-turn pushback, and directory handling | Shared skill installed in Claude, Codex, and Pi; available tools still differ by runtime |
| File completion UI | Custom file-suggestion command in `.claude/file-suggestion.sh` | Missing |
| Permissions and execution policy | Claude auto mode, Codex automatic approval review, prefix rules, trust settings, model profiles, retry policy, and sandbox choices | Pi has only an initial trust/tool/retry policy |
| Connector selection | Slack and LSP plugins in Claude; Linear MCP in Codex | Configured locally, but the connector implementations are third-party |
| Personal writing instructions | Shared voice, punctuation, vocabulary, and workflow defaults | Ported to `pi/AGENTS.md` |
| Effective Go guidance | Shared language conventions skill | Ported |
| Scheduled prompt loop | Repeats a prompt within an open session at a custom interval | Ported through `/loop`, `/loops`, and `/loop-stop` |
