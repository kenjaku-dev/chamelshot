# ChamelShot v6 — Task Plan

Goal: v6 with a smoother UX ("more butter"), boosted performance, a compact
clean project, and an improved system design. Execution is **strictly
step-by-step: Phase 0 → 1 → 2 → 3 → 4**. Every phase ends with the full
quality gate green before moving on:

```sh
uv run ruff check . && uv run ruff format --check . && uv run pyright .
QT_QPA_PLATFORM=offscreen dbus-run-session -- uv run pytest -n auto --dist loadscope -q
```

Status legend: `[ ]` todo · `[x]` done · `[~]` in progress

---

## Phase 0 — Fix all audit findings (no user-visible change)

### 0.1 Single-source versioning (P0 — versions already diverged)
- [ ] Delete stale root `PKGBUILD` + `.SRCINFO` (still 4.2.0; `aur/` is canonical)
- [ ] Create `scripts/release.sh`: bumps `version.py` + `pyproject.toml` +
      `aur/PKGBUILD`, regenerates `aur/.SRCINFO` (`makepkg --printsrcinfo`),
      commits, tags `vX.Y.Z`, pushes
- [ ] CI check job that fails when the 4 version sources diverge
- [ ] Test release.sh logic locally (dry-run mode)

### 0.2 Real checksums / supply chain (P0)
- [ ] Release CI: compute sha256 of the tag tarball, output it for the AUR
- [ ] Commit checksum into `aur/PKGBUILD` (replace `sha256sums=('SKIP')`)
- [ ] `build-appimage.sh`: pin `appimagetool` to a fixed release URL +
      verify its sha256 before use (stop using "continuous" blind download)

### 0.3 Consolidate dev dependencies (P1)
- [ ] Keep only `[dependency-groups]` in `pyproject.toml`
- [ ] Delete `[project.optional-dependencies].dev`; CI switches to
      `uv sync` (dependency-groups are default)
- [ ] Resolve version drift (pytest 8 vs 9, ruff 0.11 vs 0.16)
- [ ] Add `vulture` as a real dev dep (config exists, tool was ad-hoc)

### 0.4 CI improvements (P1)
- [ ] `astral-sh/setup-uv` with `enable-cache: true` in all jobs
- [ ] Test job: `uv run pytest -n auto --dist loadscope -q` (parity with local)
- [ ] Release job: reuse build-job artifacts (upload/download) — no second
      `uv build`
- [ ] Release notes auto-generated from the matching `CHANGELOG.md` section
      (replace `--notes ""`)

### 0.5 Coverage (P1)
- [ ] Add `pytest-cov` to dev deps + pytest addopts
- [ ] CI uploads/reports coverage; fail below threshold (start ~70%)


### 0.6 Dependency & security automation (P1)
- [ ] `.github/dependabot.yml` (pip + github-actions ecosystems)
- [ ] `uv audit` / `pip-audit` step in CI

### 0.7 Config & repo hygiene (P2)
- [ ] Remove dead `.gitignore` entries (`.pytype/`, `.mypy_cache/`)
- [ ] Move generated `benchmarks.html` to `docs/`
- [ ] `.github/`: add issue templates + PR template

**Phase 0 exit gate:** all checks green, `git push` + CI green.

---

## Phase 1 — Compact & clean the project (restructure)

### 1.1 Package layout (kills the hidden-import bug class)
- [ ] Create `src/chamelshot/` package:
      `__init__.py` imports every submodule (replaces 16 PyInstaller
      `--hidden-import` flags AND the 17-entry `[tool.setuptools]
      py-modules` list)
- [ ] `core/` — `config`, `ipc`, `dispatcher`, `proc`, `clipboard` (Qt-light)
- [ ] `capture/` — capture + compositor backends (see 1.3)
- [ ] `ui/` — `main`, `overlay`, `preview`, `editor`, `pin`, `history`,
      `settings`, `theme`
- [ ] `tray/` — `tray.py` + watcher
- [ ] Move tests 1:1 (import paths updated), pyproject packaging config
      rewritten for the package
- [ ] AppImage script: single entry point, delete manual module lists

### 1.2 Root cleanup
- [ ] `docs/adr/`: ADRs for tray rewrite, IPC design, package restructure
- [ ] Deduplicate `xdg-open` history-folder helper (4 copies:
      `main.py`, `settings.py`, `history.py`, `pin.py`)

### 1.3 Compositor abstraction layer (system design)
- [ ] `Compositor` protocol: `outputs()`, `window_tree()`,
      `screenshot_window()`, `activate()` + auto-detection
- [ ] Implementations: `Niri`, `Sway`, `Hyprland`, `Wlroots` (generic)
- [ ] Replace the `if niri / elif sway / elif hyprland` sprinkles in
      `capture.py` / `overlay.py`
- [ ] Unlock monitor mode on non-niri compositors (v5 known limitation)

**Phase 1 exit gate:** all tests pass with new import paths; bench.py
still runs; AppImage builds.

---

## Phase 2 — Performance ("boost")

### 2.1 Capture hot path (biggest win)
- [ ] `grim -` → pipe raw PNG bytes → `QPixmap.loadFromData` (remove
      temp-file + polling-retry loop, `capture.py:123`)
- [ ] Persistent worker thread reuse; no per-capture thread spawn

### 2.2 Startup
- [ ] Defer `capture` import until after the IPC handshake so
      `chamelshot -c` forwards before importing Qt widgets
- [ ] Measure with `scripts/bench.py` before/after
      (baseline hot ≈ 0.5 s, cold ≈ 1.2 s → target hot ≈ 0.35 s)

### 2.3 Memory & bundle
- [ ] AppImage: replace `--collect-all gi` with only the used typelibs
      (GIRepository, GLib, Gio)
- [ ] `history.py`: LRU thumbnail cache (stop re-decoding full PNGs)

### 2.4 CI speed (after Phase 0.4)
- [ ] Verify end-to-end CI time (target ≈ 1 min)

**Phase 2 exit gate:** bench.py shows hot-path + startup improvements
(numbers recorded in CHANGELOG).

---

## Phase 3 — "More butter" UX

- [ ] Animated overlay: dim fade-in (~120 ms), crosshair magnifier with
      pixel readout, selection rect with dim-outside
- [ ] Pins: scroll zoom, opacity slider, snap-to-edges
- [ ] Capture feedback: optional shutter sound + screen micro-flash (~80 ms)
- [ ] Notifications with actions (Save / Copy / Edit) via `notify-send -A`
- [ ] Launcher: fuzzy search across modes + inline history,
      `/`-prefixed commands (`/delay 3`)
- [ ] Editor: keyboard-only annotation flow, arrow-key nudge
      (Shift = coarse step), shape smoothing

**Phase 3 exit gate:** one feature per commit; full gate green; manual
smoke test on niri.

---

## Phase 4 — v6 release

- [ ] Decide + apply Python floor (see Open decisions)
- [ ] Bump to 6.0.0 via `scripts/release.sh` (breaking: package layout)
- [ ] CHANGELOG v6.0.0 entry (incl. bench numbers)
- [ ] Tag → CI → PyPI + GitHub release assets + AppImage
- [ ] AUR update with real sha256 (`aur/PKGBUILD` + `.SRCINFO`)
- [ ] Update README (install paths, new CLI flags, screenshots)

---

## Open decisions (need owner input)

1. **Python floor** — keep `>=3.14` (bleeding edge, blocks most pip users)
   or relax to `>=3.12`? Recommendation: test on 3.12, relax if green.
2. **Phase 3 scope** — all features, or pick a subset first?
