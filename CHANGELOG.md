# Changelog

## 0.1.0 (first public version, 2026-11-17)
- First public version: `save`, `up`, `list`, `show`, `rm`.
- Saves windows (size and position), tabs and the titles you set on them, split panes, each pane's folder, fonts and colors, and which panes ran Claude.
- Atomic saves, validated files, safe workspace names, plain-English errors when iTerm2 is not reachable.
- Saving over an existing workspace asks first (`[y/N]`; `-y`/`--yes` skips it). Names are case-sensitive, and names differing only by case are refused.
