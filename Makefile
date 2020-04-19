REPO=https://github.com/maxgio92/dotfiles.git
DOTFILES=$(HOME)/.dotfiles

.PHONY: init bash git i3 i3status terminator tmux vim xbindkeys

.DEFAULT_GOAL := all

all: init update bash git i3 i3status terminator tmux vim xbindkeys

init:
	@if [ ! -d $(DOTFILES) ]; then \
		git clone -q $(REPO) $(DOTFILES); \
	fi

update: init
	@if [ -d $(DOTFILES) ]; then \
		pushd $(DOTFILES) > /dev/null && \
		git fetch -q && \
		git reset -q --hard origin/master && \
		popd > /dev/null; \
	fi

bash: update
	@ln -sf $(DOTFILES)/bash/bashrc ~/.bashrc

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
