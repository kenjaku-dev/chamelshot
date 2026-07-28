# SnapCap - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import re
import subprocess

from PySide6.QtCore import QObject, Signal


class RegionSelector(QObject):
    region_selected = Signal(int, int, int, int)
    cancelled = Signal()

    def __init__(self):
        super().__init__()

    def show(self):
        try:
            result = subprocess.run(
                ["slurp", "-f", "%x %y %w %h"],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=30,
            )
            if result.returncode != 0:
                self.cancelled.emit()
                return
            output = result.stdout.decode().strip()
            match = re.match(r"(\d+) (\d+) (\d+) (\d+)", output)
            if match:
                x, y, w, h = map(int, match.groups())
                self.region_selected.emit(x, y, x + w, y + h)
            else:
                self.cancelled.emit()
        except subprocess.TimeoutExpired:
            self.cancelled.emit()
