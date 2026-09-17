# Syncthing

The laptop and workstation keep local copies of one shared folder.
Changes and deletions sync in both directions when both machines are online.

| Role | Share path |
| --- | --- |
| Laptop | `${XDG_DATA_HOME:-$HOME/.local/share}/workstation` |
| Workstation | `${XDG_DATA_HOME:-$HOME/.local/share}/laptop` |

XDG has no standard folder for synced files. These paths keep them under the
XDG data directory. Downloads sync only when saved or moved into the share.
Set the browser download destination to this path on each machine.
Downloads written directly to their final name may sync before completion.

## Setup

Requires Linux, a systemd user session, Bash and Syncthing 2.x.
The Make targets install Syncthing with Homebrew if it is missing.
The package is also declared in `linuxbrew/Brewfile`.

On the laptop:

```sh
cd ~/.dotfiles
make syncthing-laptop
```

On the workstation, with the same dotfiles checkout:

```sh
cd ~/.dotfiles
make syncthing-workstation
```

Each command prints that machine's public device ID. Set `LAPTOP_ID` and
`WORKSTATION_ID` in `syncthing/devices.env`. Keep that file identical in both
checkouts, then rerun each machine's target. You can retrieve the ID later:

```sh
make syncthing-id
```

To start the workstation service at boot and keep it running after logout:

```sh
sudo loginctl enable-linger "$USER"
```

Enable lingering on the laptop too if sync should run outside login sessions.
Otherwise the service starts with the user session.

## Configuration

`settings.env` declares the shared folder ID, bidirectional mode, file watcher,
hourly rescan and ten retained versions. `stignore` skips common browser
temporary files. Reapply the role target after changing these files.
File versioning preserves files replaced or deleted by the other machine.
It does not preserve local changes. Conflict copies need manual resolution.

The setup preserves existing Syncthing folders and devices. It owns the
`work-files` folder settings, its `.stignore`, and the user service.
Reapplying removes other peers from this shared folder. It leaves their
global device entries and access to unrelated folders intact.

Syncthing writes its config, certificate and private key to
`${XDG_CONFIG_HOME:-$HOME/.config}/syncthing`. Its database lives in
`${XDG_STATE_HOME:-$HOME/.local/state}/syncthing`.
These generated files stay outside Git. Do not copy a device's keys to the
other machine. Reapplying the target preserves them.
The installed launcher retains the XDG paths used during setup.
Set a custom `XDG_CONFIG_HOME` for the systemd user manager's login session
before setup so it can find the installed unit. Stop the service before
changing XDG roots. Move the existing config and state to the new roots before
reapplying if you want to retain the device identity and database.

The GUI listens on loopback at `http://127.0.0.1:8384`.
Use an SSH tunnel for remote access. Syncthing uses discovery and relays by
default, so a public inbound firewall rule is not required for relay use.
Direct connections can be faster when TCP and UDP port 22000 are reachable
over a private network. No firewall rules are changed by these targets.

```sh
systemctl --user status syncthing
journalctl --user -u syncthing
```

Stop any other Syncthing service before setup. Do not also run it through
Homebrew services. Automatic binary upgrades are disabled; update the package
through Homebrew.

References: [CLI](https://docs.syncthing.net/users/syncthing.html),
[versioning](https://docs.syncthing.net/users/versioning.html),
[firewalls](https://docs.syncthing.net/users/firewall.html).
