# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import subprocess
import time

from PySide6.QtGui import QPixmap

GRIM_NOT_FOUND = "grim is not installed. Install it: sudo pacman -S grim"


def _run_grim(args: list[str], delay: int = 0) -> QPixmap:
    if delay > 0:
        time.sleep(delay)
    cmd = ["grim"]
    cmd.extend(args)
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10)
    except FileNotFoundError:
        raise RuntimeError(GRIM_NOT_FOUND)
    if result.returncode != 0:
        raise RuntimeError(f"grim failed (exit {result.returncode}): {result.stderr.decode().strip()}")
    pm = QPixmap()
    if not pm.loadFromData(result.stdout):
        raise RuntimeError("Failed to decode grim output")
    return pm


def capture_region(
    left: int,
    top: int,
    right: int,
    bottom: int,
    delay: int = 0,
    include_cursor: bool = False,
) -> QPixmap:
    w = right - left
    h = bottom - top
    args = []
    if include_cursor:
        args.append("--cursor")
    args.extend(["-g", f"{left},{top} {w}x{h}", "-"])
    return _run_grim(args, delay)


def capture_fullscreen(delay: int = 0, include_cursor: bool = False) -> QPixmap:
    args = ["--cursor"] if include_cursor else []
    args.append("-")
    return _run_grim(args, delay)
