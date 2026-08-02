# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Unit tests for the tray menu item list and launcher behavior (main.py).

No Qt/dbus needed: `_build_menu_items` is a pure list builder, and
`_start_capture_mode` only touches `self._launcher.hide()` + `start_capture()`.
"""

from typing import Any, cast
from unittest.mock import MagicMock

import config as cfg
from main import ChamelShotApp


class _FakeLauncher:
    def __init__(self):
        self.hidden = False

    def hide(self):
        self.hidden = True


def _app(tmp_path, monkeypatch) -> Any:
    monkeypatch.setattr(cfg, "HISTORY_DIR", tmp_path)
    app = cast(Any, object.__new__(ChamelShotApp))
    app._launcher = None
    app.settings = dict(cfg.load())
    app.start_capture = MagicMock()
    app._open_history_folder = MagicMock()
    app._open_settings = MagicMock()
    app.app = MagicMock()
    return app


def test_menu_starts_with_show_interface(tmp_path, monkeypatch):
    items = _app(tmp_path, monkeypatch)._build_menu_items()
    first = items[0]
    assert first["label"] == "  \u25a6  Show Interface"
    assert callable(first["callback"])
    assert first.get("type") != "separator"


def test_menu_show_interface_is_separated_from_captures(tmp_path, monkeypatch):
    items = _app(tmp_path, monkeypatch)._build_menu_items()
    assert items[0]["label"] == "  \u25a6  Show Interface"
    assert items[1]["type"] == "separator"
    assert items[2]["label"] == "  \u25fb  Capture Region"


def test_menu_show_interface_callback_opens_launcher(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    app._show_launcher = MagicMock()
    item = app._build_menu_items()[0]
    item["callback"]()
    app._show_launcher.assert_called_once()


def test_menu_capture_items_preserved(tmp_path, monkeypatch):
    labels = [i["label"] for i in _app(tmp_path, monkeypatch)._build_menu_items() if i.get("type") != "separator"]
    assert "  \u25fb  Capture Region" in labels
    assert "  \u25ad  Capture Window" in labels
    assert "  \u229e  Capture Fullscreen" in labels
    assert "  \u2699  Settings" in labels
    assert "  \u2715  Kill" in labels


def test_start_capture_hides_launcher(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    launcher = _FakeLauncher()
    app._launcher = launcher
    app._start_capture_mode("region")
    assert launcher.hidden
    app.start_capture.assert_called_once()


def test_start_capture_without_launcher_ok(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    app._start_capture_mode("fullscreen")
    app.start_capture.assert_called_once()


def test_start_from_launcher_delegates(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    app._launcher = _FakeLauncher()
    app._start_from_launcher("window")
    assert app.settings["capture.mode"] == "window"
    app.start_capture.assert_called_once()
