# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Unit tests for the pin lifecycle state model (pin.py).

PinStore is Qt-free by design (opaque handles), so no QApplication is needed.
"""

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
