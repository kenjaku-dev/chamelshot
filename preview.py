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

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QKeySequence, QShortcut, QClipboard
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QApplication,
    QFileDialog,
    QMessageBox,
)


class PreviewWindow(QWidget):
    def __init__(self, pixmap: QPixmap, on_new_capture=None):
        super().__init__()
        self.pixmap = pixmap
        self.on_new_capture = on_new_capture
        self.setWindowTitle("SnapCap - Screenshot")
        self.setMinimumSize(400, 300)
        self.resize(600, 450)

        layout = QVBoxLayout(self)

        SCREEN_MAX = 800
        w, h = pixmap.width(), pixmap.height()
        display = pixmap
        if w > SCREEN_MAX or h > SCREEN_MAX:
            display = pixmap.scaled(
                SCREEN_MAX, SCREEN_MAX, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

        self.label = QLabel()
        self.label.setPixmap(display)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        btn_layout = QHBoxLayout()

        btn_capture = QPushButton("New Capture")
        btn_capture.clicked.connect(self.new_capture)
        btn_layout.addWidget(btn_capture)

        btn_layout.addStretch()

        btn_save = QPushButton("Save (Ctrl+S)")
        btn_save.clicked.connect(self.save)
        btn_layout.addWidget(btn_save)

        btn_copy = QPushButton("Copy (Ctrl+C)")
        btn_copy.clicked.connect(self.copy_to_clipboard)
        btn_layout.addWidget(btn_copy)

        btn_close = QPushButton("Close (Esc)")
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

        QShortcut(QKeySequence(Qt.CTRL | Qt.Key_S), self).activated.connect(self.save)
        QShortcut(QKeySequence(Qt.CTRL | Qt.Key_C), self).activated.connect(self.copy_to_clipboard)
        QShortcut(Qt.Key_Escape, self).activated.connect(self.close)

        if self.on_new_capture:
            QShortcut(QKeySequence(Qt.CTRL | Qt.Key_N), self).activated.connect(self.new_capture)

    def showEvent(self, event):
        super().showEvent(event)
        screen = self.screen()
        if screen:
            center = screen.availableGeometry().center()
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

    def save(self):
        try:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Screenshot",
                os.path.expanduser("~/snapcap.png"),
                "PNG (*.png)",
                options=QFileDialog.DontUseNativeDialog,
            )
            if path:
                self.pixmap.save(path, "PNG")
                self.close()
        except Exception as e:
            QMessageBox.warning(self, "Save Error", str(e))

    def copy_to_clipboard(self):
        try:
            from PySide6.QtCore import QBuffer

            buf = QBuffer()
            buf.open(QBuffer.ReadWrite)
            if not self.pixmap.save(buf, "PNG"):
                raise RuntimeError("Failed to encode PNG")
            png_data = buf.data().data()
            buf.close()

            if shutil.which("wl-copy"):
                subprocess.run(
                    ["wl-copy", "--type", "image/png"],
                    input=png_data,
                    timeout=5,
                )
            else:
                QApplication.clipboard().setPixmap(self.pixmap)
            self.close()
        except Exception as e:
            QMessageBox.warning(self, "Copy Error", str(e))

    def new_capture(self):
        self.close()
        if self.on_new_capture:
            self.on_new_capture()
