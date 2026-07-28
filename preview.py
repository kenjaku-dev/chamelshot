# SnapCap - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import os
import shutil
import subprocess

from PySide6.QtCore import QBuffer, Qt, QTimer
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import config as cfg


class PreviewWindow(QWidget):
    def __init__(self, pixmap: QPixmap, config: dict = None, on_new_capture=None):
        super().__init__()
        self.pixmap = pixmap
        self.cfg = config or cfg.load()
        self.on_new_capture = on_new_capture
        self.setWindowTitle("SnapCap - Screenshot")

        if self.cfg.get("preview.stay_on_top", True):
            self.setWindowFlags(Qt.WindowStaysOnTopHint)

        win_w = self.cfg.get("preview.window_width", 600)
        win_h = self.cfg.get("preview.window_height", 450)
        self.setMinimumSize(400, 300)
        self.resize(win_w, win_h)

        layout = QVBoxLayout(self)

        max_w = self.cfg.get("preview.max_width", 800)
        w, h = pixmap.width(), pixmap.height()
        display = pixmap
        if w > max_w or h > max_w:
            display = pixmap.scaled(max_w, max_w, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self.label = QLabel()
        self.label.setPixmap(display)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        btn_layout = QHBoxLayout()
        btn_capture = QPushButton("New Capture")
        btn_capture.clicked.connect(self.new_capture)
        btn_layout.addWidget(btn_capture)
        btn_layout.addStretch()
        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self.save)
        btn_layout.addWidget(btn_save)
        btn_copy = QPushButton("Copy")
        btn_copy.clicked.connect(self.copy_to_clipboard)
        btn_layout.addWidget(btn_copy)
        btn_settings = QPushButton("Settings")
        btn_settings.clicked.connect(self._open_settings)
        btn_layout.addWidget(btn_settings)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        self._bind_shortcuts()
        self._apply_auto_actions()

    def _bind_shortcuts(self):
        mapping = {
            "save": self.save,
            "copy": self.copy_to_clipboard,
            "close": self.close,
        }
        if self.on_new_capture:
            mapping["new_capture"] = self.new_capture
        for key, fn in mapping.items():
            raw = self.cfg.get(f"shortcuts.{key}", "")
            if raw:
                ks = QKeySequence.fromString(raw)
                if not ks.isEmpty():
                    QShortcut(ks, self).activated.connect(fn)

    def _apply_auto_actions(self):
        if self.cfg.get("general.auto_save"):
            self._auto_save()
        if self.cfg.get("general.auto_copy"):
            QTimer.singleShot(50, self.copy_to_clipboard)

    def _auto_save(self):
        path = cfg.generate_save_path(self.cfg)
        fmt = self.cfg.get("save.format", "PNG")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        quality = self.cfg.get("save.quality", -1)
        if quality >= 0:
            self.pixmap.save(path, fmt, quality)
        else:
            self.pixmap.save(path, fmt)

    def _notify(self, message: str):
        if not self.cfg.get("general.notification", True):
            return
        try:
            subprocess.run(
                ["notify-send", "SnapCap", message],
                timeout=3,
                stdin=subprocess.DEVNULL,
            )
        except Exception:
            pass

    def _open_settings(self):
        from settings import SettingsDialog

        dlg = SettingsDialog(self, config=self.cfg)
        if dlg.exec():
            self.cfg = cfg.load()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        screen = self.screen()
        if screen:
            center = screen.availableGeometry().center()
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

    def save(self):
        try:
            fmt = self.cfg.get("save.format", "PNG")
            quality = self.cfg.get("save.quality", -1)
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Screenshot",
                os.path.expanduser("~/snapcap.png"),
                f"{fmt} (*.{fmt.lower()})",
                options=QFileDialog.DontUseNativeDialog,
            )
            if path:
                if quality >= 0:
                    self.pixmap.save(path, fmt, quality)
                else:
                    self.pixmap.save(path, fmt)
                self._notify(f"Saved to {path}")
                self.close()
        except Exception as e:
            QMessageBox.warning(self, "Save Error", str(e))

    def copy_to_clipboard(self, closing=True):
        try:
            buf = QBuffer()
            buf.open(QBuffer.ReadWrite)
            if not self.pixmap.save(buf, "PNG"):
                raise RuntimeError("Failed to encode PNG")
            png_data = buf.data().data()
            buf.close()

            tool = self.cfg.get("clipboard.tool", "wl-copy")
            if tool in ("wl-copy", "both"):
                if shutil.which("wl-copy"):
                    subprocess.run(
                        ["wl-copy", "--type", "image/png"],
                        input=png_data,
                        timeout=5,
                    )
            if tool in ("qt", "both"):
                QApplication.clipboard().setPixmap(self.pixmap)

            self._notify("Copied to clipboard")
            if closing:
                self.close()
        except Exception as e:
            QMessageBox.warning(self, "Copy Error", str(e))

    def new_capture(self):
        self.close()
        if self.on_new_capture:
            self.on_new_capture()
