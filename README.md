# SnapCap

[![CI](https://github.com/kenjaku-dev/snapcap-wayland/actions/workflows/ci.yml/badge.svg)](https://github.com/kenjaku-dev/snapcap-wayland/actions/workflows/ci.yml)
[![AUR](https://img.shields.io/badge/AUR-snapcap--wayland-blue)](https://aur.archlinux.org/packages/snapcap-wayland)

A lightweight screenshot capture tool for **Wayland (wlroots)** compositors (niri, Sway, Hyprland, etc.).

Built with Python & Qt6. Uses `grim` + `slurp` for capture and region selection.

## Features

- Region selection via `slurp` crosshair (or fullscreen mode)
- Preview window with Save / Copy to Clipboard
- **Annotation editor** with 7 tools: Pen, Arrow, Rectangle, Circle, Line, Text, Blur
- Undo/redo, color picker, stroke width, blur radius
- Customizable keybindings in preview window
- Native Wayland clipboard support via `wl-copy`
- System tray daemon with StatusNotifierItem (Waybar, etc.)
- One-shot mode (capture and done) or persistent daemon
- Configurable delay, cursor capture, auto-save, auto-copy
- Full settings UI

## Dependencies

- `grim` — screenshot capture
- `slurp` — region selection
- `wl-clipboard` — clipboard support (optional, falls back to Qt)

```bash
sudo pacman -S grim slurp wl-clipboard
```

## Install

### AUR (recommended)

[![AUR](https://img.shields.io/badge/AUR-snapcap--wayland-blue)](https://aur.archlinux.org/packages/snapcap-wayland)

```bash
yay -S snapcap-wayland
```

### pip

```bash
pip install git+https://github.com/kenjaku-dev/snapcap-wayland.git
```

### From source

```bash
git clone https://github.com/kenjaku-dev/snapcap-wayland.git
cd snapcap-wayland
uv sync
uv run python main.py
```

### Binary release (tar.gz)

Download from [GitHub Releases](https://github.com/kenjaku-dev/snapcap-wayland/releases):

```bash
tar xzf snapcap-v0.2.0-linux-x86_64.tar.gz
./snapcap/snapcap
```

### AppImage

Download `snapcap-v0.2.0-x86_64.AppImage` from [GitHub Releases](https://github.com/kenjaku-dev/snapcap-wayland/releases), then:

```bash
chmod +x snapcap-v0.2.0-x86_64.AppImage
./snapcap-v0.2.0-x86_64.AppImage
```

## Usage

```bash
snapcap                          # show launcher window
snapcap -c                       # capture region → preview, then exit
snapcap --capture                # same as -c
snapcap -d                       # start as daemon (stays in tray)
snapcap --daemon                 # same as -d
snapcap --settings               # open settings dialog directly
snapcap --install-autostart       # add to XDG autostart (starts daemon on login)
snapcap --remove-autostart        # remove from XDG autostart
```

### Modes

- **Launcher** (default) — shows a small window with Capture Region, Capture Fullscreen, and Settings buttons
- **Capture** (`-c`/`--capture`) — skips the launcher, goes straight to capture (for keybindings)
- **Daemon** (`-d`/`--daemon`) — lives in system tray via StatusNotifierItem. Click tray icon to capture, right-click for menu
- **Settings** (`--settings`) — opens the settings dialog standalone
- **Autostart** (`--install-autostart`/`--remove-autostart`) — manage daemon autostart via XDG autostart spec. Can also be toggled in the Settings UI (General tab)

### Annotations

After capturing, click **Annotate** in the preview window to open the editor. Draw over the screenshot using the toolbar tools:

| Tool | Shortcut | Description |
|------|----------|-------------|
| ✏️ Pen | Click & drag | Freehand drawing |
| ➡️ Arrow | Click & drag | Directional arrow with filled head |
| ▭ Rectangle | Click & drag | Rectangle outline |
| ○ Circle | Click & drag | Ellipse outline |
| ╱ Line | Click & drag | Straight line |
| T Text | Click position | Enter text at cursor |
| ◎ Blur | Click & drag | Pixel blur region (adjustable radius) |

Press **Escape** to cancel an in-progress drawing. Click **✓ Apply** to bake annotations into the image, or **✗ Cancel** to discard.

### Configuration

Settings are stored in `~/.config/snapcap/config.toml` (auto-created with defaults on first run). You can edit it directly or use the settings UI from the preview window or tray menu.

```toml
[general]
auto_copy = true
auto_save = false
notification = true

[capture]
mode = "region"          # "region" or "fullscreen"
delay = 0                # seconds before capture
include_cursor = false

[save]
directory = "~/Pictures/Screenshots"
format = "PNG"
quality = -1

[shortcuts]
save = "Ctrl+S"
copy = "Ctrl+C"
new_capture = "Ctrl+N"
close = "Escape"

[preview]
max_width = 800
stay_on_top = true
```

### Niri

```kdl
binds {
    Print screen { spawn "snapcap"; }
}
```

### Sway / Hyprland

```conf
# Sway
bindsym Print exec snapcap

# Hyprland
bind = , Print, exec, snapcap
```

## License

GNU General Public License v3.0
