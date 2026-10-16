.PHONY: all

.PHONY: brew-upgrade
brew-upgrade:
	brew bundle

.PHONY: brew-install
brew-install:
	brew bundle install

BREWFILE_LOCAL ?= $(HOME)/.config/brew/Brewfile.local

# Dump installed packages, minus the exact lines of the local Brewfile, so a
# machine-only package never lands in the tracked Brewfile.
.PHONY: brew-dump
brew-dump:
	brew bundle dump -f --file=Brewfile.dump
	if [ -f "$(BREWFILE_LOCAL)" ]; then \
		grep -vxF -f "$(BREWFILE_LOCAL)" Brewfile.dump > Brewfile || [ $$? -eq 1 ]; \
	else \
		cp Brewfile.dump Brewfile; \
	fi
	rm -f Brewfile.dump

