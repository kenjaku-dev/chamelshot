# SnapCap - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import config as cfg
from capture import capture_fullscreen, capture_region
from overlay import RegionSelector
from preview import PreviewWindow
from settings import SettingsDialog
from tray import SnapCapTray


def _make_pixmap() -> QPixmap:
    icon_path = Path(__file__).parent / "icon.png"
    if icon_path.exists():
        pm = QPixmap(str(icon_path))
        if not pm.isNull():
            return pm
    pm = QPixmap(64, 64)
    pm.fill(0x2563EB)
    return pm


class SnapCapApp:
    def __init__(self, daemon=False, auto_capture=False):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("SnapCap")
        self.app.setQuitOnLastWindowClosed(not daemon)
        self.daemon = daemon
        self.auto_capture = auto_capture
        self.settings = cfg.load()
        self.selector: RegionSelector | None = None
        self.tray = None
        self._from_launcher = False

        if daemon:
            self._setup_tray()

    def _setup_tray(self):
        self._tray_menu = QMenu()
        cap_action = QAction("Capture Region")
        cap_action.triggered.connect(self.start_capture)
        self._tray_menu.addAction(cap_action)

        self._tray_menu.addSeparator()
        set_action = QAction("Settings")
        set_action.triggered.connect(self._open_settings)
        self._tray_menu.addAction(set_action)

        self._tray_menu.addSeparator()
        quit_action = QAction("Quit")
        quit_action.triggered.connect(self.app.quit)
        self._tray_menu.addAction(quit_action)

        self.tray = SnapCapTray(
            icon_pixmap=_make_pixmap(),
            on_activate=self.start_capture,
            on_settings=self._open_settings,
            on_menu=self._show_tray_menu,
        )

    def _show_tray_menu(self, x=0, y=0):
        self._tray_menu.popup(QPoint(x, y))

    def _open_settings(self):
        dlg = SettingsDialog()
        if dlg.exec():
            self.settings = cfg.load()

    def _show_launcher(self):
        self._launcher = QWidget()
        self._launcher.setWindowTitle("SnapCap")
        self._launcher.setFixedSize(260, 200)

        layout = QVBoxLayout(self._launcher)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        title = QLabel("SnapCap")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(title)

        btn_region = QPushButton("Capture Region")
        btn_region.clicked.connect(lambda: self._start_from_launcher("region"))
        layout.addWidget(btn_region)

        btn_fullscreen = QPushButton("Capture Fullscreen")
        btn_fullscreen.clicked.connect(lambda: self._start_from_launcher("fullscreen"))
        layout.addWidget(btn_fullscreen)

        btn_settings = QPushButton("Settings")
        btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(btn_settings)

        self._launcher.show()

    def _start_from_launcher(self, mode):
        self._from_launcher = True
        self._launcher.hide()
        self.settings["capture.mode"] = mode
        self.start_capture()

    def _on_cancel(self):
        if self._from_launcher:
            self._launcher.show()
        elif not self.daemon:
            QTimer.singleShot(0, self.app.quit)

    def _do_capture(self, pixmap):
        self.preview = PreviewWindow(
            pixmap,
            config=self.settings,
            on_new_capture=self.start_capture,
        )
        self.preview.show()
        if not self.daemon:
            self.preview.destroyed.connect(self.app.quit)

    def on_region_selected(self, left, top, right, bottom):
        try:
            delay = self.settings.get("capture.delay", 0)
            cursor = self.settings.get("capture.include_cursor", False)
            pixmap = capture_region(left, top, right, bottom, delay=delay, include_cursor=cursor)
            self._do_capture(pixmap)
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Capture failed: {e}")
            if not self.daemon:
                self.app.quit()

    def start_capture(self):
        mode = self.settings.get("capture.mode", "region")
        if mode == "fullscreen":
            try:
                delay = self.settings.get("capture.delay", 0)
                cursor = self.settings.get("capture.include_cursor", False)
                pixmap = capture_fullscreen(delay=delay, include_cursor=cursor)
                self._do_capture(pixmap)
            except Exception as e:
                QMessageBox.critical(None, "Error", f"Capture failed: {e}")
                if not self.daemon:
                    self.app.quit()
        else:
            self.selector = RegionSelector()
            self.selector.region_selected.connect(self.on_region_selected)
            self.selector.cancelled.connect(self._on_cancel)
            self.selector.show()

    def run(self):
        if self.auto_capture:
            QTimer.singleShot(100, self.start_capture)
        elif not self.daemon:
            QTimer.singleShot(0, self._show_launcher)
        return self.app.exec()


def check_deps():
    missing = [cmd for cmd in ("grim", "slurp") if shutil.which(cmd) is None]
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}\nInstall: sudo pacman -S {' '.join(missing)}")
        sys.exit(1)


def main():
    check_deps()
    daemon = "--daemon" in sys.argv or "-d" in sys.argv
    open_settings = "--settings" in sys.argv
    auto_capture = "--capture" in sys.argv or "-c" in sys.argv

    if open_settings:
        app = QApplication(sys.argv)
        dlg = SettingsDialog()
        dlg.exec()
        return

    app = SnapCapApp(daemon=daemon, auto_capture=auto_capture)
    sys.exit(app.run())


if __name__ == "__main__":
    main()
