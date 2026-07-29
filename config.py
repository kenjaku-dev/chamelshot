# SnapCap - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import datetime
import os
import tomllib
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "snapcap"
CONFIG_PATH = CONFIG_DIR / "config.toml"

COMMENTED = """# SnapCap Configuration
# Edit this file to customize everything.
# After saving, changes take effect on next capture.
# Restart the daemon if running in --daemon mode.

[general]
# Automatically copy screenshot to clipboard after capture
auto_copy = {general[auto_copy]}
# Automatically save screenshot to the directory below
auto_save = {general[auto_save]}
# Show desktop notification after copy/save
notification = {general[notification]}

[save]
# Directory where auto-saved screenshots go
directory = "{save[directory]}"
# Filename pattern (uses strftime: %%Y %%m %%d %%H %%M %%S)
filename_format = "{save[filename_format]}"
# Image format: PNG, JPEG, BMP, WEBP
format = "{save[format]}"
# JPEG/WebP quality 0-100 (-1 = default)
quality = {save[quality]}

[capture]
# Capture mode: "region" (select area) or "fullscreen"
mode = "{capture[mode]}"
# Delay in seconds before capture (useful for menus/tooltips)
delay = {capture[delay]}
# Include the cursor in the screenshot
include_cursor = {capture[include_cursor]}

[clipboard]
# Clipboard tool: "wl-copy", "qt", or "both"
tool = "{clipboard[tool]}"

[shortcuts]
# Keybindings in the preview window
# Use Qt key sequences: Ctrl+S, Ctrl+C, Ctrl+N, Escape, Ctrl+Shift+A, etc.
save = "{shortcuts[save]}"
copy = "{shortcuts[copy]}"
new_capture = "{shortcuts[new_capture]}"
close = "{shortcuts[close]}"

[preview]
# Maximum dimension for the thumbnail in preview (larger = slower)
max_width = {preview[max_width]}
# Initial window size in pixels
window_width = {preview[window_width]}
window_height = {preview[window_height]}
# Keep preview window on top of other windows
stay_on_top = {preview[stay_on_top]}

[ui]
# Language for UI text (currently only "en")
language = "{ui[language]}"
"""

DEFAULTS = {
    "general.auto_copy": True,
    "general.auto_save": False,
    "general.notification": True,
    "save.directory": str(Path.home() / "Pictures" / "Screenshots"),
    "save.filename_format": "snapcap_%Y%m%d_%H%M%S.png",
    "save.format": "PNG",
    "save.quality": -1,
    "capture.mode": "region",
    "capture.delay": 0,
    "capture.include_cursor": False,
    "clipboard.tool": "wl-copy",
    "shortcuts.save": "Ctrl+S",
    "shortcuts.copy": "Ctrl+C",
    "shortcuts.new_capture": "Ctrl+N",
    "shortcuts.close": "Escape",
    "preview.max_width": 800,
    "preview.window_width": 600,
    "preview.window_height": 450,
    "preview.stay_on_top": True,
    "ui.language": "en",
}


def _flatten(data: dict, prefix="") -> dict:
    result = {}
    for k, v in data.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten(v, key))
        else:
            result[key] = v
    return result


def _unflatten(data: dict) -> dict:
    result = {}
    for key, val in data.items():
        parts = key.split(".")
        d = result
        for p in parts[:-1]:
            d = d.setdefault(p, {})
        d[parts[-1]] = val
    return result


def load() -> dict:
    if not CONFIG_PATH.exists():
        _write_default()
        return dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "rb") as f:
            raw = tomllib.load(f)
        flat = _flatten(raw)
        merged = dict(DEFAULTS)
        merged.update(flat)
        return merged
    except Exception:
        return dict(DEFAULTS)


def save(data: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _write_toml(data)


def _toml_val(val):
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return str(val)
    return str(val)


def _write_default():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _write_commented(DEFAULTS)


def _write_commented(flat: dict):
    vals = _unflatten({k: _toml_val(v) for k, v in flat.items()})
    content = COMMENTED.format(**vals)
    with open(CONFIG_PATH, "w") as f:
        f.write(content)


def _write_toml(data: dict):
    flat = _flatten(data)
    merged = dict(DEFAULTS)
    merged.update(flat)
    _write_commented(merged)


AUTOSTART_PATH = Path.home() / ".config" / "autostart" / "snapcap.desktop"


def install_autostart():
    AUTOSTART_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART_PATH.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=SnapCap (Daemon)\n"
        "Comment=SnapCap system tray daemon\n"
        "Exec=snapcap -d\n"
        "Icon=snapcap\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def remove_autostart():
    AUTOSTART_PATH.unlink(missing_ok=True)


def autostart_enabled() -> bool:
    return AUTOSTART_PATH.exists()


def generate_save_path(config: dict) -> str:
    save_dir = config.get("save.directory", DEFAULTS["save.directory"])
    fmt = config.get("save.filename_format", DEFAULTS["save.filename_format"])
    os.makedirs(save_dir, exist_ok=True)
    filename = datetime.datetime.now().strftime(fmt)
    return os.path.join(save_dir, filename)
