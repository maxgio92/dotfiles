# Claude Code Configuration Template

This template provides a reusable, portable configuration for Claude Code that can be versioned and shared without exposing machine-specific paths or project details.

## Files

- **`CLAUDE.template.md`** - Generic template with placeholders
- **`CLAUDE.template.README.md`** - This file, explains usage

## Quick Start

1. **Copy template to home directory:**
   ```bash
   cp CLAUDE.template.md ~/CLAUDE.md
   ```

2. **Customize for your workspace:**
   - Edit `~/CLAUDE.md`
   - Replace `<workspace-root>` with your actual path
   - Add specific examples if helpful
   - Keep it **local** (don't version your customized version)

3. **Use with Claude Code:**
   - Claude will automatically read `~/CLAUDE.md` on startup
   - The session startup convention works immediately
   - Say "I work on [project]" to load project-specific context

## Version Control Strategy

### What to Version (Public/Shared)
- ✅ `CLAUDE.template.md` - The generic template
- ✅ `CLAUDE.template.README.md` - This usage guide
- ✅ Any scripts for generating local config

### What NOT to Version (Keep Local)
- ❌ `~/CLAUDE.md` - Your customized instance with real paths
- ❌ Project-specific examples that reveal internal structure
- ❌ Organization-specific information

### Recommended Setup

**Option A: In existing dotfiles repository**
```bash
# Add to your dotfiles repo
mkdir -p ~/.dotfiles/claude/
cp CLAUDE.template.md ~/.dotfiles/claude/
cp CLAUDE.template.README.md ~/.dotfiles/claude/

cd ~/.dotfiles
git add claude/
git commit -m "Add Claude Code configuration template"
```

**Option B: Separate repository**
```bash
# Create dedicated repo
mkdir -p ~/.claude-config
mv CLAUDE.template.* ~/.claude-config/

cd ~/.claude-config
git init
git add CLAUDE.template.*
git commit -m "Initial Claude Code configuration template"
git remote add origin <your-repo-url>
git push -u origin main
```

**Add to global gitignore:**
```bash
echo "CLAUDE.md" >> ~/.gitignore_global
```

## Updating Your Configuration

When you improve the template:

1. **Update the template:**
   ```bash
   # Edit the versioned template
   vim ~/.dotfiles/claude/CLAUDE.template.md
   git commit -am "Improve session startup convention"
   ```

2. **Regenerate your local config:**
   ```bash
   # Copy updated template
   cp ~/.dotfiles/claude/CLAUDE.template.md ~/CLAUDE.md

   # Re-apply your customizations
   # (or keep a separate local-customizations.md with your changes)
   ```

## Project-Specific Configuration

For each project you work on, create a `.claude/` directory:

```bash
cd ~/your-workspace/your-project
mkdir -p .claude
touch .claude/context.md
touch .claude/session-log.md
touch .claude/todos.md
```

These files should be **versioned with the project** so team members share context.

## Usage Example

Once setup, your workflow:

```bash
# Terminal 1: Start Claude Code
claude

# In Claude session:
User: "I work on my-api-project"

Claude automatically:
  1. Reads ~/CLAUDE.md (your global config)
  2. Finds my-api-project/.claude/
  3. Reads context.md, session-log.md, todos.md
  4. Reads my-api-project/docs/ if present
  5. Summarizes current state
  6. Ready to work!
```

## Sharing with Team

If you want team members to use this pattern:

1. **Share the template repository:**
   ```
   git clone <template-repo-url>
   cp CLAUDE.template.md ~/CLAUDE.md
   # Customize for your workspace
   ```

2. **Document team conventions:**
   - Add a section to template about team-specific patterns
   - Include links to internal documentation
   - Explain project structure conventions

3. **Keep project `.claude/` directories in repos:**
   - These are shared team context
   - Update session-log.md as team works
   - Track architectural decisions in context.md

## Migration from Existing Setup

If you already have a `~/CLAUDE.md` with hardcoded paths:

1. **Backup current version:**
   ```bash
   cp ~/CLAUDE.md ~/CLAUDE.md.backup
   ```

2. **Extract custom sections:**
   - Note any workspace-specific preferences
   - Save actual paths for reference
   - Keep any team conventions

3. **Start from template:**
   ```bash
   cp CLAUDE.template.md ~/CLAUDE.md
   ```

4. **Re-apply customizations:**
   - Add your actual workspace paths
   - Include your preferences
   - Keep it local (don't commit)

## Troubleshooting

**Q: Claude isn't loading my project context**
- Check: Does `[project]/.claude/` exist?
- Check: Did you say "I work on [project]" exactly?
- Check: Are the files readable?

**Q: Should I version my ~/CLAUDE.md?**
- No - it contains machine-specific paths
- Version the template instead
- Regenerate local from template when needed

**Q: Can I have different configs for different workspaces?**
- Yes - use environment variables or multiple template variants
- Example: `CLAUDE.template.work.md` and `CLAUDE.template.personal.md`
- Copy appropriate one to `~/CLAUDE.md`

## Benefits of This Approach

✅ **Portable** - Template works on any machine after customization
✅ **Shareable** - Team members can use same patterns
✅ **Private** - Your specific paths stay local
✅ **Maintainable** - Improve template without exposing setup
✅ **Consistent** - Everyone uses same conventions

## See Also

- Claude Code documentation: https://github.com/anthropics/claude-code
- Project-specific .claude/ pattern documentation (if you create it)
- Your team's internal wiki on development practices
