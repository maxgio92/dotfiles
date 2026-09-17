# Role-neutral global rules and the canonical Communication Rules. Every
# harness loads both; see the claude-config, codex-hooks, and pi-config targets.
INSTRUCTIONS := $(DOTFILES)/assistants/instructions/global.md
RULES := $(DOTFILES)/assistants/communication-rules/rules.md

.PHONY: assistants
assistants:
	test -L $(HOME)/.config/assistants || \
		ln -s $(DOTFILES)/assistants $(HOME)/.config/assistants
	@[ ! -f $(HOME)/CLAUDE.md ] || echo "  remove $(HOME)/CLAUDE.md if it is the old template copy; every harness under $(HOME) loads it"

# Agent prompt token budget (write-assistant doctrine): 400-700 words,
# hard cap 1200 for prompts that carry examples.
.PHONY: check-agents
check-agents:
	@fail=0; for f in $(DOTFILES)/assistants/agents/*.md; do \
		w=$$(wc -w < "$$f"); \
		if [ $$w -gt 1200 ]; then echo "FAIL $$(basename $$f): $$w words (cap 1200)"; fail=1; \
		elif [ $$w -gt 700 ]; then echo "warn $$(basename $$f): $$w words (budget 700)"; fi; \
	done; exit $$fail

# Every agent needs a routing row in the delegate-task skill, or an orchestrator
# cannot pick it.
ROUTING := $(DOTFILES)/assistants/skills/delegate-task/SKILL.md

.PHONY: check-routing
check-routing:
	@[ -f $(ROUTING) ] || { echo "FAIL: delegate-task skill absent"; exit 1; }; \
	fail=0; for f in $(DOTFILES)/assistants/agents/*.md; do \
		name=$$(basename "$$f" .md); \
		grep -Eq "^(- |\| *)\`$$name\`" $(ROUTING) || { echo "FAIL $$name: no row in delegate-task/SKILL.md"; fail=1; }; \
	done; exit $$fail

# global.md is always loaded, so it stays under 400 words and passes its own
# Communication Rules gate.
.PHONY: check-instructions
check-instructions:
	@w=$$(wc -w < $(INSTRUCTIONS)); \
		[ $$w -le 400 ] || { echo "FAIL global.md: $$w words (cap 400)"; exit 1; }
	@python3 $(DOTFILES)/assistants/communication-rules/scanner.py \
		--policy-json $(DOTFILES)/assistants/communication-rules/policy.json \
		--rules $(RULES) scan-file $(INSTRUCTIONS) >/dev/null \
		|| { echo "FAIL global.md: Communication Rules breach"; exit 1; }

# Remove dangling symlinks in $(1) that point into source root $(2), so
# deleting a source file uninstalls it on the next run. Entries that are
# not symlinks, or that link outside $(2), are left alone.
define prune_links
@for target in $(1)/*; do \
	[ -L "$$target" ] || continue; \
	case "$$(readlink "$$target")" in $(2)/*) ;; *) continue ;; esac; \
	[ -e "$$target" ] && continue; \
	rm "$$target" && echo "  prune $$(basename "$$target")"; \
done
endef

# Skills that drive a Claude Code plugin; pi and Codex run the same agents
# natively and must not see them.
CLAUDE_ONLY_SKILLS := codex
