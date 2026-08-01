# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import datetime
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QCursor, QGuiApplication, QPixmap
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
import ipc
from capture import capture_async, capture_fullscreen, capture_region
from dispatcher import EventReceiver
from overlay import CountdownOverlay, RegionSelector, WindowSelector
from preview import PreviewWindow
from settings import SettingsDialog
from tray import ChamelShotTray
from version import VERSION


def _make_pixmap() -> QPixmap:
    icon_path = Path(__file__).parent / "icon.png"
    if icon_path.exists():
        pm = QPixmap(str(icon_path))
        if not pm.isNull():
            return pm
    pm = QPixmap(64, 64)
    pm.fill(0x2563EB)
    return pm


_LAUNCHER_STYLE = """
    QWidget { background: #161617; color: #d4d4d8; }
    QLabel#title {
        color: #fff; font-size: 20px; font-weight: bold;
        letter-spacing: 0.5px;
    }
    QLabel#version { color: #71717a; font-size: 11px; }
    QPushButton {
        background: #1f1f22; color: #e4e4e7;
        border: 1px solid #2e2e32; border-radius: 6px;
        padding: 9px 14px; font-size: 13px; text-align: left;
    }
    QPushButton:hover { background: #2563eb; border-color: #2563eb; color: #fff; }
    QPushButton:pressed { background: #1d4ed8; }
    QPushButton#settings { text-align: center; background: transparent; }
    QPushButton#settings:hover { background: #2a2a2e; border-color: #3a3a40; color: #e4e4e7; }
"""


