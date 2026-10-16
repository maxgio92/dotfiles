.PHONY: standup-post
standup-post:
	@command -v claude >/dev/null
	@command -v gh >/dev/null
	@command -v jq >/dev/null
	@command -v flock >/dev/null
	@install -Dm755 "$(DOTFILES)/bin/standup-post" "$(HOME)/.local/bin/standup-post"
	@install -d -m700 "$(HOME)/.local/state/standup-post"
	@install -Dm644 "$(DOTFILES)/standup-post/standup-post.service" "$(HOME)/.config/systemd/user/standup-post.service"
	@install -Dm644 "$(DOTFILES)/standup-post/standup-post.timer" "$(HOME)/.config/systemd/user/standup-post.timer"
	@systemctl --user daemon-reload
	@systemctl --user enable --now standup-post.timer
