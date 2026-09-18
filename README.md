# dotfiles

Personal Linux configuration for shells, terminals, editors, desktops, and coding
agents. Make targets link configuration into your home directory and install
scripts, plugins, or services where needed.

## Quick start

Start with Git and GNU Make installed. Clone to `~/.dotfiles`, the path expected
by the Makefiles:

```sh
git clone https://github.com/maxgio92/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
make list
```

Choose individual targets. Review their recipes in the [Makefile](Makefile)
and back up existing configuration: many targets replace files with symlinks.
Some download and run installers. The Git configuration includes a personal
identity and signing settings.

For example, preview and apply the tmux configuration:

```sh
make -n tmux
make tmux
```

This links `~/.tmux.conf` and clones the tmux plugin manager if absent.
Install tmux separately. Other targets have their own dependencies.

To copy the helper scripts, install `rsync`, then run:

```sh
mkdir -p ~/.local/bin
make bin
export PATH="$HOME/.local/bin:$PATH"
```

Keep that PATH entry in your shell configuration.

## Choose what to configure

Run these targets from `~/.dotfiles`. The table lists common entry points;
`make list` shows the full target list.

| Area | Targets | Notes |
| --- | --- | --- |
| Shells | `bash`, `zsh` | Installs shell plugins; `zsh` also changes the login shell |
| Git | `git` | Links identity, aliases, and signing settings |
| Terminals | `tmux`, `alacritty`, `terminator` | Alacritty also installs themes and fonts |
| Editors | `vim`, `neovim` | Installs plugins and supporting tools |
| Desktops | `i3`, `i3status`, `sway`, `waybar`, `wofi`, `hyprland` | Select targets for your desktop |
| X11 | `xbindkeys`, `xinit` | Links key bindings and session configuration |
| Helpers | `bin` | Copies scripts into `~/.local/bin` |
| Agent tools | `claude`, `codex`, `pi`, `opencode` | Applies the selected tool's configuration |
| Worktrees | `workmux`, `orchestration` | Configures workmux or installs the agent coordination workflow |
| Desktop alerts | `agent-notify` | Installs the Linux systemd user socket and receiver |
| File sync | `syncthing-laptop`, `syncthing-workstation` | Applies the selected machine's sync role |

Plain `make` runs `dotonly`, a fixed set of shell, Git, desktop, terminal, and
editor targets. Use individual targets to control what changes.

`make all` currently depends on the missing `systemd-system-resume` target.
The existing `systemd-system-suspend` target installs both suspend and resume
units. It needs root and `USERNAME`. System targets such as `dnsmasq`,
`openresolv`, and `systemd-logind` also change files under `/etc`.

## Workflow guides

| Task | Guide |
| --- | --- |
| Coordinate agents in separate tmux panes and Git worktrees | [Agent orchestration](docs/orchestration.md) |
| Receive remote desktop alerts through SSH | [Remote notifications](docs/remote-agent-notifications.md) |
| Sync files between laptop and workstation | [Syncthing setup](syncthing/README.md) |
| Set up Pi agents, commands, and extensions | [Pi setup](pi/README.md) |
| Set environment variables for user services | [systemd user environment](environment.d/README.md) |

Shared agent definitions, skills, and command templates live in
[assistants/](assistants/). Tool-specific Makefiles install them for Claude,
Codex, and Pi. `make orchestration` installs the coordination skill, commands,
and `agent-work` helper; follow its guide for runtime requirements and use.

## Update

Pull changes on `main`, then rerun the targets you use:

```sh
cd ~/.dotfiles
git status --short
git pull --ff-only
make bin
```

Commit or stash local edits before pulling. Linked files reflect changes in the
checkout; copied scripts and service files need their install target rerun.
New skills or commands may also need their target rerun.

Avoid `make update` if you have local work: it runs `git reset --hard origin/main`
and discards tracked edits.
