# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Unit tests for the pin lifecycle state model (pin.py).

PinStore is Qt-free by design (opaque handles), so no QApplication is needed;
the two widget tests at the bottom exercise the PinWindow chrome (border +
resize grip) under an offscreen QApplication.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import pin as pin_mod
from pin import PinStore


def test_add_returns_incremental_ids():
    store = PinStore()
    assert store.add("a") == 0
    assert store.add("b") == 1
    assert store.count() == 2


def test_remove_only_removes_matching_id():
    store = PinStore()
    first = store.add("a")
    second = store.add("b")
    assert store.remove(first) is True
    assert store.count() == 1
    assert store.remove(first) is False
    assert store.remove(second) is True
    assert store.count() == 0


def test_close_all_clears_and_returns_handles():
    store = PinStore()
    store.add("x")
    store.add("y")
    closed = store.close_all()
    assert sorted(closed) == ["x", "y"]
    assert store.count() == 0
    # closing an already-closed store is a no-op
    assert store.close_all() == []


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _make_pin(qapp) -> pin_mod.PinWindow:
    from PySide6.QtGui import QPixmap

    store = PinStore()
    pm = QPixmap(200, 120)
    pm.fill(0x112233)
    pin = pin_mod.PinWindow(pm, store)
    pin.show()
    qapp.processEvents()
    return pin


def test_pin_window_has_border_for_dark_wallpapers(qapp):
    pin = _make_pin(qapp)
    assert pin.objectName() == "pinRoot"
    sheet = pin.styleSheet()
    assert "border" in sheet and "pinRoot" in sheet
    pin.close()


def test_pin_window_has_resize_grip_in_bottom_right(qapp):
    pin = _make_pin(qapp)
    grip = pin.size_grip
    assert grip is not None
    assert grip.isVisible()
    g = grip.geometry()
    assert g.right() <= pin.width()
    assert g.bottom() <= pin.height()
    assert g.right() >= pin.width() - 32
    assert g.bottom() >= pin.height() - 32
    pin.close()
