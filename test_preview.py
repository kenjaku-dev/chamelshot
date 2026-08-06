# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Tests for PreviewWindow save-dialog defaults (preview.py).

Regression for BUG#24-adjacent: the plain "Save" dialog used to hardcode
~/chamelshot.png instead of the configured save.directory + filename_format.
These tests avoid constructing a real PreviewWindow (needs QApplication); they
drive `save()` on a bare instance via object.__new__.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import clipboard as clip
import preview as prv


def _bare_preview(config: dict) -> prv.PreviewWindow:
    w = prv.PreviewWindow.__new__(prv.PreviewWindow)
    w.cfg = config
    return w


def test_save_dialog_defaults_to_configured_dir_and_format():
    config = {
        "save.directory": "/tmp/chamelshot-test/shots",
        "save.filename_format": "cap_%Y%m%d_%H%M%S.png",
        "save.format": "PNG",
        "save.quality": -1,
    }
    w = _bare_preview(config)
    with patch("preview.QFileDialog.getSaveFileName", MagicMock(return_value=("", ""))) as mock_dialog:
        w.save()
    default_path = mock_dialog.call_args.args[2]
    assert default_path.startswith("/tmp/chamelshot-test/shots/cap_")
    assert default_path.endswith(".png")
    assert "chamelshot-test" in default_path


def test_save_dialog_filter_matches_configured_format():
    config = {
        "save.directory": "/tmp/shots",
        "save.filename_format": "shot.png",
        "save.format": "WebP",
        "save.quality": -1,
    }
    w = _bare_preview(config)
    with patch("preview.QFileDialog.getSaveFileName", MagicMock(return_value=("", ""))) as mock_dialog:
        w.save()
    assert mock_dialog.call_args.args[3] == "WebP (*.webp)"


def test_pin_calls_on_pin_with_current_pixmap():
    w = prv.PreviewWindow.__new__(prv.PreviewWindow)
    w.cfg = {}
    w.pin_store = None
    w.on_pin = None
    w._current_pixmap = MagicMock()
    w._current_pixmap.return_value = "pixmap"
    received = {}
    w.on_pin = lambda pm: received.update(pm=pm)
    w._pin()
    assert received == {"pm": "pixmap"}


def test_wl_copy_argv_plain():
    assert clip.wl_copy_argv(False) == ["wl-copy", "--type", "image/png"]


def test_wl_copy_argv_primary():
    assert clip.wl_copy_argv(True) == ["wl-copy", "--type", "image/png", "--primary"]


def test_copy_to_clipboard_primary_feeds_primary_selection(tmp_path, monkeypatch):
    monkeypatch.setattr(prv.cfg, "HISTORY_DIR", tmp_path)
    w = prv.PreviewWindow.__new__(prv.PreviewWindow)
    w.cfg = {"clipboard.tool": "wl-copy"}
    fake_img = MagicMock()
    fake_img.save.return_value = True
    w._current_image = MagicMock(return_value=fake_img)
    w._notify = MagicMock()

    runs = []

    def fake_run_async(receiver, work, on_ok=None, on_error=None):
        result = work()
        runs.append(result)
        if on_ok:
            on_ok(result)

    monkeypatch.setattr(prv, "run_async", fake_run_async)
    monkeypatch.setattr(clip.shutil, "which", lambda name: True)
    run = MagicMock()
    monkeypatch.setattr(clip.subprocess, "run", run)

    w.copy_to_clipboard(primary=True, closing=False)

    calls = [c.args[0] for c in run.call_args_list]
    assert ["wl-copy", "--type", "image/png", "--primary"] in calls
    assert ["wl-copy", "--type", "image/png"] in calls


def test_copy_to_clipboard_primary_without_wl_copy_warns(tmp_path, monkeypatch):
    monkeypatch.setattr(prv.cfg, "HISTORY_DIR", tmp_path)
    w = prv.PreviewWindow.__new__(prv.PreviewWindow)
    w.cfg = {"clipboard.tool": "qt"}
    w._current_image = MagicMock(return_value=MagicMock())
    w._notify = MagicMock()

    warned = []
    monkeypatch.setattr(prv.QMessageBox, "warning", lambda *a, **k: warned.append(a))
    run = MagicMock()
    monkeypatch.setattr(clip.subprocess, "run", run)

    w.copy_to_clipboard(primary=True, closing=False)

    assert warned, "expected a warning when primary is requested without wl-copy"
    assert run.call_count == 0


