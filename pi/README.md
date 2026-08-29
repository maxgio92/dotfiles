# Pi User Guide

These dotfiles configure Pi with shared agents, skills, prompt templates,
workflow commands, policy checks, and worktree status reporting.

See the [parity plan](../.pi/plan.md) for differences from the Claude and Codex
setups.

## Quick Start

Install Pi and link every managed resource:

```bash
cd ~/.dotfiles
make pi
pi
```

In Pi, run `/login`, choose OpenAI Codex, and use the browser-based ChatGPT
sign-in. Run `/model` to change the active model.

For a coding task:

```text
/code-implement add validation for empty configuration values
```

Peter implements on Fable. Dastardly reviews on Sol. Peter fixes confirmed
blocking findings, and Dastardly reviews again. The workflow stops when no
blocking findings remain or when it reaches the round limit.

## Custom Commands

| Command | Purpose |
|---|---|
| `/code-implement [--max-rounds N] <task>` | Run the Peter and Dastardly implementation loop. The default is 3 rounds; the allowed range is 1 to 10 |
| `/implement-review [--max-rounds N] <task>` | Alias for `/code-implement` |
| `/code-review [scope]` | Run one read-only Dastardly review on Sol. The default scope is the current branch against its merge base |
| `/loop [interval] [prompt]` | Repeat a prompt after the agent settles. The default interval is 10 minutes |
| `/loops` | List active loops |
| `/loop-stop [id\|all]` | Stop one loop, or stop all loops when no argument is given |

Loop intervals accept compound values such as `30s`, `5m`, `1h30m`, or `1d`.

```text
/loop 2m30s check CI and address any new failure
/loops
/loop-stop 1
```

## Prompt Templates

Prompt templates expand into the editor when invoked.

| Prompt | Purpose |
|---|---|
| `/orientate` | Read project guidance and report the stack, commands, conventions, and constraints |
| `/onboard` | Review a handover document, ask questions, and recommend the first task |
| `/botsnack` | Insert the short bot-snack message |

## Skills

Pi exposes installed skills as `/skill:<name>`. A direct request can also cause
Pi to load a matching skill, but the command form makes the choice explicit.

| Command | Purpose |
|---|---|
| `/skill:codex` | Ask Codex for a code review, deeper investigation, or second opinion |
| `/skill:coordinator` | Run and combine work from several worktree agents |
| `/skill:daily [date]` | Build and save an interactive daily note |
| `/skill:effective-go` | Apply Effective Go guidance while writing or reviewing Go |
| `/skill:export-stl` | Export OpenSCAD to STL and check the geometry |
| `/skill:merge` | Commit, rebase, and merge the current branch |
| `/skill:open-pr` | Draft a pull request and open the GitHub creation page |
| `/skill:openscad` | Create and revise versioned OpenSCAD models |
| `/skill:pr-review-message` | Draft a reply to a pull request review comment |
| `/skill:preview-scad` | Render an OpenSCAD model to PNG for visual checks |
| `/skill:rebase` | Rebase the current branch and resolve conflicts |
| `/skill:review-pr` | Draft a junior, senior, or staff pull request review without posting it |
| `/skill:session-journal` | Add new Claude, Codex, and Pi session activity to today's journal |
| `/skill:slack-message` | Draft a Slack message in the configured personal voice |
| `/skill:wiki` | Ingest notes, query the personal wiki, or check wiki health |
| `/skill:workmux` | Load the workmux command and workflow reference |
| `/skill:worktree` | Start one or more tasks in workmux worktrees |

Examples:

```text
/skill:review-pr owner/repository#123 --tier staff --with-senior
/skill:daily 2026-08-29
/skill:wiki query what did I decide about release automation?
/skill:worktree run the test and documentation tasks in separate worktrees
```

## Agents

The `subagent` extension runs agents in isolated Pi processes. Ask Pi to use one
agent, several agents in parallel, or a chain where each agent receives the prior
result. User agents are the default. Project agents under `.pi/agents` require a
trusted project and `agentScope: "both"` or `"project"`.

| Agent | Role |
|---|---|
| `brain` | Finds high-value missing tests and follows local test patterns |
| `casper` | Writes Linux and open-source articles in the configured British style |
| `dastardly` | Performs adversarial Go design and correctness reviews |
| `dexter` | Works on Nix, Nixpkgs, NixOS, Home Manager, and nix-darwin |
| `donatello` | Applies an existing implementation plan with focused checks |
| `edison` | Builds conference presentations |
| `garfield` | Handles Git, Conventional Commits, pull requests, and code explanations |
| `gonzales` | Finds useful performance changes in measured hot paths |
| `openscad-agent` | Runs the OpenSCAD modelling, preview, and STL export flow |
| `penfold` | Researches a topic and prepares a concise brief for later work |
| `penry` | Reviews code for maintainability, duplication, and simpler structure |
| `pepe` | Develops LÖVE 2D games with Lua 5.1 |
| `peter` | Implements small Go changes and runs build, test, and lint checks |
| `rosey` | Creates and refines agent prompts |
| `snagglepuss` | Reviews identifier names and naming consistency |
| `velma` | Creates verified project documentation for users and contributors |

