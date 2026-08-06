# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import datetime
import os
import re
import shutil
import sys
import tomllib
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "chamelshot"
CONFIG_PATH = CONFIG_DIR / "config.toml"
CACHE_DIR = Path.home() / ".cache" / "chamelshot"
HISTORY_DIR = CACHE_DIR / "history"
IPC_SOCKET_PATH = CACHE_DIR / "daemon.sock"
MAX_HISTORY = 20

COMMENTED = """# ChamelShot Configuration
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
# Show a thumbnail preview in the notification
notification_preview = {general[notification_preview]}

[save]
# Directory where auto-saved screenshots go
directory = "{save[directory]}"
# Filename pattern (uses strftime: %%Y %%m %%d %%H %%M %%S)
filename_format = "{save[filename_format]}"
# Image format: PNG, JPEG, WebP, BMP
format = "{save[format]}"
# JPEG/WebP quality 0-100 (-1 = default)
quality = {save[quality]}

[capture]
# Capture mode: "region" (select area), "window", "fullscreen", or "monitor"
mode = "{capture[mode]}"
# Which monitor for mode "monitor": "focused" or an output name from
# `niri msg outputs` (e.g. HDMI-A-1)
monitor = "{capture[monitor]}"
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
# Pin the current screenshot on screen
pin = "{shortcuts[pin]}"
# Copy to clipboard and primary selection (middle-click paste)
copy_primary = "{shortcuts[copy_primary]}"

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
    "general.notification_preview": True,
    "save.directory": str(Path.home() / "Pictures" / "Screenshots"),
    "save.filename_format": "chamelshot_%Y%m%d_%H%M%S.png",
    "save.format": "PNG",
    "save.quality": -1,
    "capture.mode": "region",
    "capture.monitor": "focused",
    "capture.delay": 0,
    "capture.include_cursor": False,
    "clipboard.tool": "wl-copy",
    "shortcuts.save": "Ctrl+S",
    "shortcuts.copy": "Ctrl+C",
    "shortcuts.new_capture": "Ctrl+N",
    "shortcuts.close": "Escape",
    "shortcuts.pin": "Ctrl+P",
    "shortcuts.copy_primary": "Ctrl+Shift+C",
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


_warned_corrupt_config = False


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
    except tomllib.TOMLDecodeError:
        global _warned_corrupt_config
        if not _warned_corrupt_config:
            _warned_corrupt_config = True
            print(
                f"chamelshot: warning: {CONFIG_PATH} could not be parsed and was ignored; using default settings",
                file=sys.stderr,
            )
        return dict(DEFAULTS)
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


_TMPL_RE = re.compile(r"\{([a-zA-Z0-9_]+)(?:\[([a-zA-Z0-9_]+)\])?\}")


def _write_commented(flat: dict):
    vals = _unflatten({k: _toml_val(v) for k, v in flat.items()})

    def _sub(match):
        section = match.group(1)
        key = match.group(2)
        node = vals.get(section)
        if isinstance(node, dict) and key is not None and key in node:
            return str(node[key])
        if key is None and not isinstance(node, dict) and node is not None:
            return str(node)
        return match.group(0)

    content = _TMPL_RE.sub(_sub, COMMENTED)
    with open(CONFIG_PATH, "w") as f:
        f.write(content)


def _write_toml(data: dict):
    flat = _flatten(data)
    merged = dict(DEFAULTS)
    merged.update(flat)
    _write_commented(merged)


AUTOSTART_PATH = Path.home() / ".config" / "autostart" / "chamelshot.desktop"


def install_autostart():
    AUTOSTART_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART_PATH.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=ChamelShot\n"
        "Comment=ChamelShot system tray daemon\n"
        "Exec=chamelshot\n"
        "Icon=chamelshot\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def remove_autostart():
    AUTOSTART_PATH.unlink(missing_ok=True)


def autostart_enabled() -> bool:
    return AUTOSTART_PATH.exists()


DESKTOP_PATH = Path.home() / ".local" / "share" / "applications" / "chamelshot.desktop"
ICON_DEST_DIR = Path.home() / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps"
ICON_SOURCE = Path(__file__).resolve().parent / "icon.png"


def _icon_source() -> Path | None:
    """Wheel data-files put the icon under sys.prefix/share/icons (pip installs),
    while a source tree / AppImage bundle keeps it next to the modules."""
    candidates = [
        ICON_SOURCE,
        Path(sys.prefix) / "share" / "icons" / "hicolor" / "256x256" / "apps" / "chamelshot.png",
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def _desktop_content(exec_path: str) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=ChamelShot\n"
        "Comment=Screenshot capture tool for Wayland (wlroots)\n"
        f"Exec={exec_path}\n"
        "Icon=chamelshot\n"
        "Categories=Utility;Graphics;\n"
        "Terminal=false\n"
        "StartupNotify=true\n"
    )


def ensure_desktop(exec_path: str):
    """Create/patch a user app-menu entry on first run.

    pip/venv/pipx installs have no post-install hook, so the .desktop file is
    written lazily from the application itself. The Exec is pinned to the real
    binary the user actually launched (which(1)/argv[0]), unlike a static
    packaging entry that misses venv/pipx prefixes.
    """
    expected = _desktop_content(exec_path)
    icon_dest = ICON_DEST_DIR / "chamelshot.png"
    try:
        if DESKTOP_PATH.read_text() == expected and icon_dest.exists():
            return
    except OSError:
        pass
    DESKTOP_PATH.parent.mkdir(parents=True, exist_ok=True)
    DESKTOP_PATH.write_text(expected)
    icon_src = _icon_source()
    if icon_src is not None:
        ICON_DEST_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(icon_src, icon_dest)


def remove_desktop():
    DESKTOP_PATH.unlink(missing_ok=True)


def desktop_installed() -> bool:
    return DESKTOP_PATH.exists()


def generate_save_path(config: dict) -> str:
    save_dir = config.get("save.directory", DEFAULTS["save.directory"])
    fmt = config.get("save.filename_format", DEFAULTS["save.filename_format"])
    os.makedirs(save_dir, exist_ok=True)
    filename = datetime.datetime.now().strftime(fmt)
    return os.path.join(save_dir, filename)


_REFERENCE_DT = datetime.datetime(2000, 1, 1, 0, 0, 0)

# Expected filename extension per save.format value (JPEG accepts jpg/jpeg).
FORMAT_EXTENSIONS = {
    "PNG": ("png",),
    "JPEG": ("jpg", "jpeg"),
    "WebP": ("webp",),
    "BMP": ("bmp",),
}


def resolve_extension(filename_format: str) -> str | None:
    """Extension a strftime filename format resolves to, lowercased, or None."""
    name = _REFERENCE_DT.strftime(filename_format)
    ext = os.path.splitext(name)[1]
    return ext.lstrip(".").lower() or None


def validate_save_settings(config: dict) -> list[str]:
    """Non-blocking warnings about save settings; empty list = OK."""
    warnings: list[str] = []
    fmt = config.get("save.filename_format", DEFAULTS["save.filename_format"])
    img_format = config.get("save.format", DEFAULTS["save.format"])
    expected = FORMAT_EXTENSIONS.get(img_format)
    ext = resolve_extension(fmt)
    if expected and ext and ext not in expected:
        want = "/".join(expected)
        warnings.append(f'Filename format resolves to ".{ext}" but save format is {img_format} (expected ".{want}")')
    save_dir = config.get("save.directory", DEFAULTS["save.directory"])
    if not _dir_is_writable(save_dir):
        warnings.append(f"Save directory is not writable: {save_dir}")
    return warnings


def _dir_is_writable(save_dir: str) -> bool:
    """Test the directory itself, or its nearest existing ancestor: saves call
    makedirs(exist_ok=True), so a missing dir under a writable parent is fine."""
    p = Path(save_dir)
    while not p.exists():
        parent = p.parent
        if parent == p:
            break
        p = parent
    return p.is_dir() and os.access(p, os.W_OK)
