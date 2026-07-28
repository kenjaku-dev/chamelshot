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

```bash
yay -S snapcap-wayland
```

### From source

```bash
git clone https://github.com/kenjaku-dev/snapcap-wayland.git
cd snapcap-wayland
uv sync
uv run python main.py
```

### Build binary

```bash
uv pip install pyinstaller
uv run pyinstaller --onedir --windowed --name snapcap --paths . --clean main.py
./dist/snapcap/snapcap
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
