# ChamelShot

[![CI](https://github.com/kenjaku-dev/chamelshot/actions/workflows/ci.yml/badge.svg)](https://github.com/kenjaku-dev/chamelshot/actions/workflows/ci.yml)
[![AUR](https://img.shields.io/badge/AUR-chamelshot-blue)](https://aur.archlinux.org/packages/chamelshot)
[![License](https://img.shields.io/badge/license-GPLv3-blue)](LICENSE)

A lightweight screenshot capture tool for Wayland (wlroots) with a polished Qt interface.

Combines `grim` + `slurp` under the hood, abstracting the CLI into a native system tray daemon with preview, annotation, and capture delay.

**Wayland only** (wlroots-based compositors: niri, Sway, Hyprland, river, wayfire…). X11/XWayland is not supported.

Found a bug? [Report it](https://github.com/kenjaku-dev/chamelshot/issues).

---

## Quick Start

1. Install the capture tools (`grim`, `slurp`) — see [Prerequisites](#prerequisites)
2. Install ChamelShot — see [Installation](#installation)
3. Bind the `Print` key — see [Keybindings](#keybindings-wayland-compositor)
4. Press `Print` and capture your first region

---

## Prerequisites

| Tool | Purpose | Required |
|------|---------|----------|
| `grim` | Screen capture (Wayland) | Yes |
| `slurp` | Region/window selection | Yes |
| `wl-clipboard` | Copy to clipboard (`wl-copy`) | Optional |
| `swaymsg` or `hyprctl` | Window capture on Sway / Hyprland | Optional |

```sh
# Arch Linux
sudo pacman -S grim slurp

# Debian / Ubuntu
sudo apt install grim slurp

# Fedora
sudo dnf install grim slurp
```

## Installation

> **Python 3.14 is required** for the pip/source installs below. Your distro may
> ship an older Python — in that case use the AppImage or AUR package instead.

### Arch Linux (AUR)

```sh
yay -S chamelshot
```

### AppImage (portable, any distro)

Download the latest `chamelshot-vX.Y.Z-x86_64.AppImage` from [GitHub Releases](https://github.com/kenjaku-dev/chamelshot/releases):

```sh
chmod +x chamelshot-vX.Y.Z-x86_64.AppImage
./chamelshot-vX.Y.Z-x86_64.AppImage
```

The AppImage bundles Python, Qt, and the tray stack — no runtime dependencies beyond `grim` and `slurp`.

> AppImage won't launch (Ubuntu/Fedora with newer kernels)? You're missing
> libfuse2. Run it with `./chamelshot-*.AppImage --appimage-extract-and-run`
> or install `libfuse2` (`sudo apt install libfuse2t64`).

### pip (Python 3.14+, any distro)

```sh
uv tool install chamelshot
# or: pipx install chamelshot
# or: pip install --user chamelshot
```

### From source (Python 3.14+)

```sh
git clone https://github.com/kenjaku-dev/chamelshot.git
cd chamelshot
uv sync
uv run python main.py
```

---

## Usage

```sh
chamelshot                          # show launcher, stays in tray after capture
chamelshot -c                       # capture now (forwards to running daemon)
chamelshot --capture                # same as -c
chamelshot --capture-monitor        # capture the configured/focused monitor
chamelshot --region 1920x1080+100+100  # capture a sub-region (WxH+X+Y)
chamelshot --output DP-2            # capture a specific monitor by output name
chamelshot --window firefox         # capture a window by app_id (niri, best-effort)
chamelshot --pin                    # pin the current screenshot on screen
chamelshot --settings               # open settings dialog directly
chamelshot --test-tray              # pop the tray menu (diagnose tray issues)
chamelshot --open-history           # open the screenshot history folder
chamelshot --version                # print version
chamelshot -h, --help               # all options
chamelshot --install-autostart      # add to XDG autostart
chamelshot --remove-autostart       # remove from XDG autostart
```

### Keybindings (Wayland compositor)

**niri:**
```
binds = {
    Mod+Print { spawn "chamelshot"; }
    Mod+Shift+Print { spawn "chamelshot --capture"; }
    Mod+Ctrl+Print { spawn "chamelshot --settings"; }
}
```

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

## Features

### Capture Modes
- **Region** — drag to select an area; click to snap to window/monitor boundaries
- **Window** — pick from visible windows via `swaymsg`/`hyprctl`, then snap-select with `slurp -r`
- **Fullscreen** — capture the entire output with one click
- **Monitor** — pick a specific monitor (or the focused one) for multi-output setups
- **Delay** — configurable countdown overlay (0-60s) for menus, tooltips, or hover states

### Annotation Tools (9 tools)
| Tool | Description |
|------|-------------|
| Pen | Freehand drawing |
| Highlighter | Semi-transparent marker (5× width, alpha 80) |
| Arrow | Directional pointer with filled head |
| Rect | Outlined box |
| Oval | Outlined ellipse |
| Line | Straight line |
| Text | Click-to-type label (custom font size) |
| Numbering | Auto-incrementing numbered circles (1, 2, 3…) |
| Blur | Pixelation box with adjustable radius |

**Shortcuts:** `Ctrl+Z` undo, `Ctrl+Y` redo, `Escape` cancel current annotation

### Preview Window
- View, annotate, save, or copy to clipboard (including primary selection for middle-click paste)
- Pin a screenshot on screen as a frameless floating reference
- Re-capture without leaving the preview
- Keyboard shortcuts for save/copy/close/pin (configurable in settings)
- Auto-save and auto-copy on capture (configurable)

### System Tray
- Persistent StatusNotifierItem (stays after capture, no daemon flag needed)
- **Bar-rendered native menu**: exports the `com.canonical.dbusmenu` interface (`Menu` property), so waybar/Plasma/dbusmenu-capable bars draw the menu themselves; falls back to an app-drawn `ContextMenu` for hosts without dbusmenu (swaybar, etc.)
- Menu: Capture Region / Capture Window / Capture Fullscreen / Recent screenshots / Open History Folder / Settings / Kill (recents refresh live via `LayoutUpdated`)
- Left/right-click: menu; middle-click: settings
- **Single instance**: running `chamelshot` again forwards your command to the running daemon — keybindings never spawn duplicates

### Single Instance & IPC
- First launch becomes the daemon (Unix socket at `~/.cache/chamelshot/daemon.sock`)
- Later invocations forward the command to the daemon and exit
- Commands: `-c`/`--capture`, `--capture-monitor`, `--region`, `--output`, `--window`, `--pin`, `--settings`, `--test-tray`, `--open-history`

### Screenshot History
- Automatic save to `~/.cache/chamelshot/history/` on every capture
- Last 20 screenshots retained (oldest auto-pruned)
- Browse directly from tray menu (opens with `xdg-open`)

### Capture Delay
- Configure in settings (0-60 seconds)
- Visual fullscreen countdown overlay (semi-transparent black, large white numerals)
- Press `Escape` to cancel countdown

### Window Capture
- Reads visible window geometry from `swaymsg -t get_tree` (Sway) or `hyprctl clients -j` (Hyprland)
- Passes bounding boxes to `slurp -r` for snap selection
- On niri, uses `niri msg action screenshot-window` to capture the focused window directly
- Works automatically — no manual window list or menu needed

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
mode = "region"       # region | window | fullscreen | monitor
monitor = "focused"   # focused | <output name> (e.g. HDMI-A-1)
delay = 0             # seconds (0-60)
include_cursor = false

[clipboard]
tool = "wl-copy"      # wl-copy | qt | both

[shortcuts]
save = "Ctrl+S"
copy = "Ctrl+C"
new_capture = "Ctrl+N"
close = "Escape"
pin = "Ctrl+P"
copy_primary = "Ctrl+Shift+C"

[preview]
stay_on_top = true
window_width = 600
window_height = 450
max_width = 800

[ui]
language = "en"       # currently only "en"
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No tray icon on GNOME | GNOME has no native tray support — install the **AppIndicator extension** |
| No tray icon after waybar restart | Fixed in v4.1.0 (re-registers with the status notifier watcher) — update |
| Copy to clipboard does nothing | `wl-clipboard` not installed — `sudo pacman -S wl-clipboard` |
| Window capture doesn't list windows | Missing `swaymsg` (Sway) or `hyprctl` (Hyprland); on niri the focused window is captured directly |
| AppImage won't start | See [AppImage](#appimage-portable-any-distro) section (libfuse2) |
| Tray menu issues | Run `chamelshot --test-tray` to pop the menu and diagnose |

---

## Dependencies

| Type | Package |
|------|---------|
| Runtime (CLI) | `grim`, `slurp` |
| Runtime (Python) | Python 3.14+, `pyside6`, `pygobject` |
| Optional | `wl-clipboard` (Wayland clipboard), `swaymsg` or `hyprctl` (window capture) |
| Build | `uv`/pip build, `pyinstaller` (AppImage) |

---

## Migration from SnapCap

v4.0.0 is a rename from the original `snapcap-wayland` project. ChamelShot uses a fresh config at `~/.config/chamelshot/` — your old `~/.config/snapcap/` settings are **not** migrated automatically; copy them manually if you customized anything. The AUR package `chamelshot` conflicts with `snapcap-wayland`.

---

## License

GNU General Public License v3.0 or later. See [LICENSE](LICENSE).
