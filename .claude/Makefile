.PHONY: claude
claude: claude-config claude-hooks claude-skills claude-agents claude-commands claude-plugins

# The codex skill drives the official Codex plugin; install it once.
CODEX_PLUGIN := codex@openai-codex
CODEX_MARKETPLACE := openai/codex-plugin-cc

.PHONY: claude-plugins
claude-plugins:
	@command -v claude >/dev/null 2>&1 || { echo "  skip claude-plugins: claude not on PATH"; exit 0; }; \
	if claude plugin list 2>/dev/null | grep -q "$(CODEX_PLUGIN)"; then \
		echo "  plugin $(CODEX_PLUGIN) already installed"; \
	else \
		claude plugin marketplace list 2>/dev/null | grep -q "openai-codex" || claude plugin marketplace add $(CODEX_MARKETPLACE); \
		claude plugin install $(CODEX_PLUGIN) && echo "  installed plugin $(CODEX_PLUGIN)"; \
	fi

.PHONY: claude-config
claude-config:
	@mkdir -p $(HOME)/.claude/workflows $(HOME)/.claude/output-styles
	@ln -sfn $(DOTFILES)/.claude/settings.json $(HOME)/.claude/settings.json
	@if [ -e $(HOME)/.claude/CLAUDE.md ] && [ ! -L $(HOME)/.claude/CLAUDE.md ]; then \
		echo "  skip ~/.claude/CLAUDE.md (exists and is not a symlink)"; \
	else \
		ln -sfn $(INSTRUCTIONS) $(HOME)/.claude/CLAUDE.md; \
	fi
	@if [ -L $(HOME)/.claude/AGENTS.md ]; then rm $(HOME)/.claude/AGENTS.md && echo "  removed dead AGENTS.md link"; fi
	@{ printf -- '---\nname: house-style\ndescription: Communication Rules for every response\nkeep-coding-instructions: true\n---\n\n'; cat $(RULES); } \
		> $(HOME)/.claude/output-styles/house-style.md
	@ln -sfn $(DOTFILES)/.claude/file-suggestion.sh $(HOME)/.claude/file-suggestion.sh
	@ln -sfn $(DOTFILES)/.claude/statusline.sh $(HOME)/.claude/statusline.sh
	@ln -sf $(DOTFILES)/.claude/workflows/*.js $(HOME)/.claude/workflows/
	@echo "  linked settings.json, CLAUDE.md, file-suggestion.sh, statusline.sh, workflows; generated output-styles/house-style.md"

.PHONY: claude-hooks
claude-hooks:
	@mkdir -p $(HOME)/.claude/hooks
	@if [ -L "$(HOME)/.claude/hooks/*" ]; then unlink "$(HOME)/.claude/hooks/*"; fi
	@for src in $(DOTFILES)/.claude/hooks/*; do \
		[ -e "$$src" ] || continue; \
		name=$$(basename "$$src"); \
		target=$(HOME)/.claude/hooks/$$name; \
		current=$$(readlink "$$target" 2>/dev/null || true); \
		if [ -n "$$current" ] && [ "$$current" != "$$src" ]; then \
			echo "  skip hook $$name (existing symlink: $$current)"; \
		elif [ -e "$$target" ] && [ ! -L "$$target" ]; then \
			echo "  skip hook $$name ($$target exists and is not a symlink)"; \
		else \
			ln -sfn "$$src" "$$target" && echo "  link hook $$name"; \
		fi; \
	done
	@ln -sfn $(DOTFILES)/assistants/communication-rules $(HOME)/.claude/hooks/communication-rules
	@ln -sfn $(DOTFILES)/assistants/go-gate/go-gate.sh $(HOME)/.claude/hooks/go-gate.sh
	@echo "  linked shared communication-rules and go-gate hooks"

.PHONY: claude-skills
claude-skills:
	@mkdir -p $(HOME)/.claude/skills
	@for src in $(DOTFILES)/assistants/skills/*; do \
		name=$$(basename "$$src"); \
		target=$(HOME)/.claude/skills/$$name; \
		if [ -e "$$target" ] && [ ! -L "$$target" ]; then \
			echo "  skip skill $$name ($$target exists and is not a symlink)"; \
		else \
			ln -sfn "$$src" "$$target" && echo "  link skill $$name"; \
		fi; \
	done
	$(call prune_links,$(HOME)/.claude/skills,$(DOTFILES)/assistants/skills)

.PHONY: claude-agents
claude-agents:
	@mkdir -p $(HOME)/.claude/agents
	@ln -sf $(DOTFILES)/assistants/agents/*.md $(HOME)/.claude/agents/
	$(call prune_links,$(HOME)/.claude/agents,$(DOTFILES)/assistants/agents)
	@echo "  linked $$(ls $(DOTFILES)/assistants/agents/*.md | wc -l) agent(s)"

.PHONY: claude-commands
claude-commands:
	@mkdir -p $(HOME)/.claude/commands
	@ln -sf $(DOTFILES)/assistants/commands/*.md $(HOME)/.claude/commands/
	$(call prune_links,$(HOME)/.claude/commands,$(DOTFILES)/assistants/commands)
	@echo "  linked $$(ls $(DOTFILES)/assistants/commands/*.md | wc -l) command(s)"
