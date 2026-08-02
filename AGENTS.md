# ChamelShot — dev guide for AI agents and contributors

Wayland screenshot tool (niri-first, works on any wlroots/Wayland compositor).
Qt6 (PySide6) GUI + system tray via the StatusNotifierItem spec + Gio/GVariant
dbusmenu; `grim`/`slurp` subprocesses for capture. Python 3.14 only.

## Commands (all via uv)

```sh
dbus-run-session -- uv run pytest -q    # test suite (40 tests; needs a dbus
                                        # session for tray tests)
uv run pytest -q test_capture.py test_config.py   # subset, no bus needed
uv run ruff check .                     # lint
uv run ruff format .                    # format (run before committing)
uv run pyright .                        # typecheck
uv run pyinstaller ...                  # see packaging/build-appimage.sh
packaging/build-appimage.sh 4.2.0       # builds AppImage into dist/
```

## Architecture

| module | responsibility |
|---|---|
| `main.py` | QApplication entry point, wiring, global shortcuts, launcher window |
| `tray.py` | SNI tray + dbusmenu (Gio/GVariant). **Wire-format-exact — see BUG_REPORT.md #29–#31 for every gotcha found** |
| `capture.py` | grim subprocess calls + QPixmap decoding + async threading |
| `editor.py` | pixel editor / annotations, save + copy-to-clipboard |
| `overlay.py`, `preview.py` | fullscreen selection overlay, preview window |
| `settings.py` | settings dialog UI (reads/writes `config.py` TOML store) |
| `config.py` | validated defaults (dataclass + loader) |
| `ipc.py` | single-instance unix-socket server (first instance) + `--command` client |
| `dispatcher.py` | `post()` — post callables from worker threads to the Qt main thread |
| `version.py` | `__version__` |
| `aur/` | Arch AUR packaging (PKGBUILD + .SRCINFO mirror) |
| `packaging/` | AppImage build script + desktop file |

## Conventions

- `[tool.ruff] line-length = 120`, target py314; ruff select E/F/I/N/W/UP.
- **No code comments unless they explain a non-obvious "why"** (e.g. wire-format
  traps in `tray.py`, the `except (A, B) as _` paren trick).
- Python 2-style `except (A, B):` is INVALID on 3.14 — always `as _`.
- Don't type-annotate gi repository imports; they have no stubs
  (`# pyright: ignore[reportAttributeAccessIssue]` on the import line).
- Tray tests (`test_tray.py`, `test_tray_watcher.py`) must run under
  `dbus-run-session`; keep them hermetic (per-run temp dirs — the real session
  bus on dev machines breaks them).
- Never run `pyright .` outside the venv context (`uvx pyright` skips venv
  resolution and misses gi errors); always `uv run pyright .`. dist/build are
  gitignored so CI typechecks only source.

## Release flow (vX.Y.Z)

1. `git tag -f vX.Y.Z && git push -f origin vX.Y.Z` — GitHub Actions runs
   lint → typecheck → build → release (PyPI + GitHub assets incl. AppImage).
2. AUR package `chamelshot` sources the tag tarball (sha256sums are SKIP);
   edit `aur/PKGBUILD`, regen `.SRCINFO` via `makepkg --printsrcinfo`, commit
   in the AUR clone, push. Same change in repo `aur/`.
3. Bump `version.py` + `pyproject.toml` version together.

## Gotchas (all documented in BUG_REPORT.md)

- dbusmenu GetLayout MUST reply `(u(ia{sv}av))`, children variant-wrapped;
  dbus-python cannot marshal it — use Gio/GVariant. GetGroupProperties /
  AboutToShowGroup return tuple-wrapped `(a(ia{sv}))` / `(a(ib))`.
- Waybar (and most SNIs) discover items ONLY via org.kde.StatusNotifierWatcher
  — `tray.py` re-registers on watcher appearance (Gio.bus_watch_name), with a
  bounded retry while the watcher owns the name but hasn't exported the object.