class ChamelShotApp:
    def __init__(self, auto_capture=False):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("ChamelShot")
        self.app.setQuitOnLastWindowClosed(False)
        self.auto_capture = auto_capture
        self.settings = cfg.load()
        self.selector: RegionSelector | WindowSelector | None = None
        self._launcher: QWidget | None = None
        self._menu_open = False
        self._capturing = False
        self._menu: QMenu | None = None
        self._receiver = EventReceiver()
        self._setup_ipc()
        self._setup_tray()

    def _setup_ipc(self):
        ipc.clean_stale_socket(cfg.IPC_SOCKET_PATH)
        self._ipc_server = ipc.IpcServer(cfg.IPC_SOCKET_PATH, self._receiver, self._on_ipc_command)
        self._ipc_server.start()

    def _setup_tray(self):
        self.tray = ChamelShotTray(
            icon_pixmap=_make_pixmap(),
            menu_builder=self._build_menu_items,
            on_activate=self._show_tray_menu,
            on_settings=self._open_settings,
            on_menu=self._show_tray_menu,
        )

    # ---------------------------------------------------------------- IPC

    def _on_ipc_command(self, cmd: str):
        actions = {
            "capture": lambda: self.start_capture(),
            "capture-region": lambda: self._start_capture_mode("region"),
            "capture-window": lambda: self._start_capture_mode("window"),
            "capture-fullscreen": lambda: self._start_capture_mode("fullscreen"),
            "settings": self._open_settings,
            "menu": self._show_tray_menu,
            "open-history": self._open_history_folder,
            "show-launcher": self._show_launcher,
            "quit": self.app.quit,
        }
        fn = actions.get(cmd)
        if fn:
            fn()

    def _open_history_folder(self, *_args):
        cfg.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.Popen(
                ["xdg-open", str(cfg.HISTORY_DIR)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            pass

    # ---------------------------------------------------------------- Tray menu

    def _format_history_time(self, path: Path) -> str:
        try:
            ts = datetime.datetime.strptime(path.stem, "screenshot_%Y%m%d_%H%M%S_%f")
            now = datetime.datetime.now()
            if ts.date() == now.date():
                return ts.strftime("%H:%M:%S")
            if ts.date() == (now - datetime.timedelta(days=1)).date():
                return "Yesterday " + ts.strftime("%H:%M")
            return ts.strftime("%b %d %H:%M")
        except ValueError:
            return path.stem.replace("screenshot_", "").replace("_", ":", 1)[:11]

    def _build_menu_items(self) -> list:
        items = [
            {"label": "  ◻  Capture Region", "callback": lambda: self._start_capture_mode("region")},
            {"label": "  ▭  Capture Window", "callback": lambda: self._start_capture_mode("window")},
            {"label": "  ⊞  Capture Fullscreen", "callback": lambda: self._start_capture_mode("fullscreen")},
            {"type": "separator"},
            {"label": "Recent", "callback": None},
        ]

        hist = cfg.HISTORY_DIR
        shown = 0
        if hist.is_dir():
            entries = sorted(hist.glob("screenshot_*.png"), reverse=True)[: min(cfg.MAX_HISTORY, 5)]
            for entry in entries:
                label = self._format_history_time(entry)
                items.append({"label": f"  \u23f1  {label}", "callback": lambda p=entry: self._open_history_file(p)})
                shown += 1
        if not shown:
            items.append({"label": "  \u2014  No screenshots", "callback": None})

        items.extend(
            [
                {"label": "  \U0001f5c2  Open History Folder", "callback": self._open_history_folder},
                {"type": "separator"},
                {"label": "  \u2699  Settings", "callback": self._open_settings},
                {"label": "  \u2715  Kill", "callback": self.app.quit},
            ]
        )
        return items

    def _open_history_file(self, path: Path):
        try:
            subprocess.Popen(
                ["xdg-open", str(path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            pass

    def _ensure_menu(self) -> QMenu:
        """Persistent QMenu (created once — best practice: never rebuild per click).

        On Wayland the Qt::Popup flag makes Qt request an xdg_popup grab, which
        compositors reject when the click landed on another surface (the bar),
        so Qt >= 6.9 closes the menu immediately (QTBUG-139921). Mirror the
        CopyQ workaround: drop Qt::Popup, use a frameless always-on-top toplevel,
        and close explicitly when an action fires.
        """
        if self._menu is not None:
            return self._menu
        menu = QMenu()
        menu.setObjectName("trayMenu")
        if QGuiApplication.platformName() == "wayland":
            menu.setWindowFlags(
                Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
            )
            menu.triggered.connect(menu.close)
        self._menu = menu
        return menu

    def _rebuild_menu_items(self):
        menu = self._ensure_menu()
        menu.clear()
        for item in self._build_menu_items():
            if item.get("type") == "separator":
                menu.addSeparator()
                continue
            action = QAction(item.get("label", ""))
            callback = item.get("callback")
            if callback:
                action.triggered.connect(callback)
            else:
                action.setEnabled(False)
            menu.addAction(action)

    def _show_tray_menu(self, x=0, y=0):
        if self._menu_open:
            return
        self._menu_open = True
        try:
            menu = self._ensure_menu()
            self._rebuild_menu_items()

            # Coordinates come from the SNI host (ContextMenu/Activate) and are
            # reliable screen coords — prefer them over QCursor.pos(), which is
            # garbage on Wayland. (0,0) only happens for IPC "menu" commands.
            pt = QPoint(x, y)
            if pt.x() <= 0 and pt.y() <= 0:
                pt = QCursor.pos()

            menu.popup(pt)
            if QGuiApplication.platformName() == "wayland":
                # A frameless toplevel never gets focus on its own — the
                # compositor keeps focus on the previously focused window.
                menu.activateWindow()
                QApplication.setActiveWindow(menu)
                menu.setFocus()
        finally:
            self._menu_open = False

    def _open_settings(self, *_args):
        dlg = SettingsDialog()
        if dlg.exec():
            self.settings = cfg.load()

    # ---------------------------------------------------------------- Launcher

    def _show_launcher(self):
        launcher = self._launcher
        if launcher is None:
            launcher = QWidget()
            launcher.setWindowTitle(f"ChamelShot {VERSION}")
            launcher.setFixedSize(280, 260)
            launcher.setStyleSheet(_LAUNCHER_STYLE)

            layout = QVBoxLayout(launcher)
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(8)

            title = QLabel("ChamelShot")
            title.setObjectName("title")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(title)

            ver = QLabel(f"v{VERSION}")
            ver.setObjectName("version")
            ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(ver)

            layout.addSpacing(6)

            def _make_btn(text, mode):
                btn = QPushButton(text)
                btn.clicked.connect(lambda: self._start_from_launcher(mode))
                return btn

            layout.addWidget(_make_btn("  ◻  Capture Region", "region"))
            layout.addWidget(_make_btn("  ▭  Capture Window", "window"))
            layout.addWidget(_make_btn("  ⊞  Capture Fullscreen", "fullscreen"))

            layout.addSpacing(6)

            btn_settings = QPushButton("Settings")
            btn_settings.setObjectName("settings")
            btn_settings.clicked.connect(self._open_settings)
            layout.addWidget(btn_settings)
            self._launcher = launcher

        launcher.show()
        launcher.raise_()
        launcher.activateWindow()

    # ---------------------------------------------------------------- Capture

    def _start_capture_mode(self, mode):
        self.settings["capture.mode"] = mode
        self.start_capture()

    def _start_from_launcher(self, mode):
        if self._launcher:
            self._launcher.hide()
        self._start_capture_mode(mode)

    def _on_cancel(self):
        self._capturing = False
        QTimer.singleShot(0, self._show_launcher)

    def _do_capture(self, pixmap):
        self.preview = PreviewWindow(
            pixmap,
            config=self.settings,
            on_new_capture=self.start_capture,
        )
        self.preview.show()

    def _do_capture_async(self, capture_fn):
        self._capturing = True
        capture_async(
            self._receiver,
            capture_fn,
            self._on_capture_done,
            self._on_capture_error,
        )

    def _on_capture_done(self, pixmap):
        self._capturing = False
        self._do_capture(pixmap)

    def _on_capture_error(self, error):
        self._capturing = False
        QMessageBox.critical(None, "Error", f"Capture failed: {error}")

    def _do_delayed_capture(self, delay, capture_fn):
        if delay > 0:
            self._capturing = True
            self._cd = CountdownOverlay(seconds=delay)
            self._cd.finished.connect(lambda: self._do_capture_async(capture_fn))
            self._cd.show()
        else:
            self._do_capture_async(capture_fn)

    def on_region_selected(self, left, top, right, bottom):
        delay = self.settings.get("capture.delay", 0)
        cursor = self.settings.get("capture.include_cursor", False)
        self._do_delayed_capture(
            delay,
            lambda: capture_region(left, top, right, bottom, delay=0, include_cursor=cursor),
        )

    def start_capture(self):
        if self._capturing:
            return
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

    def run(self, show_launcher=True):
        if self.auto_capture:
            QTimer.singleShot(100, self.start_capture)
        elif show_launcher:
            QTimer.singleShot(0, self._show_launcher)
        return self.app.exec()


def check_deps():
    missing = [cmd for cmd in ("grim", "slurp") if shutil.which(cmd) is None]
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print("Install them with your package manager:")
        print("  Arch:        sudo pacman -S grim slurp")
        print("  Debian/Ubuntu: sudo apt install grim slurp")
        print("  Fedora:      sudo dnf install grim slurp")
        sys.exit(1)


def main():
    if "--version" in sys.argv or "-v" in sys.argv:
        print(f"chamelshot {VERSION}")
        return

    if "--install-autostart" in sys.argv:
        cfg.install_autostart()
        print("Autostart enabled")
        return
    if "--remove-autostart" in sys.argv:
        cfg.remove_autostart()
        print("Autostart disabled")
        return

    check_deps()

    # Map CLI args to an IPC command; if a daemon is already running, forward
    # the command to it and exit — this is what makes keybindings "just work"
    # without spawning duplicate instances.
    cmd = "show-launcher"
    if "--capture" in sys.argv or "-c" in sys.argv:
        cmd = "capture"
    elif "--settings" in sys.argv:
        cmd = "settings"
    elif "--test-tray" in sys.argv:
        cmd = "menu"
    elif "--open-history" in sys.argv:
        cmd = "open-history"

    if ipc.send_command(cfg.IPC_SOCKET_PATH, "ping"):
        ipc.send_command(cfg.IPC_SOCKET_PATH, cmd)
        print(f"chamelshot: forwarded '{cmd}' to running instance")
        return

    ipc.clean_stale_socket(cfg.IPC_SOCKET_PATH)

    if "--settings" in sys.argv:
        app = QApplication(sys.argv)
        dlg = SettingsDialog()
        dlg.exec()
        return

    auto_capture = "--capture" in sys.argv or "-c" in sys.argv
    app = ChamelShotApp(auto_capture=auto_capture)

    if "--test-tray" in sys.argv:
        # Start normally, then pop the tray menu ~1.5s later once the SNI
        # has registered with the tray host. If nothing appears, the tray
        # host is not calling our DBus methods.
        print("chamelshot: testing tray menu (should appear in ~1.5s)...")
        QTimer.singleShot(1500, app._show_tray_menu)
        sys.exit(app.run(show_launcher=False))

    sys.exit(app.run())


if __name__ == "__main__":
    main()
