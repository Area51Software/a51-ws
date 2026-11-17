# Contributing

Thanks for helping. Small, focused changes are easiest to review.

1. Fork, then `scripts/setup-hooks.sh` and install with `pip install -e '.[test]'`.
2. Add or update a test with your change, and run `python -m pytest`.
3. Names must be clear: a reader should never have to reconcile a variable name against the thing next to it.
4. By contributing you agree your work is licensed GPL-2.0-or-later, like the rest of the project.

## Versions

`MAJOR.MINOR.PATCH.BUILD`. The first three numbers are set by hand in `VERSION`; BUILD is the git commit
count, stamped by `scripts/hooks/pre-commit`, and a version may never be lower than an earlier one.
