# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Launcher widget geometry (E1): buttons must not be compressed.

Regression for the fixed 280x290 window clipping every action button: the
layout hint (333px) exceeded the hardcoded height, so Qt squished the buttons
below their text height. Now the height is derived from the layout, so each
button must render at full sizeHint size and fully inside the window.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

import main as main_mod


@pytest.fixture(scope="module")
def qapp():
    main_mod._load_gui()
    return QApplication.instance() or QApplication([])


def _build_launcher(qapp):
    app = main_mod.ChamelShotApp.__new__(main_mod.ChamelShotApp)
    app._launcher = None
    app._start_from_launcher = lambda mode: None
    app._show_launcher()
    launcher = app._launcher
    assert launcher is not None
    launcher.show()
    qapp.processEvents()
    return launcher


def _launcher_widgets(launcher) -> list[QWidget]:
    return [w for w in launcher.children() if isinstance(w, QWidget)]


def test_launcher_buttons_not_compressed(qapp):
    launcher = _build_launcher(qapp)
    buttons = [w for w in _launcher_widgets(launcher) if isinstance(w, QPushButton)]
    assert buttons
    for btn in buttons:
        hint_w, hint_h = btn.sizeHint().width(), btn.sizeHint().height()
        assert btn.height() >= hint_h, f"{btn.text()!r} height {btn.height()} < hint {hint_h}"
        assert btn.width() >= hint_w, f"{btn.text()!r} width {btn.width()} < hint {hint_w}"


def test_launcher_contents_inside_window(qapp):
    launcher = _build_launcher(qapp)
    rect = launcher.rect()
    for child in _launcher_widgets(launcher):
        if child.geometry().width() == 0 or child.geometry().height() == 0:
            continue
        geo = child.geometry()
        assert geo.left() >= rect.left(), f"{child} sticks out past the left edge"
        assert geo.top() >= rect.top(), f"{child} sticks out past the top edge"
        assert geo.right() <= rect.right(), f"{child} sticks out past the right edge"
        assert geo.bottom() <= rect.bottom(), f"{child} sticks out past the bottom edge"
