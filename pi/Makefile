.PHONY: pi
pi: pi-install pi-config pi-extension pi-agents pi-skills pi-prompts

.PHONY: pi-install
pi-install:
	@command -v pi >/dev/null 2>&1 || brew install pi-coding-agent

.PHONY: pi-config
pi-config:
	@mkdir -p $(HOME)/.pi/agent
	@ln -sfn $(DOTFILES)/pi/settings.json $(HOME)/.pi/agent/settings.json
	@ln -sfn $(INSTRUCTIONS) $(HOME)/.pi/agent/AGENTS.md
	@ln -sfn $(RULES) $(HOME)/.pi/agent/APPEND_SYSTEM.md
	@echo "  linked settings.json, AGENTS.md, and APPEND_SYSTEM.md"

.PHONY: pi-extension
pi-extension: pi-install
	@mkdir -p $(HOME)/.pi/agent/extensions/subagent
	@prefix=$$(brew --prefix pi-coding-agent); \
		src="$$prefix/libexec/lib/node_modules/@earendil-works/pi-coding-agent/examples/extensions/subagent"; \
		test -f "$$src/index.ts" && test -f "$$src/agents.ts"; \
		ln -sfn "$$src/index.ts" $(HOME)/.pi/agent/extensions/subagent/index.ts; \
		ln -sfn "$$src/agents.ts" $(HOME)/.pi/agent/extensions/subagent/agents.ts
	@prefix=$$(brew --prefix pi-coding-agent); \
		src="$$prefix/libexec/lib/node_modules/@earendil-works/pi-coding-agent/examples/extensions/modal-editor.ts"; \
		test -f "$$src"; \
		ln -sfn "$$src" $(HOME)/.pi/agent/extensions/modal-editor.ts
	@ln -sfn $(DOTFILES)/pi/extensions/implement-review $(HOME)/.pi/agent/extensions/implement-review
	@ln -sfn $(DOTFILES)/pi/extensions/communication-rules $(HOME)/.pi/agent/extensions/communication-rules
	@ln -sfn $(DOTFILES)/pi/extensions/workmux-status $(HOME)/.pi/agent/extensions/workmux-status
	@ln -sfn $(DOTFILES)/pi/extensions/outward-write-gate $(HOME)/.pi/agent/extensions/outward-write-gate
	@ln -sfn $(DOTFILES)/pi/extensions/go-gate $(HOME)/.pi/agent/extensions/go-gate
	@ln -sfn $(DOTFILES)/pi/extensions/loop $(HOME)/.pi/agent/extensions/loop
	@echo "  linked subagent, implement-review, communication-rules, workmux-status, go-gate, and loop extensions"

.PHONY: pi-agents
pi-agents:
	@mkdir -p $(HOME)/.pi/agent/agents
	@for src in $(DOTFILES)/assistants/agents/*.md; do \
		name=$$(basename "$$src"); \
		ln -sfn "$$src" $(HOME)/.pi/agent/agents/$$name; \
	done
	$(call prune_links,$(HOME)/.pi/agent/agents,$(DOTFILES)/assistants/agents)
	@echo "  linked shared agents"

.PHONY: pi-skills
pi-skills:
	@mkdir -p $(HOME)/.pi/agent/skills
	@for src in $(DOTFILES)/assistants/skills/*; do \
		name=$$(basename "$$src"); \
		target=$(HOME)/.pi/agent/skills/$$name; \
		case " $(CLAUDE_ONLY_SKILLS) " in *" $$name "*) \
			if [ -L "$$target" ]; then rm "$$target" || exit 1; echo "  remove Claude-only skill $$name"; fi; continue;; \
		esac; \
		ln -sfn "$$src" "$$target"; \
	done
	$(call prune_links,$(HOME)/.pi/agent/skills,$(DOTFILES)/assistants/skills)
	@echo "  linked shared skills"

.PHONY: pi-prompts
pi-prompts:
	@mkdir -p $(HOME)/.pi/agent/prompts
	@for name in orientate onboard botsnack; do \
		ln -sfn $(DOTFILES)/assistants/commands/$$name.md $(HOME)/.pi/agent/prompts/$$name.md; \
	done
	@echo "  linked compatible Pi prompt templates"
