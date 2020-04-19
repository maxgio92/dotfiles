REPO=https://github.com/maxgio92/dotfiles.git
DOTFILES=$(HOME)/.dotfiles

.PHONY: init bash git i3 i3status terminator tmux vim xbindkeys

.DEFAULT_GOAL := all

all: init bash git i3 i3status terminator tmux vim xbindkeys

init:
	@if [ ! -d $(DOTFILES) ]; then \
		git clone -q $(REPO) $(DOTFILES); \
	else \
		pushd $(DOTFILES) > /dev/null && \
		git fetch -q && \
		git reset -q --hard origin/master && \
		popd > /dev/null; \
	fi

bash:
	@ln -sf $(DOTFILES)/bash/bashrc ~/.bashrc

git:
	@ln -sf $(DOTFILES)/git/gitconfig ~/.gitconfig

i3:
	@ln -sf $(DOTFILES)/i3/config ~/.config/i3/config

i3status:
	@ln -sf $(DOTFILES)/i3status/config ~/.config/i3status/config

terminator:
	@ln -sf $(DOTFILES)/terminator/config ~/.config/terminator/config

tmux:
	@ln -sf $(DOTFILES)/tmux/tmux.conf ~/.tmux.conf

vim:
	@ln -sf $(DOTFILES)/vim/vimrc ~/.vimrc

xbindkeys:
	@ln -sf $(DOTFILES)/xbindkeys/xbindkeysrc ~/.xbindkeysrc
