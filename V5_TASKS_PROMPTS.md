# ChamelShot v5 — Task Prompts + Best Skills

Copy-paste these prompts into opencode. Each task lists the best skill(s) to
invoke first (`/skill`), then the prompt. Order follows priority.

Conventions (from AGENTS.md): all commands via `uv run`; tests under
`dbus-run-session`; line-length 120; no code comments unless "why".

---

## A. Quick bug fixes (small, self-contained)

### A1. Fix Save dialog default path
- **Skill:** `/systematic-debugging`
- **Prompt:**
```
In preview.py:370 the plain "Save" dialog still hardcodes
os.path.expanduser("~/chamelshot.png") while ExportDialog (BUG#24) uses the
configured save.directory. Make the Save dialog default to
cfg's save.directory + the filename_format (or chamelshot.png fallback), and
prefill the filename. Keep the DontUseNativeDialog option. Add/extend a test
in test_*.py if a seam exists; run ruff check and pyright after.
```

### A2. Don't silently swallow corrupt config
- **Skill:** `/systematic-debugging`
- **Prompt:**
```
config.py load() (lines 136-137) returns raw DEFAULTS on ANY exception, so a
malformed config.toml (e.g. a quote in save.directory) silently wipes the
user's settings. Change it to: try to load; on tomllib.TOMLDecodeError print a
one-time warning (stderr) explaining the file was ignored, then fall back to
defaults WITHOUT overwriting the file. Keep save() behavior unchanged. Update
test_config.py to cover corrupt file handling. Run ruff check and pyright.
```

### A3. Cancel shouldn't always pop the launcher
- **Skill:** `/systematic-debugging`
- **Prompt:**
```
In main.py, _on_cancel (line 357) always shows the launcher window. But when
capture was started via the --capture keybind (auto_capture), cancelling the
region selector pops a launcher the user never asked for. Track how capture
was started (keybind vs launcher button) and only show the launcher on cancel
when it was already visible / started from the launcher. Update
test_main_menu.py accordingly. Run the full dbus-run-session test suite.
```

### A4. Stop polluting the history cache with temp files
- **Skill:** `/simplify-code`
- **Prompt:**
```
In preview.py _open_viewer (line 457) writes the temp file into
cfg.HISTORY_DIR (_preview_tmp.png) where it's never pruned and lives next to
real screenshots. Move the temp file to a temp location (e.g.
tempfile.gettempdir() or CACHE_DIR/_tmp/) and keep it there, or clean it up
after the viewer opens. Verify history pruning and tray recents still work.
```

### A5. Make local typecheck match CI
- **Skill:** `/plan`
- **Prompt:**
```
`uv run pyright .` locally reports ~1246 errors because it scans build/ and
dist/ (PyInstaller bundles), but CI typechecks a fresh checkout so it passes.
Add include/exclude config to [tool.pyright] in pyproject.toml so local runs
exclude build/, dist/, .venv/ and report only source. Verify local output now
matches CI behavior. Do NOT touch the gi import ignore comments convention.
```

### A6. Sync stale docs (tests count, feature lists)
- **Skill:** `/ubiquitous-language`
- **Prompt:**
```
AGENTS.md says "40 tests" but the suite is now 46. README lists "9 annotation
tools" — verify the real count and behavior in editor.py and correct the
README table. Also check README claims about capture modes, shortcuts, and
config defaults against config.py DEFAULTS. Fix discrepancies only; no
feature changes. No new files.
```

---

## B. UX / polish improvements

### B1. Per-monitor (multi-output) capture
- **Skill:** `/shape` → `/implement`
- **Prompt:**
```
Add a "Capture Monitor" mode alongside region/window/fullscreen. capture.py
currently runs bare `grim` for fullscreen which composites ALL outputs.
Design: list monitors (grim -o requires output name; detect via grim -l or
wlr-randr), show a simple picker, capture with grim -o <output>. Wire it into
the tray menu, launcher window, IPC command (capture-monitor), and config
capture.mode. Keep the existing thread/async pattern. Add tests for the
monitor list parsing if it's a pure function. Full dbus-run-session suite.
```

### B2. Tray recents: re-edit instead of just xdg-open
- **Skill:** `/shape` → `/implement`
- **Prompt:**
```
In main.py, tray "Recent" entries call _open_history_file (xdg-open). Add a
"Re-edit" option per recent entry that loads the PNG back into PreviewWindow
(and Annotator) instead of opening an external viewer. Keep xdg-open as an
alternative action. Consider a submenu or a second row of actions in the
dbusmenu layout (test_tray.py covers the wire format — keep it valid).
```

