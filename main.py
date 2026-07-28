# SnapCap - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import sys
import shutil

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from capture import capture_region
from overlay import RegionSelector
from preview import PreviewWindow


class SnapCapApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("SnapCap")
        self.app.setQuitOnLastWindowClosed(True)

    def start_capture(self):
        self.selector = RegionSelector()
        self.selector.region_selected.connect(self.on_region_selected)
        self.selector.cancelled.connect(self.app.quit)
        self.selector.show()

    def on_region_selected(self, left, top, right, bottom):
        try:
            pixmap = capture_region(left, top, right, bottom)
            self.preview = PreviewWindow(pixmap, on_new_capture=self.start_capture)
            self.preview.show()
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Capture failed: {e}")
            self.app.quit()

    def run(self):
        QTimer.singleShot(100, self.start_capture)
        return self.app.exec()


def check_deps():
    missing = [cmd for cmd in ("grim", "slurp") if shutil.which(cmd) is None]
    if missing:
        print(
            f"Missing dependencies: {', '.join(missing)}\n"
            f"Install: sudo pacman -S {' '.join(missing)}"
        )
        sys.exit(1)


def main():
    check_deps()
    app = SnapCapApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
