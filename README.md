# a51-ws — save and restore your iTerm2 workspaces

**A free, open source tool from [Area 51 Software](https://area51software.io).**

Set up your terminal once. Get it all back with one command.

## The problem

If you work in the terminal all day, your screen is a carefully arranged workspace: several iTerm2
windows, a handful of tabs in each, each tab split into two or three panes, every pane sitting in the
right project folder, tabs named so you can find them, and one pane running an AI coding assistant such
as [Claude Code](https://claude.com/claude-code).

Then the Mac reboots, or crashes, or an update restarts it. All of that is gone, and you spend ten
minutes rebuilding it by hand: open the windows, split the panes, `cd` into every folder, retype the tab
names, restart the assistant. If you work on more than one project, you do it every time you switch.

## The solution

`a51-ws` remembers the arrangement under a name and rebuilds it on demand.

```bash
a51-ws save myproject     # remember everything open in iTerm2 right now
a51-ws up myproject       # rebuild it all in new windows
```

After a reboot or a crash, `a51-ws up myproject` puts back your windows (size and position), tabs **and
their titles**, split panes, each pane's folder, and each pane's font size and colors. Any pane that was
running Claude Code is restarted with `claude --continue || claude`, so it picks up where it left off.
Keep one workspace per project and switch between them by name.

```bash
a51-ws list               # your saved workspaces
a51-ws show myproject     # print one as a readable tree
a51-ws rm myproject       # delete one
```

**Why not just use iTerm2's own window arrangements?** They are a good built-in feature. `a51-ws` is for
when you also want: named workspaces stored as plain JSON files you can read, hand-edit, sync, or keep in
git; Claude Code restarted for you; and a plain-English check before anything is overwritten.

## What's New

- **0.1.0 — first public version.**
  - **Tab titles:** the titles you give your tabs are saved and put back.
  - **Safe overwriting:** saving over an existing name asks `[y/N]` first (`-y` skips the question).
    Names are case-sensitive, and names that differ only by capital letters are refused, because a Mac
    would treat them as the same file.
  - **Hardened:** saves are atomic (a crash can't leave a half-written file), hand-edited files are
    validated with clear error messages, and "can't reach iTerm2" tells you how to fix it.

The full history is in [CHANGELOG.md](CHANGELOG.md).

## Install

Homebrew support is coming. For now, install from source with [pipx](https://pipx.pypa.io):

```bash
pipx install git+https://github.com/Area51Software/workspace-switcher
```

Needs macOS, Python 3.12 or newer, [iTerm2](https://iterm2.com), and iTerm2's Python API turned on
(**iTerm2 → Settings → General → Magic → Enable Python API**).

## What it restores, and what it never does

- Restores windows (size and position), tabs and their titles, split panes, each pane's folder, and each pane's font size and colors.
- Restarts **only** `claude`, in panes where Claude was running.
- **Never re-runs anything else** (deploys, `kubectl`, `ssh`, ...). Each pane just opens in its folder.
  Re-running a deploy because the Mac rebooted would be dangerous, so that is left to you.
- It does **not** restore what was on screen (scrollback), running programs other than Claude, or titles of individual split panes.
- It works with iTerm2 on macOS only, and it never touches the network.

Saved workspaces are plain JSON in `~/.config/a51-ws/NAME.json`, safe to hand-edit. Set `A51_WS_FOLDER`
to keep them somewhere else (for example a synced folder).

## Saving over an existing name

If the name already exists you are asked, the usual Unix way (Enter means no):

```
Workspace 'myproject' already exists. Overwrite it? [y/N]
```

Use `a51-ws save -y NAME` (or `--yes`) to skip the question in scripts. With no terminal to ask on, it
refuses rather than waiting forever.

## If something goes wrong

- **"Could not connect to iTerm2"**: start iTerm2 and turn on its Python API (see Install).
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
