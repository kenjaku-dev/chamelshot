# ChamelShot

[![CI](https://github.com/kenjaku-dev/chamelshot/actions/workflows/ci.yml/badge.svg)](https://github.com/kenjaku-dev/chamelshot/actions/workflows/ci.yml)
[![AUR](https://img.shields.io/badge/AUR-chamelshot-blue)](https://aur.archlinux.org/packages/chamelshot)
[![PyPI](https://img.shields.io/pypi/v/chamelshot)](https://pypi.org/project/chamelshot/)
[![License](https://img.shields.io/badge/license-GPLv3-blue)](LICENSE)

A lightweight screenshot capture tool for Wayland (wlroots) with a polished Qt interface.

Combines `grim` + `slurp` under the hood, abstracting the CLI into a native system tray daemon with preview, annotation, and capture delay.

---

## Features

### Capture Modes
- **Region** — drag to select an area; click to snap to window/monitor boundaries
- **Window** — pick from visible windows via `swaymsg`/`hyprctl`, then snap-select with `slurp -r`
- **Fullscreen** — capture the entire output with one click
- **Delay** — configurable countdown overlay (1-30s) for menus, tooltips, or hover states

### Annotation Tools (9 tools)
| Tool | Description |
|------|-------------|
| Pen | Freehand drawing |
| Highlighter | Semi-transparent marker (5× width, alpha 80) |
| Arrow | Directional pointer with filled head |
| Rectangle | Outlined box |
| Oval | Outlined ellipse |
| Line | Straight line |
| Text | Click-to-type label (custom font size) |
| Numbering | Auto-incrementing numbered circles (1, 2, 3…) |
| Blur | Pixelation box with adjustable radius |

**Shortcuts:** `Ctrl+Z` undo, `Ctrl+Y` redo, `Escape` cancel current annotation

### Preview Window
- View, annotate, save, or copy to clipboard
- Re-capture without leaving the preview
- Keyboard shortcuts for save/copy/close (configurable in settings)
- Auto-save and auto-copy on capture (configurable)

### System Tray
- Persistent StatusNotifierItem (stays after capture, no daemon flag needed)
- Right-click menu: Capture Region / Capture Window / Capture Fullscreen / History / Settings / Quit
- Left-click: quick capture (uses default mode)
- Middle-click: open settings

### Screenshot History
- Automatic save to `~/.cache/chamelshot/history/` on every capture
- Last 20 screenshots retained (oldest auto-pruned)
- Browse directly from tray menu (opens with `xdg-open`)

### Capture Delay
- Configure in settings (0-30 seconds)
- Visual fullscreen countdown overlay (semi-transparent black, large white numerals)
- Press `Escape` to cancel countdown

### Window Capture
- Reads visible window geometry from `swaymsg -t get_tree` (Sway) or `hyprctl clients -j` (Hyprland)
- Passes bounding boxes to `slurp -r` for snap selection
- Works automatically — no manual window list or menu needed

---

## Installation

### Arch Linux (AUR)

```sh
yay -S chamelshot
```

### pip (any distro)

```sh
pip install git+https://github.com/kenjaku-dev/chamelshot.git
```

### From source

```sh
git clone https://github.com/kenjaku-dev/chamelshot.git
cd chamelshot
uv sync
uv run python main.py
```

### AppImage (portable)

Download from [GitHub Releases](https://github.com/kenjaku-dev/chamelshot/releases):

```sh
chmod +x chamelshot-v0.3.0-x86_64.AppImage
./chamelshot-v0.3.0-x86_64.AppImage
```

No dependencies required beyond `grim` and `slurp` at runtime.

---

## Usage

```sh
chamelshot                          # show launcher, stays in tray after capture
chamelshot -c                       # skip launcher, capture directly
chamelshot --capture                # same as -c
chamelshot --settings               # open settings dialog directly
chamelshot --install-autostart       # add to XDG autostart
chamelshot --remove-autostart        # remove from XDG autostart
```

### Keybindings (Wayland compositor)

**Sway:**
```
bindsym Print exec chamelshot
bindsym Shift+Print exec "chamelshot --capture"
bindsym Ctrl+Print exec "chamelshot --settings"
```

**Hyprland:**
```
bind = , Print, exec, chamelshot
bind = SHIFT, Print, exec, chamelshot -c
bind = CTRL, Print, exec, chamelshot --settings
```

---

## Configuration

Settings are stored in `~/.config/chamelshot/config.toml` (auto-created with defaults on first run). Edit directly or use the Settings UI from the preview window or tray menu.

### Full defaults

```toml
[general]
auto_copy = true
auto_save = false
notification = true

[save]
directory = "~/Pictures/Screenshots"
filename_format = "chamelshot_%Y%m%d_%H%M%S.png"
format = "PNG"
quality = -1

[capture]
mode = "region"       # region | window | fullscreen
delay = 0             # seconds (0-30)
include_cursor = true

[preview]
stay_on_top = true
window_width = 600
window_height = 450
max_width = 800

[clipboard]
tool = "wl-copy"      # wl-copy | qt | both

[shortcuts]
save = ""
copy = ""
close = ""
new_capture = ""
```

---

## Dependencies

| Type | Package |
|------|---------|
| Runtime (CLI) | `grim`, `slurp` |
| Runtime (Python) | `python`, `pyside6`, `dbus-python`, `pygobject` |
| Optional | `wl-clipboard` (Wayland clipboard), `swaymsg` or `hyprctl` (window capture) |
| Build | `python-build`, `python-installer`, `python-wheel`, `pyinstaller` (AppImage) |

---

## Migration from SnapCap

v0.3.0 is a rename from the original `snapcap-wayland` project. If you have an existing `~/.config/snapcap/` directory, ChamelShot will auto-create a fresh config at `~/.config/chamelshot/`. The AUR package `chamelshot` conflicts with `snapcap-wayland`.

---

## License

GNU General Public License v3.0 or later. See [LICENSE](LICENSE).