### B3. History browser with thumbnails
- **Skill:** `/shape` → `/implement`
- **Prompt:**
```
Build a "History" dialog (new file history.py, wired like settings.py): grid
of thumbnail previews of the last N screenshots from cfg.HISTORY_DIR with
delete, re-edit, open-folder, and copy actions. Register an IPC command
(open-history-ui) and a tray item. Follow existing dark stylesheet patterns.
Run tests + ruff + pyright.
```

### B4. Save-path / filename validation
- **Skill:** `/shape` → `/implement`
- **Prompt:**
```
settings.py filename format is free-text with no validation (e.g. user sets
%H.jpg while save.format=PNG silently mismatches). Add validation on the Save
tab: warn if the resolved extension doesn't match the chosen image format,
and suggest a fix. Also validate that the directory is writable. Keep it
non-blocking (warn, don't block). Add unit tests in test_config.py.
```

---

## C. New v5 features

### C1. Pin screenshot on screen
- **Skill:** `/grill-with-docs` (scope first) → `/to-spec` → `/to-tickets` → `/implement`
- **Prompt:**
```
Design and build "Pin screenshot": after capture, a button (and shortcut) in
the preview pins the image as a frameless always-on-top window that stays on
screen (like Flameshot's pin). Pinned windows: draggable, scrollable if
larger than screen, close with Escape, can be copied/saved/annotated from a
small action bar. One pin at a time or multiple? — decide during the grill.
Wire into PreviewWindow and IPC. Tests for the state model only (GUI is
hard to test on CI) — keep the pin lifecycle logic in a testable class.
```

### C2. Copy to clipboard + primary selection
- **Skill:** `/implement` (small) — start with `/tdd`
- **Prompt:**
```
preview.py copy_to_clipboard only sets the regular clipboard. Add a "Copy
(primary)" action that also feeds wl-copy primary selection (--primary) when
clipboard.tool includes wl-copy. Add a shortcut (configurable) and a tray/
preview button. Follow the existing async encode/copy pattern (run_async).
```

### C3. CLI: output + geometry capture options
- **Skill:** `/implement`
- **Prompt:**
```
Extend CLI/IPC: chamelshot --output <name>, --region WxH+X+Y, --window
<app_id> (best-effort), each forwarding to the daemon like existing commands
(main.py cmd mapping, ipc.py). Reuse B1 monitor detection for --output
validation. Update README usage + --help text (main.py _HELP). Keep the
50ms fast-path (no GUI import for --help/--version).
```

### C4. Notification with thumbnail
- **Skill:** `/implement` (small)
- **Prompt:**
```
preview.py _notify uses plain notify-send text. Add optional image hint:
notify-send -i <path> or the image-path hint when a saved file exists
(history/notify_<ts>.png), controlled by existing general.notification
setting + a new general.notification_preview bool (default true). Keep the
subprocess fire-and-forget pattern.
```

### C5. Annotator: eraser + crop
- **Skill:** `/shape` → `/implement`
- **Prompt:**
```
editor.py Annotator has 9 tools. Add: (1) an Eraser tool (reverts painted
pixels to the source image, not background), and (2) Crop (drag a rect on the
canvas, Enter commits, Escape cancels — reuses undo/redo stack). Update
README tool table and the tool switcher UI. Keep pixel-ops in the same
layered approach; tests for pure math only.
```

---

## D. Housekeeping

### D1. Review the whole v5 branch before merging
- **Skill:** `/code-review`
- **Prompt:**
```
Run the two-axis review (Standards + Spec) over the v5 work since the v4.2.0
tag: ruff/pyright/test hygiene, wire-format safety for tray.py dbusmenu
changes, config migration safety, and that each feature matches its ticket.
Report side by side; fix P0/P1 findings.
```

### D2. Pre-commit hook setup
- **Skill:** `/setup-pre-commit`
- **Prompt:**
```
Add pre-commit hooks matching CI: ruff check, ruff format, pyright, and
pytest (dbus-run-session + QT_QPA_PLATFORM=offscreen). Skip the
config/spec files (*.spec is gitignored). Keep it fast: format/check/lint on
staged python files, full typecheck+tests on commit.
```

### D3. Architecture survey before starting v5
- **Skill:** `/improve-codebase-architecture`
- **Prompt:**
```
Survey chamelshot for deepening opportunities: spot seams (config writes,
capture modes, clipboard backends, tray menu building) that would make the
v5 feature set easier. Produce the visual report; I'll pick one to work on
first.
```

---

## Suggested execution order

1. A1–A6 (bug fixes — each 1 commit, run full suite after each)
2. D3 architecture survey → pick features in order of cost/benefit:
   - C2 (primary clipboard) — cheapest win
   - C4 (thumbnail notifications)
   - C1 (pin) — flagship, use grill-with-docs first
   - B1 + C3 (monitor capture + CLI) — shared foundation
   - B2/B3 (history UX)
   - C5 (eraser/crop)
3. D1 review branch → D2 pre-commit → release flow (tag v5.0.0)
