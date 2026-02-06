# Claude Code - Global Instructions Template

> **TEMPLATE:** Customize this file for your workspace. Replace placeholders in angle brackets with your actual paths and preferences.

This file provides global guidance for Claude Code when working across all projects in this user's workspace.

## Project-Specific Context

**IMPORTANT:** For every project you work on, check for a `.claude/` directory in the project repository root. This directory contains project-specific context that takes precedence over these global instructions.

### Standard .claude/ Directory Structure

Each project should have:

```
project-root/
├── .claude/
│   ├── context.md       # Project-specific knowledge, architecture, patterns
│   ├── session-log.md   # Conversation history and decisions
│   └── todos.md         # Tasks, action items, and roadmap
```

### Session Workflow

**At the START of each session:**
1. Read `.claude/context.md` to understand the project architecture and patterns
2. Read `.claude/session-log.md` to see recent decisions and where we left off
3. Check `.claude/todos.md` to understand current priorities

**During the session:**
- Make architectural decisions based on context.md patterns
- Consider impact on existing work documented in session-log.md
- Update todos.md as tasks are completed or new ones emerge

**At the END of each session:**
1. **Update `session-log.md`** with today's progress, decisions made, and blockers encountered
2. **Update `context.md`** if architectural patterns changed or new discoveries were made
3. **Update `todos.md`** with completed tasks and newly identified work

### Session Startup Convention

When the user says **"I work on [PROJECT]"** or similar phrases ("working on [project]", "let's work on [project]"), automatically:

1. **Read all files in `[project]/.claude/`**
   - Use parallel reads for efficiency
   - Include all markdown files (context.md, session-log.md, todos.md, and any other .md files)

2. **Check for and read project documentation**
   - If `[project]/docs/` directory exists, read those documents
   - Prioritize README.md and architecture documents

3. **Confirm what was loaded**
   - List what context files were read
   - Summarize key points from session-log.md (where we left off)

4. **Ask about referenced materials**
   - If .claude/ files reference other documents (DEVELOPMENT.md, design docs), ask if those should be read too

**Example interaction:**
```
User: "I work on <your-project>"
Claude:
  - Reads: <your-project>/.claude/context.md, session-log.md, todos.md
  - Reads: <your-project>/docs/README.md, architecture.md (if they exist)
  - Confirms: "Loaded <your-project> context. Last session: <summary>. Current status: <summary>."
  - Asks: "Should I also read <referenced-doc> for additional details?"
```

This convention applies to any project with a `.claude/` directory structure.

### Keeping Context Focused

Context files should be concise and actionable:
- **context.md** - Current architecture, not full history
- **session-log.md** - Recent sessions (last 2-4 weeks), archive older content
- **todos.md** - Actionable items, remove completed tasks that aren't relevant anymore

**Concise is better** - Claude Code can read files, but focused context helps reasoning.

## Custom Assistants

This user has custom AI assistants (agents and commands) available at:
- **Agents:** `~/.dotfiles/assistants/agents/`
- **Commands:** `~/.dotfiles/assistants/commands/`
- **Global Rules:** `~/.dotfiles/assistants/rules/instructions.md`

### Available Agents

Specialized agents for different tasks:
- **brain** - Test engineer who suggests high-impact unit tests
- **casper** - Content creator for blog posts and video scripts
- **dexter** - Shell script expert
- **donatello** - Code implementation specialist
- **edison** - Conference presentation builder that adapts to talk format, depth, and style
- **garfield** - Git commit message expert
- **gonzales** - Performance optimization specialist
- **penfold** - Documentation overview creator
- **penry** - Code reviewer
- **pepe** - Generic coding assistant
- **rosey** - Meta-agent for creating and optimizing other agents
- **snagglepuss** - Naming conventions reviewer
- **velma** - Documentation specialist

These agents can be invoked in commands using `@agent-name` syntax or via the Task tool.

### Available Commands

Pre-built commands for common tasks in `~/.dotfiles/assistants/commands/`. Check that directory for the full list of available commands.

## Global Preferences

### Code Style
- Follow project-specific CLAUDE.md conventions when present
- Default to language/framework best practices
- Prioritize readability and maintainability

### Communication Style
- Be concise and technical
- Only use emojis if explicitly requested
- Focus on facts over validation
- No time estimates

### Tool Usage
- Use specialized tools over bash when available
- Read files before editing them
- Prefer parallel tool calls when operations are independent
- Use TodoWrite for complex multi-step tasks

## Workspace Structure

> **CUSTOMIZE:** Update this section with your actual workspace layout.

**Generic pattern:**
```
~/
├── CLAUDE.md (this file)              # Global instructions
├── <workspace-root>/                  # e.g., src/, projects/, code/, work/
│   └── <git-host>/                    # e.g., github.com/, gitlab.com/, or skip if not needed
│       └── <organization>/            # e.g., your-company/, your-username/
│           └── <repository>/
│               ├── CLAUDE.md          # Repository-level instructions (optional)
│               └── .claude/           # Repository-specific context
│                   ├── context.md
│                   ├── session-log.md
│                   └── todos.md
```

**Example (for reference - replace with your setup):**
```
~/
├── CLAUDE.md
├── projects/
│   └── my-company/
│       ├── backend-api/
│       │   └── .claude/
│       └── frontend-app/
│           └── .claude/
```

Or:
```
~/
├── CLAUDE.md
├── src/github.com/
│   └── username/
│       └── project/
│           └── .claude/
```

## Order of Precedence

When multiple instruction files exist:

1. **Project `.claude/context.md`** (highest priority)
2. **Project `CLAUDE.md`** (repository-level)
3. **Project `.claude/session-log.md`** (recent decisions)
4. **Home `~/CLAUDE.md`** (this file - global defaults)

Always respect project-specific conventions over global preferences.

---

## Customization Guide

To use this template:

1. **Copy to ~/CLAUDE.md**
   ```bash
   cp CLAUDE.template.md ~/CLAUDE.md
   ```

2. **Update Workspace Structure section**
   - Replace `<workspace-root>` with your actual path (e.g., `src/`, `projects/`)
   - Add specific examples from your workspace if helpful
   - Remove sections that don't apply

3. **Adjust Global Preferences**
   - Modify code style preferences if you have specific conventions
   - Update communication style if you prefer different defaults
   - Add any workspace-specific tool preferences

4. **Keep template versioned, keep ~/CLAUDE.md local**
   - Version this template in dotfiles or config repo
   - Add `~/CLAUDE.md` to `.gitignore_global`
   - Update template when you discover better patterns
   - Regenerate ~/CLAUDE.md from template when needed

5. **Optional: Add workspace-specific sections**
   - Common repositories
   - Team conventions
   - Frequently used commands
   - Links to internal documentation
