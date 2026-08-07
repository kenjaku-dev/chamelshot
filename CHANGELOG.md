# Changelog

All notable changes to ChamelShot.

## v5.1.0 — 2026-08-07

### Added

- **Benchmark dashboard (HTML report)** — `bench.py` gains `--html PATH`,
  which collects the suite and renders a self-contained dark dashboard
  (`benchmarks.html`, regenerate any time): a 3-release comparison table
  (v4.2.0 / v5.0.0 / v5.1.0) with lower-is-better delta chips vs the
  previous release, animated metric cards (CLI start, GUI import, daemon
  start/RSS, hot/cold capture, wheel size), and the GUI import profile as
  ranked bars. Warm-graphite OKLCH palette with a single amber accent,
  system-ui + mono pairing, layout-safe `scaleX` bar animations, and full
  `prefers-reduced-motion` support. Old-release numbers were measured by
  running the harness against git worktrees of those tags.
- **Dead-code hygiene (G7)** — a vulture pass (maintainability, not
  performance) removed five genuinely dead items: the never-sent `PING`
  IPC constant, the set-but-never-read `_original` countdown state, the
  unused tray `_items` bookkeeping and `update_icon` method (the icon was
  only ever set once, at construction), and an unused socket-path constant
  in the bench script. Everything vulture still flags is a false positive
  (Qt virtual methods, string-dispatched dbusmenu `_m_*` handlers, Gio
  signal args, pytest fixtures, mock kwargs) and is whitelisted in
  `[tool.vulture]` in pyproject.toml — run it with `uv run --with vulture
  vulture .`.
- **Event-driven history refresh (G5)** — the history dialog now refreshes
  via a `QFileSystemWatcher` (inotify) instead of polling every 2 s: new
  screenshots and external deletes appear immediately (~150 ms debounce
  coalesces bursts), with a 2 s fallback poll while the history dir doesn't
  exist yet (and to re-attach the watch once it does). Selection and scroll
  position survive every refresh, so a capture taken mid-session shows up
  without moving the user's place.
- **AppImage slimming (G4)** — the AppImage drops from 214 MB to ~63 MB
  (~70% smaller, target was ≤ 140 MB) by pruning what `--collect-all PySide6.*`
  drags in but the app never uses: the 1.1 GB of bundled icon themes, Qt
  locale/translations, the GTK platform-theme plugin (which alone pulled in
  libgtk-3, gdk-pixbuf, the glycin/openraw RAW decoders and a second ICU
  copy), the virtual-keyboard input-context plugin (which pulled the whole
  QML/Quick stack) and the PDF imageformat plugin (QtPdf). Remaining Qt libs
  are pruned by an ldd closure fixpoint over the bundle, keeping the core
  dlopen'd-by-name set (QtCore/Gui/Widgets/Network/DBus/OpenGL/WaylandClient/
  XcbQpa/EglFS*/Svg/WlShell + libpython). The build script now also cleans the
  AppDir between runs (stale files were silently shipping in previous builds).
- **Always-hot daemon (G3)** — `chamelshot --install-service` /
  `--remove-service` install a systemd user unit
  (`~/.config/systemd/user/chamelshot.service`, `Restart=on-failure`,
  `graphical-session.target`) and enable+start it; the unit template ships in
  `packaging/chamelshot.service` for packagers. `--install-autostart` now pins
  the resolved binary path (was the literal `chamelshot`, which broke for
  AppImage/venv installs). README documents autostart as the recommended
  keep-alive path. Measured with the G2 harness on niri: hot keybind
  ≈ 0.5 s vs cold ≈ 1.2 s — an always-hot daemon saves ~0.6 s per capture.
- **Automatic app-menu entry (D-series)** — pip/venv/pipx installs now get a
  launcher entry (`~/.local/share/applications/chamelshot.desktop`) with icon,
  created on first start and pinned to the real binary path. System-wide pip
  installs additionally ship the entry + icon via wheel data-files.
- **Preview zoom (F2)** — a Fit / 100% toggle for the preview window: 1:1
  pixels (scrollable) for inspecting detail before annotating, plus a
  WxH resolution label and `Z`/`F` keyboard shortcuts. Fit still honors
  `preview.max_width`.
- **Live history refresh (F3)** — the history browser polls the folder every
  2 s while visible, so new captures appear without reopening; thumbnails now
  load on a worker thread instead of freezing the dialog. The current
  selection and scroll position survive refreshes.
- **Launcher mnemonics (F4)** — Alt+R / Alt+W / Alt+F / Alt+M trigger each
  capture mode, and the launcher reliably takes keyboard focus when opened
  from tray/IPC on Wayland (deferred xdg-activation, verified on niri).

### Fixed

- **Launcher clipping (E1)** — the launcher window no longer compresses its
  buttons on scaled/HiDPI displays; its height is derived from the layout.
- **History placeholder hijack (E2)** — the "No screenshots yet" row can no
  longer become the current item and swallow Enter/C/Del.
