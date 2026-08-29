## What does this PR change?

## How was it tested?
- [ ] `uv run ruff check . && uv run ruff format --check .`
- [ ] `uv run pyright .`
- [ ] `QT_QPA_PLATFORM=offscreen dbus-run-session -- uv run pytest -n auto --dist loadscope -q`
- [ ] Manual smoke test on a real compositor (if UI-affecting)

## Checklist
- [ ] `version.py` / `pyproject.toml` versions untouched (or bumped via `scripts/release.sh`)
- [ ] CHANGELOG updated for user-visible changes
