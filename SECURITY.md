# Security

## What a51-ws does and does not touch
- It talks only to your own iTerm2 over iTerm2's local Python API. No network access, no telemetry.
- Saved workspaces are plain JSON under `~/.config/a51-ws/`. They hold folder paths, split layout and
  font/color settings. They never hold commands, history, or secrets.
- The only text it ever types into a pane is the fixed line `claude --continue || claude`, and only in panes
  that were running Claude when saved. Nothing read from a saved file is ever run as a command.
- Workspace names become file names, so they are limited to letters, digits, `.`, `-`, `_` (no `/`, no `..`).
- Saved files are validated on load; a damaged or hand-broken file gives a clear error, never a crash.

## Reporting a problem
Please use GitHub's private reporting: on the repository page choose **Security → Report a vulnerability**.
Please do not file public issues for security problems. We aim to reply within a few days.