- **Pin window visibility (E3)** — frameless pins get a visible frame/border
  and a corner resize grip, so dark screenshots no longer blend into dark
  wallpapers.
- **Shortcut validation (E4)** — the settings dialog rejects unparsable and
  duplicate shortcuts inline and blocks Save while the input is invalid.
- **Tray menu overflow (E5)** — long monitor names are elided in the monitor
  submenu; the full name rides in a `tooltip-text` property.
- **Wheel packaging (build fix)** — the wheel now includes the `theme` module
  (F1); previously it would fail to import after install.

### Refactored

- **Dev loop (G6)** — pre-commit now runs only the fast gates (ruff, format,
  whitespace, config checks, ~1 s); pyright and the full test suite moved to a
  pre-push hook. Local test runs are parallel (pytest-xdist, `--dist
  loadscope` keeps the dbus tray tests serialized): 169 tests in ~6 s instead
  of ~9 s sequential.
- **Centralized theme (F1)** — all stylesheets (launcher, history, pin,
  preview, settings) now build on shared tokens in `theme.py`; one value to
  change, no drift.

## v5.0.0 — 2026-08-06

The V5 release: monitor capture, pinning, clipboard + primary selection, a
CLI for scripted capture, thumbnail notifications, history UX, annotation
eraser/crop, and a validation + review pass over the whole tool.

### Features

- **Monitor capture (B1)** — capture a specific monitor. New `capture.monitor`
  setting (`focused` or an output name), a monitor mode in the launcher, and a
  monitor submenu in the tray. Note: monitor detection currently requires niri.
- **Pin screenshots (C1)** — pin a capture on screen as a frameless,
  always-on-top window (alt+pin, tray/launcher Pin, IPC/CLI). Pins are
  multiple and ephemeral: they are never saved to history, and all close on
  quit. Hover a pin for Copy / Save / Re-edit / Close.
- **Primary selection copy (C2)** — a "Copy Primary" action places the image on
  the Wayland primary selection (middle-click paste) via `wl-copy`, in
  addition to the regular clipboard. Rebound via
  `shortcuts.copy_primary` (default Ctrl+Shift+C). When `clipboard.tool` is
  `qt` (no `wl-copy`), the button is disabled and the action warns.
- **CLI + IPC capture (C3)** — capture by geometry, output, and window
  `app_id` without touching the combos:
  `--region WxH+X+Y`, `--output NAME`, `--window APP_ID`, plus matching IPC
  commands (`capture-geometry`, `capture-output`, `capture-window-app`).
- **Thumbnail notifications (C4)** — saved screenshots now show a thumbnail in
  the desktop notification (toggle with `general.notification_preview`).
- **Annotation eraser and crop (C5)** — restore strokes freehand (eraser) and
  crop to a dragged rectangle (commit with Enter, cancel with Escape). Both
  are undo-stack aware.
- **History UX (B2/B3)** — an improved recents list: re-edit any recent
  screenshot straight from the tray/history dialog, a thumbnail browser with
  keyboard navigation (arrows / Enter / C / Del / Esc), and a dark-styled
  dialog consistent with the rest of the app.
- **Settings validation (B4)** — the settings dialog now validates the save
  directory and filename format non-blockingly as you type (format/extension
  mismatches and non-writable target directories are flagged before you save).
  The writability check accepts directories that don't exist yet but whose
  nearest parent is writable (they are created on save).

### Fixes & refactors

- Consolidated the clipboard pipeline (Qt + `wl-copy`, incl. primary) into one
  module shared by preview, pin, history and the tray copy action.
- Fixed an N+1-edit latent bug where the built wheel/AppImage omitted the
  v5 modules (`clipboard`, `history`, `pin`, `dispatcher`) because they are
  lazy-imported; `pyproject.toml` and the AppImage build now bundle them.
- CI hygiene: `pyright`/`ruff` errors in new tests, `libegl1` for offscreen
  PySide6 tests, hermetic temp dirs for tray tests.
- Added **pre-commit hooks** matching CI: `ruff` check+format on staged files,
  then `pyright` and the full `pytest` suite on every commit.

### Dependencies

- `pyside6>=6.11.1`, `pygobject>=3.56.0` (unchanged); development tooling now
  pins `pytest>=9.1.1`, `ruff>=0.16.0`, `dbus-python>=1.4.0`,
  `pyinstaller>=6.21.0`.

### Installation notes

- **AUR package temporarily paused** — the Arch AUR is currently offline for
  maintenance, so the `chamelshot` AUR package has not yet been bumped to
  `5.0.0`. It will be updated as soon as the AUR is back up. Until then, use
  the AppImage from the [GitHub release](https://github.com/kenjaku-dev/chamelshot/releases)
  or `pip install chamelshot`.
- The GitHub release ships `chamelshot-5.0.0` as wheel, sdist and AppImage.

### Known limitations

- **Monitor mode is niri-only** — monitor enumeration/detection uses
  `niri msg outputs`; on other wlroots compositors, region / window /
  fullscreen capture still work, but the monitor submenu and `--output` are
  unavailable.
