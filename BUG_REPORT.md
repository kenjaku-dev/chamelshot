# ChamelShot Bug Report & Fix Log

## P0 — Crashes & Broken Functionality

### 29. Tray context menu fully broken on Wayland (niri + waybar)
**Files:** `tray.py`, `main.py`
**Root cause:** Two independent failures stacked:
1. **DBus serving was dead.** The tray ran its DBus objects on a GLib main loop in a worker thread. Once a `QCoreApplication` exists (always, in the real app), dbus-glib sources on the default main context are never dispatched from a worker thread (verified empirically — the worker loop still iterates plain GLib sources, but the dbus source never fires). Result: every SNI call from the host (waybar) got `NoReply` — `Activate`/`ContextMenu`/`GetAll` never reached the app. The "menu" never even triggered.
2. **Even when dispatched, the menu couldn't render.** Qt ≥ 6.9 rejects `Qt::Popup` windows whose transient parent never received input ("Failed to create grabbing popup", QTBUG-139921) — waybar's click goes to the bar, not to our 1×1 anchor window, so niri rejects the xdg_popup.

**Fix (best practice, per the SNI spec):**
1. **DBusMenu export** (`com.canonical.dbusmenu` at `/MenuBar`): the SNI now advertises `Menu` + `ItemIsMenu=True`, so waybar/Plasma render the menu natively as a GTK menu attached to the bar (`dbusmenu_gtkmenu_new`) — no popup from our process at all. Full protocol: `GetLayout`, `GetGroupProperties`, `GetProperty`, `Event`, `EventGroup`, `AboutToShow` (+ `LayoutUpdated` signal for live recents refresh).
2. **No more worker thread**: tray objects are created on the main thread and served by the Qt event loop (`dbus.mainloop.glib` + `app.exec()`). Callbacks run on the main thread directly.
3. **Robust `ContextMenu(x, y)` fallback** for hosts without dbusmenu (swaybar, etc.): persistent QMenu created once; on Wayland the `Qt::Popup` flag is dropped (CopyQ workaround — frameless always-on-top toplevel, `triggered` → close, explicit `activateWindow()`/`setActiveWindow()`/`setFocus()` after popup). Host-provided coordinates are used (never `QCursor.pos()`).
4. Removed the dead 1×1 anchor window and `_TrayPopup` fallback.
5. `AboutToShow` fingerprinting: recents changes trigger `LayoutUpdated` so hosts re-fetch the layout.

**Tests:** `test_tray.py` (6 tests, run via `dbus-run-session -- pytest test_tray.py`) — server subprocess mirrors production (main-thread GLib loop), clients are subprocesses like a real SNI host. Covers layout, item props, event dispatch, AboutToShow refresh, properties.

### 30. Tray icon shows but menu items never render (waybar)
**Files:** `tray.py`
**Root cause:** The `GetLayout` reply violated the dbusmenu wire format. libdbusmenu-glib (which waybar links via `libdbusmenu-gtk3`) builds its expected signature from its own introspection and refuses anything else: it requires exactly `<arg type="u" name="revision"/>` + `<arg type="(ia{sv}av)" name="layout"/>` — a struct `(id, a{sv}, av)` whose `av` children are variant-wrapped `(ia{sv}av)` structs. The old reply carried children as plain ints inside the root props dict, so libdbusmenu parsed zero items → empty menu. Verified with a compiled C client against the installed `libdbusmenu-glib.so.4` (identical failure to waybar).
**Fix:** Rewrote `tray.py` on PyGObject/Gio. dbus-python 1.4.0 cannot marshal this reply at all — every variant-wrapped / nested-container reply (e.g. `dbus.Struct(..., variant_level=1)`, `Array([...], signature="v")`) raises `TypeError: Expected a string or unicode object` when the reply is appended. GVariant builds the wire bytes exactly: `GLib.Variant("(u(ia{sv}av))", (revision, (parent_id, props_dict, children_list)))` with children as native `(ia{sv}av)` tuples. Two gi quirks discovered on the way: prebuilt `a{sv}` variants get unboxed when iterated inside another constructor (assemble native dicts of `GLib.Variant` values instead), and `emit_signal(bus_name, object_path, interface, signal, params)` — swapping path/interface made `AboutToShow` return `Failed: emit_signal() takes exactly 6 arguments`. Also fixed `Version` property type to `u` (libdbusmenu rejects `i`). `GetGroupProperties`/`AboutToShowGroup` originally returned bare `a(ia{sv})`/`a(ib)` replies instead of `(a(ia{sv}))`/`(a(ib))` tuples — `g_variant_is_of_type` assertion in Gio, menu calls failed when waybar opened the menu. DBus serving still rides the GLib default main context driven by Qt's `QEventDispatcherGlib` — main thread only, no worker thread.

