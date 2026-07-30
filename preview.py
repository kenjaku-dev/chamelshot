# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import datetime
import os
import shutil
import subprocess

from PySide6.QtCore import QBuffer, QIODevice, Qt, QTimer
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import config as cfg
from editor import Annotator


class PreviewWindow(QWidget):
    def __init__(self, pixmap: QPixmap, config: dict | None = None, on_new_capture=None):
        super().__init__()
        self.pixmap = pixmap
        self.cfg = config or cfg.load()
        self.on_new_capture = on_new_capture
        self.setWindowTitle("ChamelShot - Screenshot")

        if self.cfg.get("preview.stay_on_top", True):
            self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)

        win_w = self.cfg.get("preview.window_width", 600)
        win_h = self.cfg.get("preview.window_height", 450)
        self.setMinimumSize(400, 300)
        self.resize(win_w, win_h)

        layout = QVBoxLayout(self)

        max_w = self.cfg.get("preview.max_width", 800)
        w, h = pixmap.width(), pixmap.height()
        display = pixmap
        if w > max_w or h > max_w:
            display = pixmap.scaled(
                max_w,
                max_w,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        self.stack = QStackedWidget()
        self.preview_label = QLabel()
        self.preview_label.setPixmap(display)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.preview_label)
        self.annotator = Annotator(pixmap)
        self.annotator.accepted.connect(self._on_annotated)
        self.annotator.cancelled.connect(self._show_preview)
        self.stack.addWidget(self.annotator)
        self.stack.setCurrentWidget(self.preview_label)
        layout.addWidget(self.stack, 1)

        btn_layout = QHBoxLayout()
        btn_capture = QPushButton("New Capture")
        btn_capture.clicked.connect(self.new_capture)
        btn_layout.addWidget(btn_capture)
        btn_layout.addStretch()
        btn_annotate = QPushButton("Annotate")
        btn_annotate.clicked.connect(self._show_annotator)
        btn_layout.addWidget(btn_annotate)
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
        btn_close.setToolTip("Minimize to tray")
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_close)
        btn_quit = QPushButton("Quit")
        btn_quit.setToolTip("Exit ChamelShot")
        btn_quit.clicked.connect(QApplication.quit)
        btn_layout.addWidget(btn_quit)
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
            QTimer.singleShot(50, lambda: self.copy_to_clipboard(closing=False))

    def _save_to_history(self, pixmap: QPixmap):
        hist_dir = cfg.HISTORY_DIR
        hist_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = hist_dir / f"screenshot_{ts}.png"
        pixmap.save(str(path), "PNG")
        entries = sorted(hist_dir.glob("screenshot_*.png"), reverse=True)
        for old in entries[cfg.MAX_HISTORY :]:
            old.unlink(missing_ok=True)

    def _auto_save(self):
        path = cfg.generate_save_path(self.cfg)
        fmt = self.cfg.get("save.format", "PNG")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        quality = self.cfg.get("save.quality", -1)
        if quality >= 0:
            self.pixmap.save(path, fmt, quality)
        else:
            self.pixmap.save(path, fmt)
        self._save_to_history(self.pixmap)

    def _notify(self, message: str):
        if not self.cfg.get("general.notification", True):
            return
        try:
            subprocess.run(
                ["notify-send", "ChamelShot", message],
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

    def _current_pixmap(self) -> QPixmap:
        if self.stack.currentWidget() == self.annotator and self.annotator.canvas.annotations:
            return self.annotator.canvas.result_pixmap()
        return self.pixmap

    def save(self):
        try:
            fmt = self.cfg.get("save.format", "PNG")
            quality = self.cfg.get("save.quality", -1)
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Screenshot",
                os.path.expanduser("~/chamelshot.png"),
                f"{fmt} (*.{fmt.lower()})",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if path:
                px = self._current_pixmap()
                if quality >= 0:
                    px.save(path, fmt, quality)
                else:
                    px.save(path, fmt)
                self._save_to_history(px)
                self._notify(f"Saved to {path}")
                self.close()
        except Exception as e:
            QMessageBox.warning(self, "Save Error", str(e))

    def copy_to_clipboard(self, closing=True):
        try:
            px = self._current_pixmap()
            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.ReadWrite)
            if not px.save(buf, "PNG"):
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
                QApplication.clipboard().setPixmap(px)

            self._notify("Copied to clipboard")
            if closing:
                self.close()
        except Exception as e:
            QMessageBox.warning(self, "Copy Error", str(e))

    def _show_annotator(self):
        self.annotator.canvas.source = self.pixmap
        self.annotator.canvas.annotations.clear()
        self.annotator.canvas._history.clear()
        self.annotator.canvas._redo_stack.clear()
        self.annotator.canvas.update()
        self.stack.setCurrentWidget(self.annotator)

    def _show_preview(self):
        self.stack.setCurrentWidget(self.preview_label)

    def _on_annotated(self, annotated: QPixmap):
        self.pixmap = annotated
        self._update_preview_display()
        self._show_preview()

    def _update_preview_display(self):
        max_w = self.cfg.get("preview.max_width", 800)
        w, h = self.pixmap.width(), self.pixmap.height()
        display = self.pixmap
        if w > max_w or h > max_w:
            display = self.pixmap.scaled(
                max_w,
                max_w,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.preview_label.setPixmap(display)

    def new_capture(self):
        self.close()
        if self.on_new_capture:
            self.on_new_capture()
