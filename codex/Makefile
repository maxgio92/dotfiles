.PHONY: codex
codex: codex-hooks codex-skills codex-agents codex-legacy-skills codex-prompts

.PHONY: codex-legacy-skills
codex-legacy-skills:
	@[ -d $(CODEX_LEGACY_SKILLS) ] || exit 0; \
	for entry in $(CODEX_LEGACY_SKILLS)/*; do \
		[ -e "$$entry" ] || [ -L "$$entry" ] || continue; \
		name=$$(basename "$$entry"); \
		if [ -L "$$entry" ]; then \
			case "$$(readlink "$$entry")" in $(DOTFILES)/assistants/skills/*) rm "$$entry" && echo "  remove legacy skill link $$name";; esac; \
		elif [ -d "$$entry" ] && [ -e "$(DOTFILES)/assistants/agents/$$name.md" ] && [ -f "$$entry/SKILL.md" ] && [ ! -L "$$entry/SKILL.md" ]; then \
			rm -r "$$entry" && echo "  remove legacy agent persona $$name"; \
		fi; \
	done

.PHONY: codex-prompts
codex-prompts:
	@mkdir -p $(HOME)/.codex/prompts
	$(call prune_links,$(HOME)/.codex/prompts,$(DOTFILES)/codex/prompts)
	@ln -sf $(DOTFILES)/codex/prompts/*.md $(HOME)/.codex/prompts/
	@echo "  linked Codex prompts"

.PHONY: codex-hooks
codex-hooks:
	@mkdir -p $(HOME)/.codex
	@ln -sfn $(DOTFILES)/codex/hooks.json $(HOME)/.codex/hooks.json
	@if [ -L $(HOME)/.codex/AGENTS.md ]; then rm $(HOME)/.codex/AGENTS.md; fi
	@{ cat $(INSTRUCTIONS) && echo && cat $(RULES); } > $(HOME)/.codex/AGENTS.md
	@echo "  linked Codex hooks.json; generated AGENTS.md from global.md and rules.md"

# Codex reads user skills from ~/.agents/skills; $CODEX_HOME/skills is deprecated since 0.154.
CODEX_SKILLS := $(HOME)/.agents/skills
# Codex still loads the deprecated root; a duplicate skill name there makes a
# `$name` mention resolve to nothing, so dotfiles-owned entries are removed.
CODEX_LEGACY_SKILLS := $(HOME)/.codex/skills
# Marks persona dirs this Makefile copied, so pruning never touches user skills.
PERSONA_MARKER := .dotfiles-persona
.PHONY: codex-skills
codex-skills:
	@mkdir -p $(CODEX_SKILLS)
	@for src in $(DOTFILES)/assistants/skills/*; do \
		name=$$(basename "$$src"); \
		target=$(CODEX_SKILLS)/$$name; \
		case " $(CLAUDE_ONLY_SKILLS) " in *" $$name "*) \
			if [ -L "$$target" ]; then rm "$$target" || exit 1; echo "  remove Claude-only skill $$name"; fi; continue;; \
		esac; \
		if [ -e "$$target" ] && [ ! -L "$$target" ]; then \
			echo "  skip skill $$name ($$target exists and is not a symlink)"; \
		else \
			ln -sfn "$$src" "$$target" && echo "  link skill $$name"; \
		fi; \
	done
	$(call prune_links,$(CODEX_SKILLS),$(DOTFILES)/assistants/skills)

.PHONY: codex-agents
codex-agents:
	@mkdir -p $(CODEX_SKILLS)
	@for src in $(DOTFILES)/assistants/agents/*.md; do \
		name=$$(basename "$$src" .md); \
		target=$(CODEX_SKILLS)/$$name; \
		if [ -e "$$target" ] && [ ! -d "$$target" ]; then \
			echo "  skip agent persona $$name ($$target exists and is not a directory)"; \
		else \
			mkdir -p "$$target"; \
			if [ -L "$$target/SKILL.md" ]; then unlink "$$target/SKILL.md"; fi; \
			cp "$$src" "$$target/SKILL.md" && : > "$$target/$(PERSONA_MARKER)" && echo "  install agent persona $$name"; \
		fi; \
	done
	@for dir in $(CODEX_SKILLS)/*/; do \
		dir="$${dir%/}"; \
		[ -d "$$dir" ] || continue; \
		[ -L "$$dir" ] && continue; \
		[ -f "$$dir/$(PERSONA_MARKER)" ] || continue; \
		name=$$(basename "$$dir"); \
		[ -e "$(DOTFILES)/assistants/agents/$$name.md" ] && continue; \
		rm -r "$$dir" && echo "  prune agent persona $$name"; \
	done
