# ChamelShot

[![CI](https://github.com/kenjaku-dev/chamelshot/actions/workflows/ci.yml/badge.svg)](https://github.com/kenjaku-dev/chamelshot/actions/workflows/ci.yml)
[![AUR](https://img.shields.io/badge/AUR-chamelshot-blue)](https://aur.archlinux.org/packages/chamelshot)

A lightweight screenshot capture tool for Wayland (wlroots).

Built with PySide6, providing a native system tray and intuitive launcher UI.

Combines `grim` + `slurp` under the hood, but abstracts away the CLI with a polished Qt interface featuring screenshot preview, annotation tools (freehand, arrow, rectangle, ellipse, text, highlighter, numbering), and blur effects.

---

## Features

- **Region capture** — drag to select, click on a window, or click on a monitor
- **Multiple annotation tools** — freehand, arrow, rectangle, ellipse, text, highlighter, numbering (press `Ctrl+Z`/`Ctrl+Y` to undo/redo)
- **Blur** — pixelate sensitive areas
- **Preview window** — edit, save, copy to clipboard, or discard
- **Window capture** — click any open window to capture it
- **Countdown overlay** — visual countdown when delay is set
- **Screenshot history** — previous captures accessible from the tray menu
- **Settings UI** — auto-copy, auto-save, notification, filename format, capture delay
- **Autostart** — optional XDG autostart integration
- **System tray** — persistent StatusNotifierItem with icon (stays after capture)

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

### AppImage

Download from [GitHub Releases](https://github.com/kenjaku-dev/chamelshot/releases):

```sh
chmod +x chamelshot-v0.3.0-x86_64.AppImage
./chamelshot-v0.3.0-x86_64.AppImage
```

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
```

**Hyprland:**
```
bind = , Print, exec, chamelshot
```

## Configuration

Settings are stored in `~/.config/chamelshot/config.toml` (auto-created with defaults on first run). You can edit it directly or use the settings UI from the preview window or tray menu.

### Defaults

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
mode = "region"
delay = 0
```

## Dependencies

- **Runtime:** `grim`, `slurp`, `python`, `python-pyside6`, `wl-clipboard` (optional)
- **Build:** `python-build`, `python-installer`, `python-wheel`

## License

GNU General Public License v3.0 or later.
