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
from typing import override

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImage, QKeySequence, QPixmap, QShortcut
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
import theme as t
from dispatcher import run_async

_HISTORY_GLOB = "screenshot_*.png"
_MAX_THUMBS = 10
_THUMB_SIZE = 160

_STYLE = f"""
    QWidget {{ background: {t.BG}; color: {t.TEXT_BODY}; }}
    QListWidget {{
        background: {t.PANEL}; border: 1px solid {t.BORDER}; border-radius: {t.RADIUS};
        padding: 4px;
    }}
    QLabel#hint {{ color: {t.TEXT_MUTED}; font-size: 11px; }}
    QPushButton {{
        background: {t.PANEL}; color: {t.TEXT};
        border: 1px solid {t.BORDER}; border-radius: {t.RADIUS};
        padding: 6px 14px; font-size: 13px;
    }}
    QPushButton:hover {{ background: {t.ACCENT}; border-color: {t.ACCENT}; color: {t.TEXT_WHITE}; }}
    QPushButton:pressed {{ background: {t.ACCENT_PRESSED}; }}
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
        # Poll while visible so captures taken while the daemon runs show up
        # without reopening; started/stopped in the show/hide events below.
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._refresh)

    @override
    def showEvent(self, event):
        super().showEvent(event)
        self._refresh()
        self._timer.start()

    @override
    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

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
        """Sync the list to the history folder, minimizing UI churn.

        Newest-first order only ever gains new captures at the front and loses
        deleted ones, so we prepend/remove instead of clearing: no flicker and
        the scroll position is preserved. Returns early when nothing changed
        (e.g. a timer tick with no new capture).
        """
        entries = self._entries_sorted()
        rendered = [
            self.list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.list.count())
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) is not None
        ]
        has_placeholder = self._placeholder_item() is not None
        if rendered == entries and has_placeholder == (not entries):
            return
        self._entries = entries
        self._sync_items(entries)
        ph = self._placeholder_item()
        if self._entries:
            if ph is not None:
                self.list.takeItem(self.list.row(ph))
            self.setWindowTitle("ChamelShot - History")
            current = self._current_path()
            if current in self._entries:
                self._select_path(current)
            else:
                self._select_path(self._entries[0])
        else:
            if ph is None:
                empty = QListWidgetItem("No screenshots yet — capture something first")
                empty.setFlags(Qt.ItemFlag.NoItemFlags)
                self.list.addItem(empty)
            self.setWindowTitle("ChamelShot - History (empty)")
            self.list.setCurrentRow(-1)

    def _sync_items(self, entries: list[Path]):
        """Minimal list surgery: remove vanished entries, prepend new ones."""
        taken = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            path = it.data(Qt.ItemDataRole.UserRole)
            if path is not None and path not in entries:
                taken.append(it)
        for it in taken:
            self.list.takeItem(self.list.row(it))
        have = {self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())}
        for pos, path in enumerate(entries):
            if path not in have:
                item = self._make_item(path)
                self.list.insertItem(pos, item)
                # Load the thumbnail only once the item is attached, so the
                # async callback's ownership check sees a live list widget.
                self._load_thumb_async(item, path)

    def _placeholder_item(self) -> QListWidgetItem | None:
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) is None:
                return it
        return None

    def _select_path(self, path: Path):
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == path:
                self.list.setCurrentItem(self.list.item(i))
                return

    @staticmethod
    def _blank_pixmap() -> QPixmap:
        pm = QPixmap(_THUMB_SIZE, _THUMB_SIZE)
        pm.fill(QColor(t.BG))
        return pm

    def _make_item(self, path: Path) -> QListWidgetItem:
        item = QListWidgetItem(
            QIcon(self._blank_pixmap()), path.stem.removeprefix("screenshot_").replace("_", " ")[:19]
        )
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setToolTip(str(path))
        return item

    def _load_thumb_async(self, item: QListWidgetItem, path: Path):
        """Load the thumbnail off the UI thread to keep the dialog responsive.

        QImage is safe to load in a worker thread; the result comes back on the
        main thread via dispatcher and only matters if the item is still in the
        list (a refresh may have removed it while the load was in flight).
        """

        def work():
            img = QImage(str(path))
            if img.isNull():
                return None
            if max(img.width(), img.height()) > _THUMB_SIZE:
                img = img.scaled(
                    _THUMB_SIZE,
                    _THUMB_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            return img

        def done(img):
            if img is not None and item.listWidget() is self.list:
                item.setIcon(QIcon(QPixmap.fromImage(img)))

        run_async(self, work, done, on_error=lambda e: None)

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
