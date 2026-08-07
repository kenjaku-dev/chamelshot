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
import time
from pathlib import Path
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

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


def test_refresh_prepends_new_capture_keeps_selection(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "HISTORY_DIR", tmp_path)
    _seed(tmp_path, ["screenshot_20260805_120000_000.png"])
    dlg = hst.HistoryDialog()
    dlg.show()
    qapp.processEvents()
    _seed(tmp_path, ["screenshot_20260805_150000_000.png"])
    dlg._refresh()
    qapp.processEvents()
    assert dlg.list.count() == 2
    assert dlg.list.item(0).data(hst.Qt.ItemDataRole.UserRole).name == "screenshot_20260805_150000_000.png"
    cur = dlg.list.currentItem()
    assert cur.data(hst.Qt.ItemDataRole.UserRole).name == "screenshot_20260805_120000_000.png"
    dlg.close()


def test_refresh_removes_deleted_entry(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "HISTORY_DIR", tmp_path)
    _seed(tmp_path, ["screenshot_20260805_120000_000.png", "screenshot_20260805_150000_000.png"])
    dlg = hst.HistoryDialog()
    dlg.show()
    qapp.processEvents()
    assert dlg.list.count() == 2
    (tmp_path / "screenshot_20260805_150000_000.png").unlink()
    dlg._refresh()
    qapp.processEvents()
    assert dlg.list.count() == 1
    assert dlg.list.currentItem().data(hst.Qt.ItemDataRole.UserRole).name == "screenshot_20260805_120000_000.png"
    dlg.close()


def test_refresh_placeholder_round_trip(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "HISTORY_DIR", tmp_path)
    dlg = hst.HistoryDialog()
    dlg.show()
    qapp.processEvents()
    assert dlg.list.count() == 1
    assert dlg.list.item(0).flags() == hst.Qt.ItemFlag.NoItemFlags
    _seed(tmp_path, ["screenshot_20260805_120000_000.png"])
    dlg._refresh()
    qapp.processEvents()
    assert dlg.list.count() == 1
    assert dlg.list.currentItem() is not None
    (tmp_path / "screenshot_20260805_120000_000.png").unlink()
    dlg._refresh()
    qapp.processEvents()
    assert dlg.list.count() == 1
    assert dlg.list.item(0).flags() == hst.Qt.ItemFlag.NoItemFlags
    dlg.close()


def test_watch_active_only_while_visible(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "HISTORY_DIR", tmp_path)
    dlg = hst.HistoryDialog()
    assert not dlg._watcher.directories()
    dlg.show()
    qapp.processEvents()
    assert dlg._watcher.directories() == [str(tmp_path)]
    assert not dlg._fallback.isActive()
    dlg.hide()
    qapp.processEvents()
    assert not dlg._watcher.directories()
    dlg.close()


def _qwait_until(app, condition, timeout_s=3.0) -> bool:
    from PySide6.QtTest import QTest

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if condition():
            return True
        QTest.qWait(20)
    return condition()


def test_new_capture_appears_via_watcher(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "HISTORY_DIR", tmp_path)
    _seed(tmp_path, ["screenshot_20260805_120000_000.png"])
    dlg = hst.HistoryDialog()
    dlg.show()
    qapp.processEvents()
    assert dlg.list.count() == 1
    _seed(tmp_path, ["screenshot_20260805_150000_000.png"])
    assert _qwait_until(qapp, lambda: dlg.list.count() == 2)
    assert dlg.list.item(0).data(hst.Qt.ItemDataRole.UserRole).name == "screenshot_20260805_150000_000.png"
    dlg.close()


def test_external_delete_updates_list_via_watcher(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "HISTORY_DIR", tmp_path)
    _seed(tmp_path, ["screenshot_20260805_120000_000.png", "screenshot_20260805_150000_000.png"])
    dlg = hst.HistoryDialog()
    dlg.show()
    qapp.processEvents()
    assert dlg.list.count() == 2
    (tmp_path / "screenshot_20260805_150000_000.png").unlink()
    assert _qwait_until(qapp, lambda: dlg.list.count() == 1)
    assert dlg.list.item(0).data(hst.Qt.ItemDataRole.UserRole).name == "screenshot_20260805_120000_000.png"
    dlg.close()


def test_watcher_keeps_selection_after_external_add(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "HISTORY_DIR", tmp_path)
    _seed(tmp_path, ["screenshot_20260805_120000_000.png", "screenshot_20260805_140000_000.png"])
    dlg = hst.HistoryDialog()
    dlg.show()
    qapp.processEvents()
    dlg.list.setCurrentRow(0)
    _seed(tmp_path, ["screenshot_20260805_150000_000.png"])
    assert _qwait_until(qapp, lambda: dlg.list.count() == 3)
    assert dlg.list.currentItem().data(hst.Qt.ItemDataRole.UserRole).name == "screenshot_20260805_140000_000.png"
    dlg.close()


def test_fallback_polls_until_dir_exists_then_watches(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "HISTORY_DIR", tmp_path / "nope")
    dlg = hst.HistoryDialog()
    dlg.show()
    qapp.processEvents()
    assert not dlg._watcher.directories()
    assert dlg._fallback.isActive()
    hist_dir = tmp_path / "nope"
    hist_dir.mkdir()
    _seed(hist_dir, ["screenshot_20260805_120000_000.png"])
    assert _qwait_until(
        qapp,
        lambda: dlg.list.count() == 1 and dlg.list.item(0).data(hst.Qt.ItemDataRole.UserRole) is not None,
        timeout_s=4.0,
    )
    assert dlg._watcher.directories() == [str(hist_dir)]
    assert not dlg._fallback.isActive()
    dlg.close()


def test_thumb_placeholder_icon_is_replaced_by_scaled_image(qapp, tmp_path, monkeypatch):
    from PySide6.QtGui import QImage

    png = tmp_path / "screenshot_20260805_120000_000.png"
    QImage(640, 480, QImage.Format.Format_RGB32).save(str(png))

    def fake_run_async(_receiver, work, on_ok=None, on_error=None):
        if on_ok:
            on_ok(work())

    monkeypatch.setattr(cfg, "HISTORY_DIR", tmp_path)
    monkeypatch.setattr(hst, "run_async", fake_run_async)
    dlg = hst.HistoryDialog()
    qapp.processEvents()
    assert dlg.list.count() == 1
    pm = dlg.list.item(0).icon().pixmap(160, 160)
    assert (pm.width(), pm.height()) == (160, 120)
    dlg.close()


def test_thumb_async_skips_detached_item(qapp, tmp_path, monkeypatch):
    from PySide6.QtGui import QImage

    png = tmp_path / "screenshot_20260805_120000_000.png"
    QImage(640, 480, QImage.Format.Format_RGB32).save(str(png))

    def fake_run_async(_receiver, work, on_ok=None, on_error=None):
        img = work()
        if on_ok:
            on_ok(img)

    monkeypatch.setattr(cfg, "HISTORY_DIR", tmp_path)
    monkeypatch.setattr(hst, "run_async", fake_run_async)
    dlg = hst.HistoryDialog()
    item = dlg.list.item(0)
    dlg.list.takeItem(0)
    assert item.listWidget() is None
    dlg._load_thumb_async(item, png)  # must no-op, not crash
    qapp.processEvents()
    dlg.close()
