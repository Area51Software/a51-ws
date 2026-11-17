#!/usr/bin/env bash
# One-time setup after cloning: use the version-controlled hooks in scripts/hooks.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath scripts/hooks
chmod +x scripts/hooks/* scripts/*.sh
echo "Hooks enabled (core.hooksPath = scripts/hooks)."
