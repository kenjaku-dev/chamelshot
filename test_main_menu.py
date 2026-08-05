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
import main as main_mod
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
    app._capturing = False
    app._from_launcher = False
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


def test_cancel_from_keybind_does_not_show_launcher(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    app._from_launcher = False
    app._show_launcher = MagicMock()
    fake_timer = MagicMock()
    monkeypatch.setattr(main_mod, "QTimer", fake_timer, raising=False)
    app._on_cancel()
    fake_timer.singleShot.assert_not_called()
    app._show_launcher.assert_not_called()


def test_cancel_from_launcher_restores_launcher_once(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    app._from_launcher = True
    app._show_launcher = MagicMock()
    monkeypatch.setattr(main_mod, "QTimer", MagicMock(), raising=False)
    app._on_cancel()
    main_mod.QTimer.singleShot.assert_called_once()
    main_mod.QTimer.singleShot.call_args.args[1]()
    app._show_launcher.assert_called_once()
    assert app._from_launcher is False


def test_start_capture_resets_launcher_origin(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    app._from_launcher = True
    app._capturing = False
    app.settings["capture.mode"] = "region"
    selector = MagicMock()
    selector_cls = MagicMock(return_value=selector)
    monkeypatch.setattr(main_mod, "RegionSelector", selector_cls, raising=False)
    app.start_capture = ChamelShotApp.start_capture.__get__(app)
    app.start_capture()
    assert app._from_launcher is False
    selector_cls.assert_called_once()


def test_start_from_launcher_marks_origin(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    launcher = _FakeLauncher()
    app._launcher = launcher
    app.settings["capture.mode"] = "region"
    selector = MagicMock()
    selector_cls = MagicMock(return_value=selector)
    monkeypatch.setattr(main_mod, "RegionSelector", selector_cls, raising=False)
    app.start_capture = ChamelShotApp.start_capture.__get__(app)
    app._start_from_launcher("region")
    assert app.settings["capture.mode"] == "region"
    assert launcher.hidden
    assert app._from_launcher is True


def _write_history_shots(dirpath, n):
    for i in range(n):
        p = dirpath / f"screenshot_20260805_12000{i}_000.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 8)


def test_recent_submenu_has_edit_actions(tmp_path, monkeypatch):
    _write_history_shots(tmp_path, 2)
    app = _app(tmp_path, monkeypatch)
    items = app._build_menu_items()
    recents = [i for i in items if "Recent" in i.get("label", "")]
    assert len(recents) == 1
    children = recents[0].get("children", [])
    assert len(children) == 2
    child = children[0]
    assert "[1]" in child["label"]
    actions = child.get("children", [])
    labels = [a["label"].strip() for a in actions]
    assert labels == ["✎  Re-edit", "🗂  Open", "⧉  Copy"]
    assert all(a["callback"] for a in actions)


def test_recent_submenu_no_shots(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    items = app._build_menu_items()
    recents = [i for i in items if "Recent" in i.get("label", "")]
    children = recents[0].get("children", [])
    assert children[0]["label"].strip() == "—  No screenshots"
    assert children[0].get("callback") is None


def test_history_tray_item_registered(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    app._open_history_ui = MagicMock()
    items = app._build_menu_items()
    history_items = [i for i in items if "History Browser" in i.get("label", "")]
    assert len(history_items) == 1
    history_items[0]["callback"]()
