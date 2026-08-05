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
