# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Unit tests for the history browser dialog logic (history.py).

Data/action methods run on a bare instance via object.__new__ (no Qt,
matching test_preview.py's pattern); the two selection tests at the bottom
use a real dialog under an offscreen QApplication.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import config as cfg
import history as hst


def _bare_dialog(config: dict | None = None) -> hst.HistoryDialog:
    d = hst.HistoryDialog.__new__(hst.HistoryDialog)
    d.cfg = config or {}
    return d


def _seed(tmp_path: Path, names: list[str]) -> list[Path]:
    for name in names:
        (tmp_path / name).write_bytes(b"png")
    return [tmp_path / n for n in names]


def test_entries_sorted_newest_first_capped(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "HISTORY_DIR", tmp_path)
    _seed(tmp_path, [f"screenshot_20260805_15000{i}.png" for i in range(3)])
    _seed(tmp_path, ["notes.txt", "screenshot.png"])
    d = _bare_dialog()
    entries = d._entries_sorted()
    assert len(entries) == 3
    assert entries[0].name > entries[-1].name
    assert all(e.name.startswith("screenshot_") for e in entries)


def test_entries_sorted_missing_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "HISTORY_DIR", tmp_path / "nope")
    assert _bare_dialog()._entries_sorted() == []


def test_delete_path_removes_file_and_refreshes(tmp_path):
    d = _bare_dialog()
    d._refresh = MagicMock()
    target, keeper = _seed(tmp_path, ["screenshot_20260801_1.png", "screenshot_20260801_2.png"])
    d._delete_path(target)
    assert not target.exists()
    assert keeper.exists()
    d._refresh.assert_called_once()


def test_delete_path_missing_refreshes_without_error(tmp_path):
    d = _bare_dialog()
    d._refresh = MagicMock()
    d._delete_path(tmp_path / "ghost.png")
    d._refresh.assert_called_once()


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_empty_history_selects_no_item(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "HISTORY_DIR", tmp_path)
    dlg = hst.HistoryDialog()
    dlg.show()
    qapp.processEvents()
    assert dlg.list.count() == 1
    assert dlg.list.item(0).flags() == hst.Qt.ItemFlag.NoItemFlags
    assert dlg.list.currentItem() is None
    dlg.close()


def test_nonempty_history_selects_newest_item(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "HISTORY_DIR", tmp_path)
    _seed(tmp_path, ["screenshot_20260805_120000_000.png", "screenshot_20260805_150000_000.png"])
    dlg = hst.HistoryDialog()
    dlg.show()
    qapp.processEvents()
    cur = dlg.list.currentItem()
    assert cur is not None
    path = cur.data(hst.Qt.ItemDataRole.UserRole)
    assert path.name == "screenshot_20260805_150000_000.png"
    dlg.close()
