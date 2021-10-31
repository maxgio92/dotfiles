REPO := https://github.com/maxgio92/dotfiles.git
REMOTE := origin
BRANCH := main
DOTFILES := $(HOME)/.dotfiles
git := $(shell command -v git 2>/dev/null)

.DEFAULT_GOAL := dotonly

dotonly: init update bash bin git i3 i3status terminator tmux vim xbindkeys xinit
all: init update bash bin git i3 i3status terminator tmux vim xbindkeys xinit openresolv dnsmasq systemd-logind systemd-system-resume

.PHONY: list
list:
	@$(MAKE) -pRrq -f $(lastword $(MAKEFILE_LIST)) : 2>/dev/null \
		| awk -v RS= -F: '/^# File/,/^# Finished Make data base/ \
		{if ($$1 !~ "^[#.]") {print $$1}}' \
		| sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$'

.PHONY: init
init:
	@if [ ! -d $(DOTFILES) ]; then \
		$(git) clone -q $(REPO) $(DOTFILES); \
	fi

.PHONY: update
update: SHELL := /usr/bin/env bash
update: init
	@if [ -d $(DOTFILES) ]; then \
		pushd $(DOTFILES) > /dev/null && \
		$(git) fetch -q && \
		$(git) reset -q --hard $(REMOTE)/$(BRANCH) && \
		popd > /dev/null; \
	fi

.PHONY: alacritty
alacritty: update
	@mkdir -p $(HOME)/.config/alacritty
	@ln -sf $(DOTFILES)/alacritty/alacritty.yml $(HOME)/.config/alacritty/alacritty.yml

.PHONY: bash
bash: update shell_aliases fzf
	@ln -sf $(DOTFILES)/bash/bash_profile $(HOME)/.bash_profile && \
	ln -sf $(DOTFILES)/bash/profile $(HOME)/.profile && \
	ln -sf $(DOTFILES)/bash/bashrc $(HOME)/.bashrc && \
	ln -sf $(DOTFILES)/bash/bash_logout $(HOME)/.bash_logout && \
	ln -sf $(DOTFILES)/bash/bash_completion $(HOME)/.bash_completion

.PHONY: bin
bin: update
	@ln -sf $(DOTFILES)/bin $(HOME)/.local/

.PHONY: krew
krew: update
	@test -d $$HOME/.krew || \
		( \
		  set -x; cd "$$(mktemp -d)" && \
			OS="$$(uname | tr '[:upper:]' '[:lower:]')" && \
			ARCH="$$(uname -m | sed -e 's/x86_64/amd64/' -e 's/\(arm\)\(64\)\?.*/\1\2/' -e 's/aarch64$$/arm64/')" && \
			KREW="krew-$${OS}_$${ARCH}" && \
			curl -fsSLO "https://github.com/kubernetes-sigs/krew/releases/latest/download/$${KREW}.tar.gz" && \
			tar zxvf "$${KREW}.tar.gz" && \
			KREW=./krew-"$${OS}_$${ARCH}" && \
			"$$KREW" install krew \
		)

.PHONY: fzf
fzf: update
	@test -d $(HOME)/.fzf \
		&& $(git) -C $(HOME)/.fzf pull \
		|| $(git) clone --depth 1 https://github.com/junegunn/fzf.git $(HOME)/.fzf
	@$(HOME)/.fzf/install --all

.PHONY: git
git: update
	@ln -sf $(DOTFILES)/git/gitconfig $(HOME)/.gitconfig

.PHONY: i3
i3: update
	@mkdir -p $(HOME)/.config/i3
	@ln -sf $(DOTFILES)/i3/config $(HOME)/.config/i3/config

.PHONY: i3status
i3status: update
	@ln -sf $(DOTFILES)/i3status/config $(HOME)/.config/i3status/config

.PHONY: sway
sway: update
	@mkdir -p $(HOME)/.config/sway
	@ln -sf $(DOTFILES)/sway/config $(HOME)/.config/sway/config

