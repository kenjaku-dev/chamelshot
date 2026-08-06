# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""History browser dialog: thumbnail grid of recent screenshots.

Wired like settings.py (a QDialog built up front; the daemon opens it from
the tray / IPC). Actions per thumbnail: re-edit (opens PreviewWindow), copy
to clipboard, open the history folder, delete. Keyboard-first: arrows
navigate the grid, Enter re-edits, C copies, Del deletes, Esc closes.
"""

import subprocess
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

import clipboard as clip
import config as cfg
import proc

_HISTORY_GLOB = "screenshot_*.png"
_MAX_THUMBS = 10
_THUMB_SIZE = 160

_STYLE = """
    QWidget { background: #161617; color: #d4d4d8; }
    QListWidget {
        background: #1f1f22; border: 1px solid #2e2e32; border-radius: 6px;
        padding: 4px;
    }
    QLabel#hint { color: #71717a; font-size: 11px; }
    QPushButton {
        background: #1f1f22; color: #e4e4e7;
        border: 1px solid #2e2e32; border-radius: 6px;
        padding: 6px 14px; font-size: 13px;
    }
    QPushButton:hover { background: #2563eb; border-color: #2563eb; color: #fff; }
    QPushButton:pressed { background: #1d4ed8; }
"""


class HistoryDialog(QDialog):
    def __init__(self, parent=None, config=None, on_edit=None):
        super().__init__(parent)
        self.setWindowTitle("ChamelShot - History")
        self.setMinimumSize(640, 480)
        self.setStyleSheet(_STYLE)
        self.cfg = config or cfg.load()
        self.on_edit = on_edit or self._default_edit
        self._entries: list[Path] = []
        self._build_ui()
        self._refresh()

    # --------------------------------------------------------------- UI

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.list = QListWidget(self)
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(QSize(_THUMB_SIZE, _THUMB_SIZE))
        self.list.setGridSize(QSize(_THUMB_SIZE + 24, _THUMB_SIZE + 52))
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list.setSpacing(8)
        self.list.setWordWrap(True)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_context_menu)
        self.list.itemActivated.connect(self._on_activated)
        self.list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self.list, 1)

        self.hint = QLabel("Enter: re-edit  ·  C: copy  ·  Del: delete  ·  Esc: close")
        self.hint.setObjectName("hint")
        layout.addWidget(self.hint)

        btn_row = QHBoxLayout()
        btn_open = QPushButton("Open Folder")
        btn_open.clicked.connect(self._open_folder)
        btn_row.addWidget(btn_open)
        btn_row.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        QShortcut(QKeySequence("Return"), self).activated.connect(self._activate_current)
        QShortcut(QKeySequence("C"), self).activated.connect(self._copy_current)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self._delete_current)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.reject)

    def _open_folder(self):
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

    # ----------------------------------------------------------- data

    def _entries_sorted(self) -> list[Path]:
        hist = cfg.HISTORY_DIR
        if not hist.is_dir():
            return []
        return sorted(hist.glob(_HISTORY_GLOB), reverse=True)[:_MAX_THUMBS]

    def _refresh(self):
        self.list.clear()
        self._entries = self._entries_sorted()
        for path in self._entries:
            item = self._make_item(path)
            self.list.addItem(item)
        if not self._entries:
            empty = QListWidgetItem("No screenshots yet — capture something first")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(empty)
            self.setWindowTitle("ChamelShot - History (empty)")
        else:
            self.setWindowTitle("ChamelShot - History")
            # Only select a real entry; the NoItemFlags placeholder above must
            # never become the current item or Enter/C/Del hit a dead row.
            self.list.setCurrentItem(self.list.item(0))

    def _make_item(self, path: Path) -> QListWidgetItem:
        pm = QPixmap(str(path))
        if not pm.isNull():
            long_side = max(pm.width(), pm.height())
            if long_side > _THUMB_SIZE:
                pm = pm.scaled(
                    _THUMB_SIZE,
                    _THUMB_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        else:
            pm = QPixmap(_THUMB_SIZE, _THUMB_SIZE)
            pm.fill(QColor("#161617"))
        item = QListWidgetItem(QIcon(pm), path.stem.removeprefix("screenshot_").replace("_", " ")[:19])
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setToolTip(str(path))
        return item

    def _current_path(self) -> Path | None:
        item = self.list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    # ----------------------------------------------------------- actions

    def _default_edit(self, path: Path):
        QMessageBox.warning(self, "Re-edit", f"No editor configured for:\n{path}")

    def _on_activated(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path is not None:
            self.on_edit(path)

    def _activate_current(self):
        item = self.list.currentItem()
        if item is not None:
            self._on_activated(item)

    def _copy_current(self):
        path = self._current_path()
        if path is None:
            return
        self._do_copy(path)

    def _delete_current(self):
        path = self._current_path()
        if path is None:
            return
        self._delete_path(path)

    def _delete_path(self, path: Path):
        if not path.exists():
            self._refresh()
            return
        try:
            path.unlink()
        except OSError as e:
            QMessageBox.warning(self, "Delete", f"Could not delete:\n{path}\n{e}")
        self._refresh()

    def _do_copy(self, path: Path):
        pm = QPixmap(str(path))
        if pm.isNull():
            QMessageBox.warning(self, "Copy", f"Could not load image:\n{path}")
            return
        try:
            png = path.read_bytes()
        except OSError:
            png = None
        try:
            clip.copy_pixmap(pm, self.cfg, png=png)
        except OSError:
            pass

    def _on_context_menu(self, pos):
        spec = self.list.itemAt(pos)
        if spec is None:
            return
        path = spec.data(Qt.ItemDataRole.UserRole)
        if path is None:
            return
        menu = QMenu(self)
        act_edit = menu.addAction("Re-edit")
        act_open = menu.addAction("Open")
        act_copy = menu.addAction("Copy to clipboard")
        act_delete = menu.addAction("Delete")
        chosen = menu.exec(self.list.mapToGlobal(pos))
        if chosen is act_edit:
            self.on_edit(path)
        elif chosen is act_open:
            try:
                subprocess.Popen(["xdg-open", str(path)], stdin=subprocess.DEVNULL)
            except FileNotFoundError:
                pass
        elif chosen is act_copy:
            self._do_copy(path)
        elif chosen is act_delete:
            self._delete_path(path)
