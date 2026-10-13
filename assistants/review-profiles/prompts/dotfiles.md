# Dotfiles review rubric

- Make targets: a target links or copies files into the home directory. Check that it is idempotent, that it does not overwrite a regular file the user owns without saying so, and that a new file is reachable from an existing target.
- Helpers in `bin/`: the `bin` target copies them to `~/.local/bin`, so a helper must not read files relative to the repository. Check the shebang, the executable bit, and that rejections exit non-zero with one stderr line.
- Tests: a new helper gets a test under `tests/` in the convention of its language (`test_<name>.py` with `unittest`, or `<name>-tests.sh`).
- Assistant prompts and skills: shared rules live in one place under `assistants/`; a skill or agent links to them rather than copying them. Check that every path and line citation still points at the cited text.
- Portability: shell config must load on a host where an optional tool is missing.
- Public content: no secrets, tokens, internal hostnames, or employer names in config, fixtures, or prompts.
