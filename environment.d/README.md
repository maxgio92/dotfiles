# Environment variables

The user instance of systemd does not inherit any of the environment variables set in places like .bashrc etc. There are several ways to set environment variables for the systemd user instance:

1. For users with a `$HOME` directory, create a `.conf` file in the `~/.config/environment.d/` directory with lines of the form `NAME=VAL`. Affects only that user's user unit. See environment.d(5) for more information.
1. Use the DefaultEnvironment option in /etc/systemd/user.conf file. Affects all user units.
1. Add a drop-in configuration file in `/etc/systemd/system/user@.service.d/`. Affects all user units; see #Service example
1. At any time, use `systemctl --user set-environment` or `systemctl --user import-environment`. Affects all user units started after setting the environment variables, but not the units that were already running.
1. Using the `dbus-update-activation-environment --systemd --all` command provided by dbus. Has the same effect as `systemctl --user` import-environment, but also affects the D-Bus session. You can add this to the end of your shell initialization file.
1. For "global" environment variables for the user environment you can use the environment.d directories which are parsed by some generators. See environment.d(5) and systemd.generator(7) for more information.
1. You can also write a systemd.environment-generator(7) script which can produce environment variables that vary from user to user, this is probably the best way if you need per-user environments (this is the case for `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`, etc).

One variable you may want to set is PATH.

After configuration, the command systemctl --user show-environment can be used to verify that the values are correct. 

---

Read more on Arch [docs](https://wiki.archlinux.org/title/Systemd/User#Environment_variables) about Systemd.
