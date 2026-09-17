# Remote Claude alerts

Send alerts over SSH to `notify-send`. Keep Alacritty.

## Research: 2026-09-17

- The existing Claude hooks update workmux status. The installed clorch hook
  prints BEL and calls macOS `osascript`.
- [Alacritty](https://alacritty.org/config-alacritty.html#bell) can run a command
  on BEL, but that byte carries no project or window data.
- [tmux](https://raw.githubusercontent.com/tmux/tmux/master/tmux.1) requires
  `allow-passthrough all` for hidden panes. OSC delivery needs a terminal that
  handles the sequence and an attached client.
- [Claude](https://code.claude.com/docs/en/hooks#notification) supplies
  `notification_type` and `cwd`. Hook stdout does not reach the terminal directly.
- [OpenSSH](https://man.openbsd.org/ssh#R) can forward a remote Unix socket to
  a local socket. The laptop needs no SSH server.

## Plan

1. Add a Python sender and Linux receiver.
2. Add an async hook for permission, elicitation, and idle events.
3. Validate event types and sizes. Pass text as arguments to a fixed command.
4. Test socket delivery, malformed input, and disconnects.
5. Test real popups from visible and hidden remote tmux windows.

Python matches the existing hooks and needs no build step.
Rust may cut startup time. Neither version was benchmarked.

The sender drops events when disconnected. Retries and autostart remain future work.

## Setup

Both hosts need Python 3 and SSH socket forwarding.
The Linux laptop needs `notify-send` and a notification service.
Install the scripts on both hosts:

```sh
make bin
```

On the remote host:

```sh
make claude-config
mkdir -p ~/.local/state/agent-notify
chmod 700 ~/.local/state/agent-notify
```

Start the receiver in a laptop terminal within the desktop session:

```sh
agent-notify serve
```

Connect from another laptop terminal. Replace USER, SERVER, and the remote home
path with their real values:

```sh
ssh -o ExitOnForwardFailure=yes \
  -R /home/USER/.local/state/agent-notify/notify.sock:$HOME/.local/state/agent-notify/notify.sock \
  USER@SERVER
```

Attach tmux and start Claude. The tunnel handles events from hidden windows
while SSH stays connected. No tmux passthrough setting is needed.

Use one tunnel per remote socket. Its owner and remote root can submit alerts.
After a crash, stop the old process before removing its stale `notify.sock`.

### SSH host alias

Add this entry to the laptop's `~/.ssh/config`:

```sshconfig
Host workstation
    HostName SERVER_IP_OR_DNS
    User REMOTE_USER
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    ExitOnForwardFailure yes
    RemoteForward /home/REMOTE_USER/.local/state/agent-notify/notify.sock /home/LOCAL_USER/.local/state/agent-notify/notify.sock
```

Replace the placeholders and key path. Socket paths must be absolute.
Complete the receiver and directory setup above, then connect:

```sh
ssh workstation
```

See [RemoteForward](https://man.openbsd.org/ssh_config#RemoteForward).

## Checks

Run the automated tests:

```sh
python3 -m unittest discover -s tests -p 'test_agent_notify.py' -v
```

Send a sample from the remote host:

```sh
printf '%s\n' '{"notification_type":"permission_prompt","cwd":"/srv/example"}' \
  | agent-notify send
```

Repeat from a hidden tmux window. Trigger a real Claude permission prompt and
idle event. Confirm the popup names the source window. Disconnect SSH and
confirm Claude continues. Delivery failures go to stderr; the hook returns zero.

Nine tests passed with a fake `notify-send`.
Socket tests ran outside the sandbox. SSH and desktop checks remain open.