### 31. Tray icon vanishes after waybar restarts
**Files:** `tray.py`, `test_tray_watcher.py`
**Root cause:** SNI hosts (waybar included, per its source in `src/modules/sni/`) learn about items **only** through `org.kde.StatusNotifierWatcher`: the host dumps `RegisteredStatusNotifierItems` when it registers and reacts to `StatusNotifierItemRegistered` signals — there is no bus-name scanning of `org.kde.StatusNotifierItem-*`. The tray called `RegisterStatusNotifierItem` exactly once at startup inside `try/except: pass`. Any miss (waybar not ready yet, or — the real killer — a **waybar restart**) left the item unregistered forever: the new watcher process starts with an empty item list and nothing ever re-registers. Observed live: waybar restarted twice in one session, killing the icon each time; a manual `RegisterStatusNotifierItem` via gdbus instantly made the item appear in the watcher list.
**Fix:** Watch the watcher name (`Gio.bus_watch_name` on `org.kde.StatusNotifierWatcher`) and register on every appearance; register from the `on_name_acquired` callback (name definitely owned); re-register after every watcher restart; bounded 300 ms retry while the watcher owns its name but hasn't exported its object yet (waybar's `busAcquired` does exactly that). Failures are retried, not swallowed.
**Tests:** `test_tray_watcher.py` — fake watcher lifecycle (appear → tray registers with its SNI bus name; kill → restart → tray re-registers).

## P0 — Crashes & Broken Functionality

### 1. Tray icon crash on startup
**File:** `tray.py:27`
**Root cause:** `QImage.constBits()` in PySide6 6.11.1 returns `memoryview`, not a pointer. The old code called `.asarray()` which doesn't exist on `memoryview`.
**Fix:** `bytes(img.constBits())` instead of `img.constBits().asarray()`

### 2. AppImage crash — "libshiboken/signature: could not initialize part 2"
**File:** `main.py:14` (importing PySide6.QtCore)
**Root cause:** After renaming `snapcap/` to `chamelshot/`, the `.venv/bin/pyinstaller` shebang still pointed to `/home/achraf/.../snapcap/.venv/bin/python3` which no longer existed. PyInstaller fell back to the `uv tool` version under Python 3.13, but PySide6 was installed in the project's Python 3.14 venv — so PySide6 was never bundled.
**Fix:** `uv sync --reinstall-package pyinstaller` regenerated the shebang to the correct path.

### 3. Venv activation scripts stale paths
**Files:** `.venv/bin/activate`, `.venv/bin/activate.csh`, `.venv/bin/activate.fish`, `.venv/bin/activate.nu`
**Root cause:** All activation scripts hardcode `VIRTUAL_ENV='/home/achraf/.../snapcap/.venv'`. After renaming the folder, activation is broken.
**Fix:** Regenerate venv or symlink the old path.

---

## P1 — Features Not Working

### 4. Tray context menu doesn't appear
**File:** `tray.py:56-59`
**Root cause 1:** `QTimer.singleShot(0, callback)` was called from the GLib background thread. The GLib main loop doesn't process Qt timer events, so the callback never fired. The tray ran DBus in a background thread via `GLib.MainLoop()`, and DBus method calls (Activate, ContextMenu, SecondaryActivate) ran in that thread. `QTimer.singleShot` created a QTimer in the GLib thread — which never fires.
**Root cause 2:** `QMenu.popup(QPoint(x, y))` with x=0,y=0 (Wayland gives no global coordinates) caused invisible menu positioning.
**Fix:** Replaced `QTimer.singleShot` with `QCoreApplication.postEvent()` + a custom `_EventReceiver` — Qt's thread-safe cross-thread event posting. Also added `QCursor.pos()` fallback for menu positioning on Wayland.

### 5. Tray icon displayed incorrectly ("diplicted")
**File:** `tray.py:25`
**Root cause:** `_icon_data()` used `QImage.Format.Format_RGBA8888` but the StatusNotifierItem protocol spec requires `QImage.Format.Format_ARGB32_Premultiplied` (0xAARRGGBB). Wrong byte order caused visual corruption.
**Fix:** Changed to `Format_ARGB32_Premultiplied`. Also cap icon size to 64x64 for consistent rendering across tray implementations.

### 6. Left-click on tray starts capture instead of showing menu
**File:** `main.py:84`
**Root cause:** `on_activate` (left-click) was set to `start_capture`. User expects a context menu.
**Fix:** Changed to `_show_tray_menu` so left-click shows the same menu as right-click.

---

## P2 — UX & Missing Features

### 7. Preview button duplication (floating overlay + bottom bar)
**File:** `preview.py`
**Issue:** Floating overlay had Quick Save, Copy, Export, Open. Bottom bar had Save, Copy, New Capture, Annotate, Settings, Close, Quit. Copy appeared twice. Save vs Quick Save/Export was confusing.
**Fix:** Removed Save and Copy from bottom bar. Bottom bar now only: New Capture, Annotate, Settings, Close, Kill. Overlay handles all save/export actions.

### 8. No Export dialog (format, quality options)
**File:** `preview.py`
**Issue:** Only Save (file dialog, in config format) and Copy to clipboard existed. No way to choose format/quality on-the-fly.
**Fix:** Added `ExportDialog` with Format combo (PNG/JPEG/WebP/BMP), Quality slider (for lossy formats), and path picker. Buttons: Save, Copy, Cancel.

