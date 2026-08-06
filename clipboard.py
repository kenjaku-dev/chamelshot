# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Shared clipboard plumbing: Qt clipboard + wl-copy (incl. primary selection)."""

import shutil
import subprocess

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

import proc


def wl_copy_argv(primary: bool = False) -> list[str]:
    """wl-copy argv: [--primary] places the image on the primary selection."""
    args = ["wl-copy", "--type", "image/png"]
    if primary:
        args.append("--primary")
    return args


def wl_copy(png_data: bytes, primary: bool = False) -> None:
    subprocess.run(wl_copy_argv(primary), input=png_data, timeout=5, env=proc.env())


def wl_copy_supported(cfg: dict) -> bool:
    """True when the configured tool can reach wl-copy (needed for primary)."""
    return cfg.get("clipboard.tool", "wl-copy") in ("wl-copy", "both") and bool(shutil.which("wl-copy"))


def _png_bytes(buf: QBuffer) -> bytes | None:
    raw = buf.data().data()
    if raw is None:
        return None
    return bytes(raw)


def pixmap_png(pm: QPixmap) -> bytes | None:
    """PNG bytes for a pixmap, or None when the image cannot be PNG-encoded."""
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.ReadWrite)
    png = _png_bytes(buf) if pm.save(buf, "PNG") else None
    buf.close()
    return png


def image_png(img) -> bytes | None:
    """PNG bytes for a QImage, or None when the image cannot be PNG-encoded."""
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.ReadWrite)
    png = _png_bytes(buf) if img.save(buf, b"PNG") else None
    buf.close()
    return png


def copy_pixmap(pm: QPixmap, cfg: dict, primary: bool = False, png: bytes | None = None) -> None:
    """Copy a pixmap to the configured clipboards; primary needs wl-copy."""
    tool = cfg.get("clipboard.tool", "wl-copy")
    if tool in ("qt", "both"):
        QApplication.clipboard().setPixmap(pm)
    if wl_copy_supported(cfg):
        if png is None:
            png = pixmap_png(pm)
        if png is None:
            return
        targets = [False]
        if primary:
            targets.append(True)
        for is_primary in targets:
            wl_copy(png, is_primary)
