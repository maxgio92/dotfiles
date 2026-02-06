.PHONY: flatpak-dump
flatpak-dump:
	flatpak list --app --columns=application > flatpaks.txt

.PHONY: flatpak-remote-ensure
flatpak-remote-ensure:
	flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo

.PHONY: flatpak-sync
flatpak-sync: flatpak-remote-ensure
	xargs flatpak install -y < flatpaks.txt