def test_open_viewer_writes_temp_file_outside_history(tmp_path, monkeypatch):
    hist_dir = tmp_path / "history"
    monkeypatch.setattr(prv.cfg, "HISTORY_DIR", hist_dir)
    w = _bare_preview({})

    fake_img = MagicMock()
    fake_img.save.return_value = True
    w._current_image = MagicMock(return_value=fake_img)

    saved_to = {}

    def fake_run_async(receiver, work, on_ok=None, on_error=None):
        result = work()
        saved_to["path"] = result
        if on_ok:
            on_ok(result)

    monkeypatch.setattr(prv, "run_async", fake_run_async)
    monkeypatch.setattr(prv.shutil, "which", lambda name: name == "eog")
    popen = MagicMock()
    monkeypatch.setattr(prv.subprocess, "Popen", popen)

    w._open_viewer()

    path = Path(saved_to["path"])
    assert "history" not in str(path).lower()
    assert str(path).startswith(tempfile.gettempdir())
    assert not (hist_dir / "_preview_tmp.png").exists()
    assert hist_dir.exists() is False
    popen.assert_called_once()
    assert popen.call_args.args[0][0] == "eog"


def test_notify_args_plain():
    assert prv._notify_args("Copied to clipboard") == ["notify-send", "ChamelShot", "Copied to clipboard"]


def test_notify_args_with_image():
    args = prv._notify_args("Saved to /tmp/x.png", image="/tmp/x.png", preview=True)
    assert args == ["notify-send", "-i", "/tmp/x.png", "ChamelShot", "Saved to /tmp/x.png"]


def test_notify_args_image_skipped_when_preview_off():
    args = prv._notify_args("Saved to /tmp/x.png", image="/tmp/x.png", preview=False)
    assert args == ["notify-send", "ChamelShot", "Saved to /tmp/x.png"]


def test_notify_sends_image_hint_when_saved(tmp_path, monkeypatch):
    w = prv.PreviewWindow.__new__(prv.PreviewWindow)
    w.cfg = {"general.notification": True, "general.notification_preview": True}
    popen = MagicMock()
    monkeypatch.setattr(prv.subprocess, "Popen", popen)
    w._notify("Saved to /tmp/x.png", image="/tmp/x.png")
    popen.assert_called_once()
    assert popen.call_args.args[0] == ["notify-send", "-i", "/tmp/x.png", "ChamelShot", "Saved to /tmp/x.png"]


def test_notify_skips_image_when_preview_disabled(tmp_path, monkeypatch):
    w = prv.PreviewWindow.__new__(prv.PreviewWindow)
    w.cfg = {"general.notification": True, "general.notification_preview": False}
    popen = MagicMock()
    monkeypatch.setattr(prv.subprocess, "Popen", popen)
    w._notify("Saved to /tmp/x.png", image="/tmp/x.png")
    popen.assert_called_once()
    assert popen.call_args.args[0] == ["notify-send", "ChamelShot", "Saved to /tmp/x.png"]


def test_save_notifies_with_image_hint(tmp_path, monkeypatch):
    w = _bare_preview({"general.notification": True, "general.notification_preview": True})
    w._notify = MagicMock()
    w.close = MagicMock()
    monkeypatch.setattr(prv, "_history_add", lambda path: None)
    fake_img = MagicMock()
    fake_img.save.return_value = True
    saved_to = {}

    def fake_run_async(receiver, work, on_ok=None, on_error=None):
        result = work()
        saved_to["path"] = result
        if on_ok:
            on_ok(result)

    monkeypatch.setattr(prv, "run_async", fake_run_async)
    w._save_async(fake_img, "/tmp/shot.png", "PNG", -1, close=False)
    assert Path(saved_to["path"]) == Path("/tmp/shot.png")
    w._notify.assert_called_once_with("Saved to /tmp/shot.png", image="/tmp/shot.png")
