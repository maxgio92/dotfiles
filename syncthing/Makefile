.PHONY: syncthing-install syncthing-laptop syncthing-workstation syncthing-id
syncthing-install:
	@command -v syncthing >/dev/null 2>&1 || brew install syncthing

syncthing-laptop: syncthing-install
	@bash "$(DOTFILES)/syncthing/setup.sh" laptop

syncthing-workstation: syncthing-install
	@bash "$(DOTFILES)/syncthing/setup.sh" workstation

syncthing-id:
	@bash "$(DOTFILES)/syncthing/run.sh" device-id
