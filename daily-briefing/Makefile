.PHONY: daily-briefing
daily-briefing:
	@command -v claude >/dev/null
	@install -Dm755 "$(DOTFILES)/bin/daily-briefing" "$(HOME)/.local/bin/daily-briefing"
	@install -Dm644 "$(DOTFILES)/daily-briefing/daily-briefing.service" "$(HOME)/.config/systemd/user/daily-briefing.service"
	@install -Dm644 "$(DOTFILES)/daily-briefing/daily-briefing.timer" "$(HOME)/.config/systemd/user/daily-briefing.timer"
	@systemctl --user daemon-reload
	@systemctl --user enable --now daily-briefing.timer
