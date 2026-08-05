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
from typing import TYPE_CHECKING

import config as cfg
import ipc
import proc
from version import VERSION

if TYPE_CHECKING:
    from PySide6.QtCore import QBuffer, QIODevice, QPoint, Qt, QTimer
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

    from capture import capture_async, capture_fullscreen, capture_region
    from dispatcher import EventReceiver
    from history import HistoryDialog
    from overlay import CountdownOverlay, RegionSelector, WindowSelector
    from preview import PreviewWindow
    from settings import SettingsDialog
    from tray import ChamelShotTray

# Heavy imports (PySide6, gi, capture/overlay/preview/settings/tray) happen
# lazily in _load_gui(), so `--version`, `--install-autostart`, and the IPC
# forward path run in ~50ms instead of paying ~1s of Qt import on every
# keybind press.
_loaded_gui = False


def _load_gui():
    global _loaded_gui
    if _loaded_gui:
        return
    import PySide6.QtCore as qtcore  # noqa: N813
    import PySide6.QtGui as qtgui  # noqa: N813
    import PySide6.QtWidgets as qtw  # noqa: N813

    import capture as cap
    import dispatcher as disp
    import history as hst
    import overlay as ov
    import preview as prv
    import settings as stg
    import tray as tr

    g = globals()
    g["QPoint"] = qtcore.QPoint
    g["QBuffer"] = qtcore.QBuffer
    g["QIODevice"] = qtcore.QIODevice
    g["Qt"] = qtcore.Qt
    g["QTimer"] = qtcore.QTimer
    g["QAction"] = qtgui.QAction
    g["QCursor"] = qtgui.QCursor
    g["QGuiApplication"] = qtgui.QGuiApplication
    g["QPixmap"] = qtgui.QPixmap
    g["QApplication"] = qtw.QApplication
    g["QLabel"] = qtw.QLabel
    g["QMenu"] = qtw.QMenu
    g["QMessageBox"] = qtw.QMessageBox
    g["QPushButton"] = qtw.QPushButton
    g["QVBoxLayout"] = qtw.QVBoxLayout
    g["QWidget"] = qtw.QWidget
    g["capture_async"] = cap.capture_async
    g["capture_fullscreen"] = cap.capture_fullscreen
    g["capture_region"] = cap.capture_region
    g["EventReceiver"] = disp.EventReceiver
    g["CountdownOverlay"] = ov.CountdownOverlay
    g["RegionSelector"] = ov.RegionSelector
    g["WindowSelector"] = ov.WindowSelector
    g["PreviewWindow"] = prv.PreviewWindow
    g["SettingsDialog"] = stg.SettingsDialog
    g["HistoryDialog"] = hst.HistoryDialog
    g["ChamelShotTray"] = tr.ChamelShotTray
    _loaded_gui = True


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
        self._history_dlg = None
        self.preview: PreviewWindow | None = None
        self._capturing = False
        self._from_launcher = False
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
            "open-history-ui": self._open_history_ui,
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
                env=proc.env(),
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
            {"label": "  \u25a6  Show Interface", "callback": self._show_launcher},
            {"type": "separator"},
            {"label": "  ◻  Capture Region", "callback": lambda: self._start_capture_mode("region")},
            {"label": "  ▭  Capture Window", "callback": lambda: self._start_capture_mode("window")},
            {"label": "  ⊞  Capture Fullscreen", "callback": lambda: self._start_capture_mode("fullscreen")},
            {"type": "separator"},
        ]

        recent: list[dict] = []
        hist = cfg.HISTORY_DIR
        if hist.is_dir():
            entries = sorted(hist.glob("screenshot_*.png"), reverse=True)[: min(cfg.MAX_HISTORY, 5)]
            for idx, entry in enumerate(entries, start=1):
                label = self._format_history_time(entry)
                recent.append(
                    {
                        "label": f"  \u231f  [{idx}] {label}",
                        "children": [
                            {"label": "  \u270e  Re-edit", "callback": lambda p=entry: self._reopen_for_edit(p)},
                            {"label": "  \U0001f5c2  Open", "callback": lambda p=entry: self._open_history_file(p)},
                            {"label": "  \u29c9  Copy", "callback": lambda p=entry: self._copy_history_file(p)},
                        ],
                    }
                )
        if not recent:
            recent.append({"label": "  \u2014  No screenshots", "callback": None})
        items.append({"label": "  \u231f  Recent", "children": recent})

        items.extend(
            [
                {"label": "  \U0001f5c2  History Browser", "callback": self._open_history_ui},
                {"label": "  \U0001f5c2  Open History Folder", "callback": self._open_history_folder},
                {"type": "separator"},
                {"label": "  \u2699  Settings", "callback": self._open_settings},
                {"label": "  \u2715  Kill", "callback": self.app.quit},
            ]
        )
        return items

    def _open_history_ui(self, *_args):
        dlg = getattr(self, "_history_dlg", None)
        if dlg is None or not dlg.isVisible():
            dlg = HistoryDialog(config=self.settings, on_edit=self._reopen_for_edit)
            self._history_dlg = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _reopen_for_edit(self, path: Path):
        pm = QPixmap(str(path))
        if pm.isNull():
            QMessageBox.warning(None, "Re-edit", f"Could not load image:\n{path}")
            return
        old = getattr(self, "preview", None)
        if old is not None:
            old.close()
        self.preview = PreviewWindow(
            pm,
            config=self.settings,
            on_new_capture=self.start_capture,
            source_path=str(path),
        )
        self.preview.show()

    def _copy_history_file(self, path: Path):
        pm = QPixmap(str(path))
        if pm.isNull():
            QMessageBox.warning(None, "Copy", f"Could not load image:\n{path}")
            return
        tool = self.settings.get("clipboard.tool", "wl-copy")
        if tool in ("qt", "both"):
            QApplication.clipboard().setPixmap(pm)
        if tool in ("wl-copy", "both") and shutil.which("wl-copy"):
            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.ReadWrite)
            if pm.save(buf, "PNG"):
                subprocess.run(
                    ["wl-copy", "--type", "image/png"],
                    input=buf.data().data(),
                    timeout=5,
                    env=proc.env(),
                )
            buf.close()

    def _open_history_file(self, path: Path):
        try:
            subprocess.Popen(
                ["xdg-open", str(path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=proc.env(),
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

        def add_items(target, items):
            for item in items:
                if item.get("type") == "separator":
                    target.addSeparator()
                    continue
                children = item.get("children")
                if children:
                    sub = QMenu(item.get("label", ""))
                    add_items(sub, children)
                    target.addMenu(sub)
                    continue
                action = QAction(item.get("label", ""))
                callback = item.get("callback")
                if callback:
                    action.triggered.connect(callback)
                else:
                    action.setEnabled(False)
                target.addAction(action)

        add_items(menu, self._build_menu_items())

    def _show_tray_menu(self, x=0, y=0):
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
        if self._launcher is not None:
            self._launcher.hide()
        self.start_capture()

    def _start_from_launcher(self, mode):
        self._start_capture_mode(mode)
        # Set after start_capture() resets it — only launcher-origin cancels
        # restore the launcher.
        self._from_launcher = True

    def _on_cancel(self):
        self._capturing = False
        if self._from_launcher:
            self._from_launcher = False
            QTimer.singleShot(0, self._show_launcher)

    def _do_capture(self, pixmap):
        old = getattr(self, "preview", None)
        if old is not None:
            old.close()
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

    def _on_selector_error(self, message):
        self._capturing = False
        QMessageBox.warning(None, "Window capture", message)

    def _on_selector_pixmap(self, pixmap):
        self._capturing = False
        self._do_capture(pixmap)

    def _do_delayed_capture(self, delay, capture_fn):
        if delay > 0:
            self._capturing = True
            self._cd = CountdownOverlay(seconds=delay)
            self._cd.finished.connect(lambda: self._do_capture_async(capture_fn))
            self._cd.cancelled.connect(self._on_countdown_cancelled)
            self._cd.show()
        else:
            self._do_capture_async(capture_fn)

    def _on_countdown_cancelled(self):
        self._capturing = False

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
        self._from_launcher = False  # any direct entry (keybind/IPC/tray) clears launcher origin
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
            self.selector.pixmap_captured.connect(self._on_selector_pixmap)
            self.selector.error.connect(self._on_selector_error)
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


_HELP = f"""ChamelShot {VERSION} - screenshot capture tool for Wayland (wlroots)

Usage:
  chamelshot [options]

Options:
  -c, --capture          Capture using the configured mode (region/window/fullscreen)
      --settings         Open the settings dialog
      --test-tray        Start normally, then pop the tray menu after ~1.5s
      --open-history     Open the history folder
      --history          Open the history browser
      --install-autostart  Install an autostart entry (runs at login)
      --remove-autostart Remove the autostart entry
  -v, --version          Print version and exit
  -h, --help             Show this help and exit
"""


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(_HELP, end="")
        return

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
    elif "--history" in sys.argv:
        cmd = "open-history-ui"
    elif "--open-history" in sys.argv:
        cmd = "open-history"

    if ipc.send_command(cfg.IPC_SOCKET_PATH, "ping"):
        ipc.send_command(cfg.IPC_SOCKET_PATH, cmd)
        print(f"chamelshot: forwarded '{cmd}' to running instance")
        return

    ipc.clean_stale_socket(cfg.IPC_SOCKET_PATH)

    if "--settings" in sys.argv:
        _load_gui()
        app = QApplication(sys.argv)
        dlg = SettingsDialog()
        dlg.exec()
        return

    auto_capture = "--capture" in sys.argv or "-c" in sys.argv
    _load_gui()
    try:
        app = ChamelShotApp(auto_capture=auto_capture)
    except ipc.AlreadyRunningError:
        print("chamelshot: another instance started concurrently; exiting")
        return

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