Examples:

```text
Use the brain agent to find the three most useful missing tests.
Run penry and snagglepuss in parallel on the current diff.
Ask penfold to research the API, then pass its result to velma for documentation.
```

Use `/code-implement` for the standard Peter and Dastardly coding flow. It fixes
their models and enforces the structured review contract.

## Extensions

| Extension | Behaviour |
|---|---|
| `subagent` | Runs one agent, parallel agents, or a sequential agent chain in isolated contexts |
| `implement-review` | Registers `/code-implement`, `/implement-review`, and `/code-review` |
| `communication-rules` | Applies the shared prose rules to context, tool calls, and final replies |
| `go-gate` | Checks edited Go files and runs the final Go build, test, format, and lint gate |
| `loop` | Registers scheduled prompt loops for the current session |
| `workmux-status` | Marks the current tmux workmux window as `working` or `done` |

`implement-review/review-output.ts` is an internal child extension. It accepts
Dastardly's structured findings during the implementation loop and is not a
user command.

## Models

The default model is `openai-codex/gpt-5.6-sol` with medium thinking.

| Provider | Enabled models |
|---|---|
| OpenAI Codex | `gpt-5.6-sol`, `gpt-5.6-terra` |
| Anthropic | `claude-sonnet-5`, `claude-opus-5`, `claude-fable-5` |

`/code-implement` always uses `claude-fable-5` for Peter and `gpt-5.6-sol` for
Dastardly. `/code-review` always uses `gpt-5.6-sol`. Other agents inherit the
active model unless their agent file declares one.

Use `/model` or Ctrl+L to select a model. Use Shift+Tab to change thinking level.
Use Ctrl+P and Shift+Ctrl+P to cycle through the enabled models.

## Built-in Pi Commands

These commands come from Pi itself. Type `/` to search them in the editor.

| Command | Purpose |
|---|---|
| `/login`, `/logout` | Manage provider credentials |
| `/llama` | Manage llama.cpp router models |
| `/model` | Select the active model |
| `/scoped-models` | Choose the models used by Ctrl+P cycling |
| `/settings` | Change thinking, theme, delivery, and transport settings |
| `/resume` | Resume a saved session |
| `/new` | Start a new session |
| `/name <name>` | Name the current session |
| `/session` | Show the session file, ID, messages, tokens, and cost |
| `/tree` | Continue from an earlier point in the current session |
| `/trust` | Save the trust choice for the current project |
| `/fork` | Fork from an earlier user message |
| `/clone` | Copy the active branch into a new session |
| `/compact [prompt]` | Compact the current context |
| `/copy` | Copy the last assistant reply |
| `/export [file]` | Export the session to HTML or JSONL |
| `/import <file>` | Import and resume a JSONL session |
| `/share` | Upload a private GitHub gist with a shareable page |
| `/reload` | Reload extensions, skills, prompts, themes, and context files |
| `/hotkeys` | Show all keyboard shortcuts |
| `/changelog` | Show Pi version history |
| `/quit` | Exit Pi |

## Tools and Policy

The default tool set is `read`, `bash`, `edit`, `write`, `grep`, `find`, and
`ls`. The subagent extension adds the `subagent` tool. The implementation loop
loads `submit_review` only inside Dastardly's child process.

Pi asks before trusting project-local resources. It does not send install
telemetry or analytics. Requests may retry up to three times. The shared
communication rules and Go gate apply automatically.

Sessions are saved under `~/.pi/agent/sessions/`. Use `pi --no-session` for an
ephemeral run.

## Configuration Map

| Source | Live path | Purpose |
|---|---|---|
| `pi/settings.json` | `~/.pi/agent/settings.json` | Models, tools, trust, retries, telemetry, and theme |
| `pi/AGENTS.md` | `~/.pi/agent/AGENTS.md` | Personal writing rules and the default coding workflow |
| `pi/extensions/` | `~/.pi/agent/extensions/` | Custom commands and lifecycle behaviour |
| `assistants/agents/` | `~/.pi/agent/agents/` | Shared agent definitions |
| `assistants/skills/` | `~/.pi/agent/skills/` | Shared skills |
| `assistants/commands/{orientate,onboard,botsnack}.md` | `~/.pi/agent/prompts/` | Pi prompt templates |

Run `make pi` after adding a managed agent, skill, prompt, or extension. Run
`/reload` inside Pi after editing an existing resource.

## Common Problems

| Symptom | Fix |
|---|---|
| A custom command is missing | Run `make pi`, then `/reload` |
| A model is unavailable | Run `/login` for its provider, then select it with `/model` |
| `/code-implement` reports no diff | Give Peter a task that changes the working tree, or review existing work with `/code-review` |
| `/code-implement` rejects the diff size | Narrow the task. The workflow limits captured diffs to 1 MiB |
| A project agent needs approval | Run `/trust`, or use only the default user agents |
| Workmux status does not change | Run Pi inside the tmux session managed by workmux |
| A Go edit cannot finish | Read the gate output and fix the reported format, build, test, or lint failure |