### 9. No Quick Save (save to default dir)
**Issue:** User had to go through file dialog or enable auto-save in config.
**Fix:** Added "Quick Save" button — saves to config's `save.directory` with configured format silently, then closes.

### 10. No "Open in viewer" action
**Issue:** No way to open screenshot in external image viewer from preview.
**Fix:** Added "Open" button — saves a temp PNG to history dir, opens with xdg-open/gimp/eog/feh/sxiv.

### 11. Inconsistent button naming ("Quit" vs "Kill")
**Files:** `preview.py`, `main.py`
**Issue:** User wanted "Kill" instead of "Quit".
**Fix:** Renamed "Quit" to "Kill" in both preview bottom bar and tray context menu.

### 12. Bottom bar buttons unstyled (default Qt look)
**File:** `preview.py`
**Issue:** Floating overlay had dark styled buttons, bottom bar had default OS-styled buttons — inconsistent.
**Fix:** Styled bottom bar with matching dark theme (dark background, border, hover effects).

---

## P3 — Minor Issues

### 13. `_open_settings` incompatible with event dispatch
**File:** `main.py:114`
**Issue:** After switching to `postEvent` dispatching, `SecondaryActivate` calls the settings callback with `(x, y)` args, but `_open_settings()` accepted no arguments.
**Fix:** Changed to `def _open_settings(self, *_args):`

### 14. Preview `_show_preview` referenced wrong widget
**File:** `preview.py:390`
**Issue:** After adding `preview_container` wrapper, `_show_preview` still set `preview_label` as the current widget instead of `preview_container`.
**Fix:** Changed to `self.preview_container`.

---

## v4.0.0 — New fixes (2026)

| # | Severity | Fix |
|---|----------|-----|
| 15 | P0 | **Config crash on braces** — `_write_commented` used `.format()` which crashed if any value contained `{}`. Replaced with safe regex templating (`config.py`) |
| 16 | P1 | **Broken history timestamps** — tray menu showed `20260801:143000_123456`. Now parsed with strptime and shown as `14:30:00` / `Yesterday 09:12` / `Jul 30 09:12` (`main.py:_format_history_time`) |
| 17 | P1 | **No single instance** — pressing Print twice spawned 2 daemons. Added Unix-socket IPC (`ipc.py`): first instance is daemon, later invocations forward commands and exit |
| 18 | P1 | **UI freeze during capture** — grim/slurp ran synchronously on the main thread (up to 30s freeze). Now run in worker threads, results posted back via shared dispatcher (`dispatcher.py`, `capture.py:capture_async`, `overlay.py`) |
| 19 | P1 | **`_from_launcher` sticky flag** — never reset, causing wrong cancel behavior after first launcher capture. Removed entirely; cancel always shows launcher |
| 20 | P1 | **Cross-thread dispatch duplicated** — tray and async capture each had their own event classes. Unified in `dispatcher.py` (thread-safe `postEvent` pattern) |
| 21 | P2 | **Hardcoded Arch in dep check** — `check_deps` now lists Arch/Debian/Fedora commands |
| 22 | P2 | **Preview stay-on-top broken** — `setWindowFlags(WindowStaysOnTopHint)` without `Window` type. Fixed to `Window \| WindowStaysOnTopHint` |
| 23 | P2 | **Unchecked pixmap.save()** — silent save failures. All saves now check return value and surface errors |
| 24 | P2 | **ExportDialog wrong default path** — used `~/chamelshot.png`; now defaults to configured save dir |
| 25 | P2 | **`_auto_save` duplicated `_quick_save`** — consolidated into one code path |
| 26 | P2 | **Dead code** — removed unused `_EventReceiver`/`_CallEvent` (tray), `update_icon`, `_menu_items` |
| 27 | P2 | **Version scattered** — centralized in `version.py` (4.0.0) |
| 28 | P2 | **No CLI diagnostics** — added `--version`, `--test-tray` (pops tray menu 1.5s after start to verify SNI dispatch), `--open-history` |

## Summary (v3.0)

| Severity | Fixed | Description |
|----------|-------|-------------|
| P0 | ✓ | Tray icon crash on startup (memoryview) |
| P0 | ✓ | AppImage crash (stale venv shebang after rename) |
| P0 | ✓ | Venv activation scripts stale paths |
| P1 | ✓ | Context menu never appears (QTimer in wrong thread) |
| P1 | ✓ | Icon displayed wrong pixel format (ARGB32) |
| P1 | ✓ | Left-click doesn't show menu |
| P2 | ✓ | Preview button duplication |
| P2 | ✓ | Missing Export dialog |
| P2 | ✓ | Missing Quick Save |
| P2 | ✓ | Missing Open in viewer |
| P2 | ✓ | Inconsistent button naming |
| P2 | ✓ | Bottom bar unstyled |
| P3 | ✓ | _open_settings arg mismatch |
| P3 | ✓ | _show_preview wrong widget ref |
