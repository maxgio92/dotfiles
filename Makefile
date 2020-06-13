REPO=https://github.com/maxgio92/dotfiles.git
REMOTE=origin
MASTER=master
DOTFILES=$(HOME)/.dotfiles
git=`which git`

.PHONY: init bash bin git i3 i3status terminator tmux vim xbindkeys xinit openresolv dnsmasq systemd-logind systemd-system-resume

.DEFAULT_GOAL := dotonly

dotonly: init update bash bin git i3 i3status terminator tmux vim xbindkeys xinit
all: init update bash bin git i3 i3status terminator tmux vim xbindkeys xinit openresolv dnsmasq systemd-logind systemd-system-resume

init:
	@if [ ! -d $(DOTFILES) ]; then \
		$(git) clone -q $(REPO) $(DOTFILES); \
	fi

update: init
	@if [ -d $(DOTFILES) ]; then \
		pushd $(DOTFILES) > /dev/null && \
		$(git) fetch -q && \
		$(git) reset -q --hard $(REMOTE)/$(MASTER) && \
		popd > /dev/null; \
	fi

bash: update
	@ln -sf $(DOTFILES)/bash/bash_profile ~/.bash_profile && \
	ln -sf $(DOTFILES)/bash/profile ~/.profile && \
	ln -sf $(DOTFILES)/bash/bashrc ~/.bashrc && \
	ln -sf $(DOTFILES)/bash/bash_aliases ~/.bash_aliases && \
	ln -sf $(DOTFILES)/bash/bash_logout ~/.bash_logout && \
	ln -sf $(DOTFILES)/bash/bash_completion ~/.bash_completion

bin: update
	@ln -sf $(DOTFILES)/bin ~/.local/

git: update
	@ln -sf $(DOTFILES)/git/gitconfig ~/.gitconfig

i3: update
	@ln -sf $(DOTFILES)/i3/config ~/.config/i3/config

i3status: update
	@ln -sf $(DOTFILES)/i3status/config ~/.config/i3status/config

terminator: update
	@ln -sf $(DOTFILES)/terminator/config ~/.config/terminator/config

tmux: update
	@ln -sf $(DOTFILES)/tmux/tmux.conf ~/.tmux.conf

vim: update
	@ln -sf $(DOTFILES)/vim/vimrc ~/.vimrc

xbindkeys: update
	@ln -sf $(DOTFILES)/xbindkeys/xbindkeysrc ~/.xbindkeysrc

xinit: update
	@ln -sf $(DOTFILES)/xinit/xinitrc ~/.xinitrc

openresolv: update
	@ln -sf $(DOTFILES)/etc/openresolv/resolvconf.conf /etc/resolvconf.conf

dnsmasq: openresolv update
	ifneq ($(shell id -u), 0)
		@echo "You must be root to perform this action."
	else
		@mkdir -p /etc/dnsmasq.d \
			&& ln -sf $(DOTFILES)/etc/dnsmasq/dnsmasq.conf /etc/dnsmasq.conf \
			&& systemctl restart dnsmasq
	endif

systemd-logind: update
	ifneq ($(shell id -u), 0)
		@echo "You must be root to perform this action."
	else
		@mkdir -p /etc/systemd/logind.conf.d \
			&& cp $(DOTFILES)/etc/systemd/logind.conf.d/*.conf /etc/systemd/logind.conf.d/ \
			&& systemctl kill -s HUP systemd-logind
	endif

systemd-system-suspend: update
	ifneq ($(shell id -u), 0)
		@echo "You must be root to perform this action."
	else
		@cp $(DOTFILES)/etc/systemd/system/suspend@.service /etc/systemd/system/ \
			&& cp $(DOTFILES)/etc/systemd/system/resume@.service /etc/systemd/system/ \
			&& systemctl enable suspend@.service \
			&& systemctl enable resume@.service
	endif
