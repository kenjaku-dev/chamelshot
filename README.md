# SnapCap

A lightweight screenshot capture tool for **Wayland (wlroots)** compositors (niri, Sway, Hyprland, etc.).

Built with Python & Qt6. Uses `grim` + `slurp` for capture and region selection.

## Features

- Region selection via `slurp` crosshair
- Preview window with Save / Copy to Clipboard
- Ctrl+S to save, Ctrl+C to copy, Ctrl+N for new capture
- Native Wayland clipboard support via `wl-copy`
- One-shot mode (capture and done)

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
tar xzf snapcap-v0.1.0-linux-x86_64.tar.gz
./snapcap/snapcap
```

### AppImage

Download `snapcap-v0.1.0-x86_64.AppImage` from [GitHub Releases](https://github.com/kenjaku-dev/snapcap-wayland/releases), then:

```bash
chmod +x snapcap-v0.1.0-x86_64.AppImage
./snapcap-v0.1.0-x86_64.AppImage
```

## Usage

```bash
snapcap                    # capture region → preview
```

### Niri keybinding

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
