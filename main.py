# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import shutil
import subprocess
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
from overlay import CountdownOverlay, RegionSelector, WindowSelector
from preview import PreviewWindow
from settings import SettingsDialog
from tray import ChamelShotTray


def _make_pixmap() -> QPixmap:
    icon_path = Path(__file__).parent / "icon.png"
    if icon_path.exists():
        pm = QPixmap(str(icon_path))
        if not pm.isNull():
            return pm
    pm = QPixmap(64, 64)
    pm.fill(0x2563EB)
    return pm


class ChamelShotApp:
    def __init__(self, auto_capture=False):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("ChamelShot")
        self.app.setQuitOnLastWindowClosed(False)
        self.auto_capture = auto_capture
        self.settings = cfg.load()
        self.selector: RegionSelector | WindowSelector | None = None
        self._from_launcher = False
        self._setup_tray()

    def _setup_tray(self):
        self._tray_menu = QMenu()
        cap_action = QAction("Capture Region")
        cap_action.triggered.connect(lambda: self._start_capture_mode("region"))
        self._tray_menu.addAction(cap_action)
        win_action = QAction("Capture Window")
        win_action.triggered.connect(lambda: self._start_capture_mode("window"))
        self._tray_menu.addAction(win_action)
        fs_action = QAction("Capture Fullscreen")
        fs_action.triggered.connect(lambda: self._start_capture_mode("fullscreen"))
        self._tray_menu.addAction(fs_action)

        self._tray_menu.addSeparator()
        self._history_menu = self._tray_menu.addMenu("History")
        self._rebuild_history_menu()

        self._tray_menu.addSeparator()
        set_action = QAction("Settings")
        set_action.triggered.connect(self._open_settings)
        self._tray_menu.addAction(set_action)

        self._tray_menu.addSeparator()
        quit_action = QAction("Quit")
        quit_action.triggered.connect(self.app.quit)
        self._tray_menu.addAction(quit_action)

        self.tray = ChamelShotTray(
            icon_pixmap=_make_pixmap(),
            on_activate=self.start_capture,
            on_settings=self._open_settings,
            on_menu=self._show_tray_menu,
        )

    def _rebuild_history_menu(self):
        self._history_menu.clear()
        hist = cfg.HISTORY_DIR
        if not hist.is_dir():
            self._history_menu.addAction("(empty)").setEnabled(False)
            return
        entries = sorted(hist.glob("screenshot_*.png"), reverse=True)[: cfg.MAX_HISTORY]
        if not entries:
            self._history_menu.addAction("(empty)").setEnabled(False)
            return
        for entry in entries:
            ts = entry.stem.replace("screenshot_", "").replace("_", ":", 1)
            action = QAction(ts)
            action.triggered.connect(lambda _, p=str(entry): subprocess.run(["xdg-open", p], stdin=subprocess.DEVNULL))
            self._history_menu.addAction(action)
        self._tray_menu.setActiveAction(self._history_menu.menuAction())

    def _show_tray_menu(self, x=0, y=0):
        self._tray_menu.popup(QPoint(x, y))

    def _open_settings(self):
        dlg = SettingsDialog()
        if dlg.exec():
            self.settings = cfg.load()

    def _show_launcher(self):
        self._launcher = QWidget()
        self._launcher.setWindowTitle("ChamelShot")
        self._launcher.setFixedSize(260, 200)

        layout = QVBoxLayout(self._launcher)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        title = QLabel("ChamelShot")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(title)

        btn_region = QPushButton("Capture Region")
        btn_region.clicked.connect(lambda: self._start_from_launcher("region"))
        layout.addWidget(btn_region)

        btn_fullscreen = QPushButton("Capture Fullscreen")
        btn_fullscreen.clicked.connect(lambda: self._start_from_launcher("fullscreen"))
        layout.addWidget(btn_fullscreen)

        btn_window = QPushButton("Capture Window")
        btn_window.clicked.connect(lambda: self._start_from_launcher("window"))
        layout.addWidget(btn_window)

        btn_settings = QPushButton("Settings")
        btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(btn_settings)

        self._launcher.show()

    def _start_capture_mode(self, mode):
        self.settings["capture.mode"] = mode
        self.start_capture()

    def _start_from_launcher(self, mode):
        self._from_launcher = True
        self._launcher.hide()
        self._start_capture_mode(mode)

    def _on_cancel(self):
        if self._from_launcher:
            self._launcher.show()
        else:
            QTimer.singleShot(0, self._show_launcher)

    def _do_capture(self, pixmap):
        self._rebuild_history_menu()
        self.preview = PreviewWindow(
            pixmap,
            config=self.settings,
            on_new_capture=self.start_capture,
        )
        self.preview.show()

    def _do_delayed_capture(self, delay, capture_fn):
        if delay > 0:
            self._cd = CountdownOverlay(seconds=delay)

            def _go():
                try:
                    pixmap = capture_fn()
                    self._do_capture(pixmap)
                except Exception as e:
                    QMessageBox.critical(None, "Error", f"Capture failed: {e}")

            self._cd.finished.connect(_go)
            self._cd.show()
        else:
            try:
                pixmap = capture_fn()
                self._do_capture(pixmap)
            except Exception as e:
                QMessageBox.critical(None, "Error", f"Capture failed: {e}")

    def on_region_selected(self, left, top, right, bottom):
        delay = self.settings.get("capture.delay", 0)
        cursor = self.settings.get("capture.include_cursor", False)
        self._do_delayed_capture(
            delay,
            lambda: capture_region(left, top, right, bottom, delay=0, include_cursor=cursor),
        )

    def start_capture(self):
        mode = self.settings.get("capture.mode", "region")
        if mode == "fullscreen":
            delay = self.settings.get("capture.delay", 0)
            cursor = self.settings.get("capture.include_cursor", False)
            self._do_delayed_capture(
                delay,
                lambda: capture_fullscreen(delay=0, include_cursor=cursor),
            )
        elif mode == "window":
            self.selector = WindowSelector()
            self.selector.region_selected.connect(self.on_region_selected)
            self.selector.cancelled.connect(self._on_cancel)
            self.selector.show()
        else:
            self.selector = RegionSelector()
            self.selector.region_selected.connect(self.on_region_selected)
            self.selector.cancelled.connect(self._on_cancel)
            self.selector.show()

    def run(self):
        if self.auto_capture:
            QTimer.singleShot(100, self.start_capture)
        else:
            QTimer.singleShot(0, self._show_launcher)
        return self.app.exec()


def check_deps():
    missing = [cmd for cmd in ("grim", "slurp") if shutil.which(cmd) is None]
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}\nInstall: sudo pacman -S {' '.join(missing)}")
        sys.exit(1)


def main():
    check_deps()

    if "--install-autostart" in sys.argv:
        cfg.install_autostart()
        print("Autostart enabled")
        return
    if "--remove-autostart" in sys.argv:
        cfg.remove_autostart()
        print("Autostart disabled")
        return

    open_settings = "--settings" in sys.argv
    auto_capture = "--capture" in sys.argv or "-c" in sys.argv

    if open_settings:
        app = QApplication(sys.argv)
        dlg = SettingsDialog()
        dlg.exec()
        return

    app = ChamelShotApp(auto_capture=auto_capture)
    sys.exit(app.run())


if __name__ == "__main__":
    main()
