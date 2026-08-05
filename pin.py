# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Pinned screenshots: in-memory, frameless, always-on-top reference windows.

PinStore is the pure, Qt-free lifecycle model (unit-tested); PinWindow is the
frameless widget that renders one pin. Pins are ephemeral: they are not copied
to history, produce no file on disk, and all close when the app quits.
"""

import shutil
import subprocess

from PySide6.QtCore import QBuffer, QEvent, QIODevice, Qt, QTimer
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import config as cfg
import proc

PIN_BAR_STYLE = """
    QWidget { background: rgba(30, 30, 30, 190); border-radius: 6px; }
    QPushButton {
        background: transparent; color: #ccc; border: none;
        border-radius: 4px; padding: 6px 10px; font-size: 12px;
    }
    QPushButton:hover { background: #333; color: #fff; }
"""


class PinStore:
    """Registry of open pins. Holds opaque handles so tests need no Qt."""

    def __init__(self):
        self._pins = {}
        self._next_id = 0

    def add(self, handle) -> int:
        pin_id = self._next_id
        self._next_id += 1
        self._pins[pin_id] = handle
        return pin_id

    def remove(self, pin_id: int) -> bool:
        return self._pins.pop(pin_id, None) is not None

    def close_all(self):
        closed = list(self._pins.values())
        self._pins.clear()
        return closed

    def count(self) -> int:
        return len(self._pins)


class PinWindow(QWidget):
    """Frameless always-on-top window showing one pinned screenshot.

    Drag anywhere to move; Escape or the bar's Close to unpin; images larger
    than the screen scroll inside a scroll area. Copy/Save reuse the same
    clipboard/format settings as the preview window.
    """

    def __init__(self, pixmap: QPixmap, store: PinStore, on_reedit=None):
        super().__init__()
        self.pixmap = pixmap
        self.store = store
        self.on_reedit = on_reedit
        self.pin_id = self.store.add(self)
        self.cfg = cfg.load()

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumSize(120, 90)
        self._size_to_pixmap(pixmap)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area, 1)

        self.image_label = QLabel()
        self.image_label.setPixmap(pixmap)
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.viewport().installEventFilter(self)

        self.toolbar = QWidget()
        self.toolbar.setStyleSheet(PIN_BAR_STYLE)
        self.toolbar.setVisible(False)
        bar = QHBoxLayout(self.toolbar)
        bar.setContentsMargins(6, 4, 6, 4)
        bar.setSpacing(4)
        for text, slot in (
            ("Copy", self._copy),
            ("Save", self._save),
            ("Re-edit", self._re_edit),
            ("Close", self.close),
        ):
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            bar.addWidget(btn)
        layout.addWidget(self.toolbar)

        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self.close)

    def _size_to_pixmap(self, pixmap: QPixmap):
        work = self.screen().availableGeometry() if self.screen() else None
        w, h = pixmap.width(), pixmap.height()
        if work:
            w, h = min(w, work.width()), min(h, work.height())
        self.resize(w, h)

    def enterEvent(self, event):  # noqa: N802
        self.toolbar.setVisible(True)
        self.toolbar.raise_()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        QTimer.singleShot(200, lambda: self.toolbar.setVisible(self.underMouse()))
        super().leaveEvent(event)

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.scroll_area.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._dragging = True
            return False
        if (
            obj is self.scroll_area.viewport()
            and event.type() == QEvent.Type.MouseMove
            and getattr(self, "_dragging", False)
        ):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            return False
        if obj is self.scroll_area.viewport() and event.type() == QEvent.Type.MouseButtonRelease:
            self._dragging = False
            return False
        return super().eventFilter(obj, event)

    def _copy(self):
        tool = self.cfg.get("clipboard.tool", "wl-copy")
        if tool in ("qt", "both"):
            QApplication.clipboard().setPixmap(self.pixmap)
        if tool in ("wl-copy", "both") and shutil.which("wl-copy"):
            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.ReadWrite)
            if self.pixmap.save(buf, "PNG"):
                subprocess.run(
                    ["wl-copy", "--type", "image/png"],
                    input=buf.data().data(),
                    timeout=5,
                    env=proc.env(),
                )
            buf.close()
        self._notify("Pinned image copied")

    def _save(self):
        default_path = cfg.generate_save_path(self.cfg)
        fmt = self.cfg.get("save.format", "PNG")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Pinned Image",
            default_path,
            f"{fmt} (*.{fmt.lower()})",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return
        quality = self.cfg.get("save.quality", -1)
        fmt_bytes = fmt.encode()
        ok = self.pixmap.save(path, fmt_bytes) if quality < 0 else self.pixmap.save(path, fmt_bytes, quality)
        if not ok:
            QMessageBox.warning(self, "Save Error", f"Failed to write file: {path}")
            return
        self._notify(f"Saved to {path}")

    def _re_edit(self):
        if self.on_reedit:
            self.on_reedit(self.pixmap)

    def _notify(self, message: str):
        if not self.cfg.get("general.notification", True):
            return
        try:
            subprocess.Popen(
                ["notify-send", "ChamelShot", message],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=proc.env(),
            )
        except Exception:
            pass

    def closeEvent(self, event):  # noqa: N802
        self.store.remove(self.pin_id)
        super().closeEvent(event)
