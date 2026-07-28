# SnapCap - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import subprocess
from PySide6.QtGui import QPixmap


def capture_region(left: int, top: int, right: int, bottom: int) -> QPixmap:
    w = right - left
    h = bottom - top
    result = subprocess.run(
        ["grim", "-g", f"{left},{top} {w}x{h}", "-"],
        capture_output=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"grim failed (exit {result.returncode}): {result.stderr.decode().strip()}"
        )
    pm = QPixmap()
    if not pm.loadFromData(result.stdout):
        raise RuntimeError("Failed to decode grim output")
    return pm
