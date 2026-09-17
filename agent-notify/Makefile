.PHONY: agent-notify
agent-notify:
	@command -v python3 >/dev/null
	@command -v notify-send >/dev/null
	@install -Dm755 "$(DOTFILES)/bin/agent-notify" "$(HOME)/.local/bin/agent-notify"
	@install -d -m700 "$(HOME)/.local/state/agent-notify"
	@install -Dm644 "$(DOTFILES)/agent-notify/agent-notify.service" "$(HOME)/.config/systemd/user/agent-notify.service"
	@install -Dm644 "$(DOTFILES)/agent-notify/agent-notify.socket" "$(HOME)/.config/systemd/user/agent-notify.socket"
	@systemctl --user daemon-reload
	@systemctl --user enable --now agent-notify.socket
	@systemctl --user try-restart agent-notify.service
