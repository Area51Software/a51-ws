#!/usr/bin/env bash
# Stamp a51_ws/_version.py as MAJOR.MINOR.PATCH.BUILD.
#   MAJOR.MINOR.PATCH = the hand-set label in the VERSION file (never auto-advanced).
#   BUILD             = git commit count including the commit being made (never resets).
# Fails (never warns) when the new version would go BACKWARDS, and in a shallow clone,
# because a shallow commit count is wrong. Re-stamping the same count is allowed (amend).
# Usage: scripts/bump-version.sh [REPO_ROOT]
set -euo pipefail

repo_root="${1:-$(git rev-parse --show-toplevel)}"
cd "$repo_root"

if [ "$(git rev-parse --is-shallow-repository)" = "true" ]; then
  echo "bump-version: refusing to stamp in a shallow clone (the commit count would be wrong)." >&2
  exit 1
fi

version_label="$(tr -d '[:space:]' < VERSION)"
if ! [[ "$version_label" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "bump-version: VERSION must look like MAJOR.MINOR.PATCH, found '$version_label'." >&2
  exit 1
fi

if git rev-parse --verify -q HEAD >/dev/null; then
  new_build=$(( $(git rev-list --count HEAD) + 1 ))
else
  new_build=1
fi

version_file="a51_ws/_version.py"
if [ -f "$version_file" ]; then
  previous_version="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$version_file")"
  IFS=. read -r prev_major prev_minor prev_patch prev_build <<< "$previous_version"
  IFS=. read -r new_major new_minor new_patch <<< "$version_label"
  # Compare the whole tuple, left to right, numerically (never BUILD alone).
  for pair in "$new_major:$prev_major" "$new_minor:$prev_minor" "$new_patch:$prev_patch" "$new_build:$prev_build"; do
    new_part="${pair%%:*}"; previous_part="${pair##*:}"
    if [ "$new_part" -gt "$previous_part" ]; then break; fi
    if [ "$new_part" -lt "$previous_part" ]; then
      echo "bump-version: $version_label.$new_build is LOWER than the stamped $previous_version. Versions never go backwards." >&2
      exit 1
    fi
  done
fi

printf '__version__ = "%s.%s"\n' "$version_label" "$new_build" > "$version_file"
echo "bump-version: stamped $version_label.$new_build"
