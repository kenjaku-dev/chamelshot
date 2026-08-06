# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Pure-math unit tests for the annotator (editor.py).

The annotator paints Qt objects, so pixel ops are untestable without a
QApplication; the crop/eraser geometry is extracted into pure helpers and
tested here. No Qt/dbus needed.
"""

from editor import (
    clamp_rect_to_source,
    crop_from_points,
    normalize_rect,
)


def test_normalize_rect_orders_corners():
    assert normalize_rect(50, 30, 10, 60) == (10, 30, 50, 60)


def test_normalize_rect_keeps_already_ordered():
    assert normalize_rect(1, 2, 3, 4) == (1, 2, 3, 4)


def test_clamp_rect_to_source_clips_negative():
    assert clamp_rect_to_source(-5, -5, 100, 100, 50, 40) == (0, 0, 50, 40)


def test_clamp_rect_to_source_clips_overflow():
    assert clamp_rect_to_source(0, 0, 200, 200, 100, 80) == (0, 0, 100, 80)


def test_clamp_rect_fully_outside_returns_none():
    assert clamp_rect_to_source(60, 60, 80, 80, 50, 50) is None


def test_crop_from_points_uses_corners():
    assert crop_from_points([(40, 40), (10, 10)], 100, 100) == (10, 10, 40, 40)


def test_crop_from_points_needs_two_points():
    assert crop_from_points([(10, 10)], 100, 100) is None


def test_crop_from_points_empty_returns_none():
    assert crop_from_points([], 100, 100) is None


def test_crop_from_points_clamped_to_source():
    assert crop_from_points([(-20, -20), (200, 200)], 100, 80) == (0, 0, 100, 80)


def test_eraser_points_thinned_above_minimum_distance():
    from editor import thin_points

    assert thin_points([(0, 0), (0, 0)], 2.0) == [(0, 0)]
    assert thin_points([(0, 0), (0, 1), (0, 1), (0, 5)], 2.0) == [(0, 0), (0, 5)]
    assert len(thin_points([(0, 0), (5, 5), (10, 10)], 2.0)) == 3