.PHONY: terminator
terminator: update
	@mkdir -p $(HOME)/.config/terminator
	@ln -sf $(DOTFILES)/terminator/config $(HOME)/.config/terminator/config

.PHONY: tmux
tmux: update
	@ln -sf $(DOTFILES)/tmux/tmux.conf $(HOME)/.tmux.conf

.PHONY: vim
vim: update
	@hash node || ./bin/install-ospackage.sh nodejs &> /dev/null
	@curl -sfLo $(HOME)/.vim/autoload/plug.vim --create-dirs \
		    https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim
	@vim +PlugInstall +qall
	@ln -sf $(DOTFILES)/vim/vimrc $(HOME)/.vimrc

.PHONY: waybar
waybar: update
	@ln -sf $(DOTFILES)/waybar $(HOME)/.config

.PHONY: wofi
wofi: update
	@ln -sf $(DOTFILES)/wofi $(HOME)/.config

.PHONY: xbindkeys
xbindkeys: update
	@ln -sf $(DOTFILES)/xbindkeys/xbindkeysrc $(HOME)/.xbindkeysrc

.PHONY: xinit
xinit: update
	@ln -sf $(DOTFILES)/xinit/xinitrc $(HOME)/.xinitrc

.PHONY: openresolv
openresolv: update
	@ln -sf $(DOTFILES)/etc/openresolv/resolvconf.conf /etc/resolvconf.conf

.PHONY: dnsmasq
dnsmasq: openresolv update
ifneq ($(shell id -u), 0)
	@echo "You must be root to perform this action."
else
	@mkdir -p /etc/dnsmasq.d \
		&& ln -sf $(DOTFILES)/etc/dnsmasq/dnsmasq.conf /etc/dnsmasq.conf \
		&& systemctl restart dnsmasq
endif

.PHONY: systemd-logind
systemd-logind: update
ifneq ($(shell id -u), 0)
	@echo "You must be root to perform this action."
else
	@mkdir -p /etc/systemd/logind.conf.d \
		&& cp $(DOTFILES)/etc/systemd/logind.conf.d/*.conf /etc/systemd/logind.conf.d/ \
		&& systemctl kill -s HUP systemd-logind
endif

.PHONY: systemd-system-suspend
systemd-system-suspend: update
ifneq ($(shell id -u), 0)
	@echo "You must be root to perform this action and set USERNAME variable."
else
	@cp $(DOTFILES)/etc/systemd/system/suspend@.service /etc/systemd/system/ \
		&& cp $(DOTFILES)/etc/systemd/system/resume@.service /etc/systemd/system/ \
		&& systemctl enable suspend@$(USERNAME).service \
		&& systemctl enable resume@$(USERNAME).service
endif

.PHONY: zsh
zsh: update shell_aliases prezto fzf
	@ln -sf $(DOTFILES)/zsh/zshrc $(HOME)/.zshrc

.PHONY: prezto
prezto: PREZTO_HOME := $(HOME)/.zprezto
prezto: update
	@if [ ! -d $(PREZTO_HOME) ]; then \
		$(git) clone --recursive https://github.com/sorin-ionescu/prezto.git \
			$(PREZTO_HOME); \
	else \
		pushd $(PREZTO_HOME) > /dev/null && \
		$(git) pull && \
		$(git) submodule sync --recursive && \
		$(git) submodule update --init --recursive && \
		popd > /dev/null; \
	fi

.PHONY: shell_aliases
shell_aliases: update
	@ln -sf $(DOTFILES)/shell_aliases \
		$(HOME)/.shell_aliases

.PHONY: bat
bat: update
	@hash bat || ./bin/install-ospackage.sh bat &> /dev/null
	@test -d $(HOME)/.config/bat || \
		mkdir $(HOME)/.config/bat
	@ln -sf $(DOTFILES)/bat/config \
		$(HOME)/.config/bat/config
