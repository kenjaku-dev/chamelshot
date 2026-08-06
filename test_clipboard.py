# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Tests for the shared clipboard helpers (clipboard.py).

The Qt-clipboard branch needs a live QApplication, so these drive the wl-copy
path with a stubbed shutil.which/subprocess.run. setPixmap is never reached
when the tool is wl-copy-only.
"""

from unittest.mock import MagicMock

import clipboard as clip


def test_copy_pixmap_wl_only_with_primary(monkeypatch):
    pm = MagicMock()
    pm.save.return_value = True
    monkeypatch.setattr(clip.shutil, "which", lambda name: True)
    run = MagicMock()
    monkeypatch.setattr(clip.subprocess, "run", run)

    clip.copy_pixmap(pm, {"clipboard.tool": "wl-copy"}, primary=True)

    calls = [c.args[0] for c in run.call_args_list]
    assert ["wl-copy", "--type", "image/png", "--primary"] in calls
    assert ["wl-copy", "--type", "image/png"] in calls


def test_copy_pixmap_wl_only_plain(monkeypatch):
    pm = MagicMock()
    pm.save.return_value = True
    monkeypatch.setattr(clip.shutil, "which", lambda name: True)
    run = MagicMock()
    monkeypatch.setattr(clip.subprocess, "run", run)

    clip.copy_pixmap(pm, {"clipboard.tool": "wl-copy"})

    calls = [c.args[0] for c in run.call_args_list]
    assert calls == [["wl-copy", "--type", "image/png"]]


def test_copy_pixmap_reuses_provided_png_bytes(monkeypatch):
    pm = MagicMock()
    monkeypatch.setattr(clip.shutil, "which", lambda name: True)
    run = MagicMock()
    monkeypatch.setattr(clip.subprocess, "run", run)

    clip.copy_pixmap(pm, {"clipboard.tool": "wl-copy"}, png=b"\x00\x01")

    assert pm.save.call_count == 0
    assert run.call_args_list[0].kwargs["input"] == b"\x00\x01"


def test_copy_pixmap_no_wl_copy_when_missing(monkeypatch):
    pm = MagicMock()
    monkeypatch.setattr(clip.shutil, "which", lambda name: False)
    run = MagicMock()
    monkeypatch.setattr(clip.subprocess, "run", run)

    clip.copy_pixmap(pm, {"clipboard.tool": "wl-copy"})

    assert run.call_count == 0


def test_wl_copy_supported_false_without_tool_or_binary(monkeypatch):
    monkeypatch.setattr(clip.shutil, "which", lambda name: None)
    assert clip.wl_copy_supported({"clipboard.tool": "qt"}) is False
    assert clip.wl_copy_supported({"clipboard.tool": "both"}) is False
    monkeypatch.setattr(clip.shutil, "which", lambda name: True)
    assert clip.wl_copy_supported({"clipboard.tool": "both"}) is True
