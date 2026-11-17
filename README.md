# a51-ws — iTerm2 workspace switcher

**A free, open source tool from [Area 51 Software](https://area51software.io).**

Arrange iTerm2 once: windows, tabs, split panes, folders, fonts and colors, and a pane running
[Claude Code](https://claude.com/claude-code). Save it with a name. After a reboot or a crash, bring it
all back with one command. Keep a different workspace for each project.

```bash
a51-ws save myproject     # remember everything open in iTerm2 right now (asks first if the name exists)
a51-ws up myproject       # rebuild it in new windows; Claude restarts where it was running
a51-ws list               # your saved workspaces
a51-ws show myproject     # print one as a readable tree
a51-ws rm myproject       # delete one
```

## Install

Homebrew support is coming. For now, install from source with [pipx](https://pipx.pypa.io):

```bash
pipx install git+https://github.com/Area51Software/workspace-switcher
```

Needs macOS, Python 3.12 or newer, [iTerm2](https://iterm2.com), and iTerm2's Python API turned on
(**iTerm2 → Settings → General → Magic → Enable Python API**).

## What it restores, and what it never does

- Restores windows (size and position), tabs **and the titles you gave them**, split panes, each pane's folder, and each pane's font size and colors.
- Restarts **only** `claude`, as `claude --continue || claude`, in panes where Claude was running.
- **Never re-runs anything else** (deploys, `kubectl`, `ssh`, ...). Each pane just opens in its folder.
  Re-running a deploy because the Mac rebooted would be dangerous, so it is left to you.

Saved workspaces are plain JSON in `~/.config/a51-ws/NAME.json`, safe to hand-edit. Set `A51_WS_FOLDER`
to keep them somewhere else (for example a synced folder).

## Saving over an existing name

If the name already exists you are asked, the usual Unix way (Enter means no):

```
Workspace 'myproject' already exists. Overwrite it? [y/N]
```

Use `a51-ws save -y NAME` (or `--yes`) to skip the question in scripts. With no terminal to ask on, it
refuses rather than waiting forever. Names are case-sensitive, and since a Mac treats `Work.json` and
`work.json` as the same file, `Work` is refused when `work` exists, so one can never overwrite the other.

## If something goes wrong

- **"Could not connect to iTerm2"**: start iTerm2 and turn on its Python API (see above).
- **A saved file is damaged**: the error names the file and the line. Fix it by hand, or `a51-ws rm NAME` and save again.
- **A folder was deleted since you saved**: you get a warning and that pane opens in your home folder.
- Add `A51_WS_DEBUG=1` to any command to see the full technical error.

## Why "Area 51"?

Because we build unusual, useful things. `a51-ws` is the first of a set of small tools we are releasing
for free. More at [area51software.io](https://area51software.io).

## Develop

```bash
git clone https://github.com/Area51Software/workspace-switcher && cd workspace-switcher
scripts/setup-hooks.sh                    # stamps the build number on every commit
python3 -m venv .venv && .venv/bin/pip install -e '.[test]'
.venv/bin/python -m pytest
```

Versions look like `0.1.0.23`: `MAJOR.MINOR.PATCH` is set by hand in `VERSION`; the last number is the
commit count and only goes up. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

GPL-2.0-or-later. Copyright (C) 2026 Area 51 Software. See [LICENSE](LICENSE).
It depends on the `iterm2` Python package (GPL-2.0), which is why this tool is GPL too.
