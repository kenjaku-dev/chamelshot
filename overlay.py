# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import json
import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

import proc


class RegionSelector(QObject):
    region_selected = Signal(int, int, int, int)
    cancelled = Signal()

    def __init__(self):
        super().__init__()

    def show(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            result = subprocess.run(
                ["slurp", "-f", "%x %y %w %h"],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=30,
                env=proc.env(),
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


class WindowSelector(QObject):
    region_selected = Signal(int, int, int, int)
    cancelled = Signal()
    error = Signal(str)
    pixmap_captured = Signal(object)

    def __init__(self):
        super().__init__()

    def show(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            if "NIRI_SOCKET" in os.environ:
                self._run_niri()
                return
            boxes = self._get_window_boxes()
            if not boxes:
                if "SWAYSOCK" in os.environ or "HYPRLAND_INSTANCE_SIGNATURE" in os.environ:
                    self.cancelled.emit()
                else:
                    self.error.emit(
                        "Window capture is not supported on this compositor yet. Use Capture Region instead."
                    )
                return
            args = ["slurp", "-r", "-f", "%x %y %w %h"]
            result = subprocess.run(
                args,
                input="\n".join(boxes).encode(),
                capture_output=True,
                timeout=30,
                env=proc.env(),
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

    def _run_niri(self):
        # niri's IPC only reports tile sizes/offsets, not absolute window
        # geometry (niri-wm/niri#2381), so slurp boxes are impossible. Use
        # niri's native focused-window screenshot instead. The file is written
        # asynchronously after the command returns, so poll for it briefly.
        try:
            with tempfile.TemporaryDirectory(prefix="chamelshot-") as tmp:
                out = Path(tmp) / "window.png"
                result = subprocess.run(
                    ["niri", "msg", "action", "screenshot-window", "--path", str(out)],
                    capture_output=True,
                    timeout=10,
                    env=proc.env(),
                )
                if result.returncode != 0:
                    self.error.emit("niri window capture failed: " + result.stderr.decode().strip())
                    return
                for _ in range(50):
                    if out.exists() and out.stat().st_size > 0:
                        break
                    time.sleep(0.1)
                pm = QPixmap(str(out)) if out.exists() else QPixmap()
                if pm.isNull():
                    self.error.emit("niri window capture produced an empty image")
                    return
                self.pixmap_captured.emit(pm)
        except FileNotFoundError:
            self.error.emit("niri is not installed (niri msg not found)")
        except subprocess.TimeoutExpired:
            self.error.emit("niri window capture timed out")

    def _get_window_boxes(self) -> list[str]:
        if "SWAYSOCK" in os.environ:
            return self._sway_boxes()
        if "HYPRLAND_INSTANCE_SIGNATURE" in os.environ:
            return self._hypr_boxes()
        return []

    def _sway_boxes(self) -> list[str]:
        try:
            result = subprocess.run(
                ["swaymsg", "-t", "get_tree"],
                capture_output=True,
                timeout=5,
                env=proc.env(),
            )
            if result.returncode != 0:
                return []
            tree = json.loads(result.stdout)
            boxes = []

            def walk(node):
                if node.get("type") == "output" and node.get("name", "").startswith("__"):
                    return
                rect = node.get("rect", {})
                if node.get("visible", False) and node.get("type") in ("con", "floating_con"):
                    x, y, w, h = rect.get("x", 0), rect.get("y", 0), rect.get("width", 0), rect.get("height", 0)
                    if w > 0 and h > 0:
                        boxes.append(f"{x},{y} {w}x{h}")
                for child in node.get("nodes", []):
                    walk(child)
                for child in node.get("floating_nodes", []):
                    walk(child)

            for node in tree.get("nodes", []):
                walk(node)
            return boxes
        except Exception:
            return []

    def _hypr_boxes(self) -> list[str]:
        try:
            result = subprocess.run(
                ["hyprctl", "clients", "-j"],
                capture_output=True,
                timeout=5,
                env=proc.env(),
            )
            if result.returncode != 0:
                return []
            clients = json.loads(result.stdout)
            boxes = []
            for c in clients:
                if c.get("hidden", False) or c.get("floating", False):
                    continue
                at = c.get("at", [0, 0])
                size = c.get("size", [0, 0])
                x, y = at
                w, h = size
                if w > 0 and h > 0:
                    boxes.append(f"{x},{y} {w}x{h}")
            return boxes
        except Exception:
            return []


class CountdownOverlay(QWidget):
    finished = Signal()
    cancelled = Signal()

    def __init__(self, seconds: int = 3):
        super().__init__()
        self._remaining = max(1, seconds)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.showFullScreen()

        self._label = QLabel(str(self._remaining))
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPixelSize(200)
        font.setBold(True)
        self._label.setFont(font)
        self._label.setStyleSheet("color: white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self.setStyleSheet("background-color: rgba(0, 0, 0, 120);")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self):
        self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop()
            self.close()
            self.finished.emit()
        else:
            self._label.setText(str(self._remaining))

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self._timer.stop()
            self.close()
            self.cancelled.emit()
        super().keyPressEvent(event)

    def closeEvent(self, event):  # noqa: N802
        # External close (compositor keybind, window manager): stop the count
        # and release the capture lock so _capturing isn't left stuck True.
        if self._timer.isActive():
            self._timer.stop()
            self.cancelled.emit()
        super().closeEvent(event)
