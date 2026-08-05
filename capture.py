# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import json
import subprocess
import threading
import time

from PySide6.QtGui import QPixmap

import proc
from dispatcher import post

GRIM_NOT_FOUND = "grim is not installed. Install it: sudo pacman -S grim"

Monitor = tuple[str, str, str]  # (output name, make, model)


def _run_niri(args: list[str]) -> dict | None:
    """Run `niri msg` and parse stdout as JSON; None on any failure."""
    try:
        result = subprocess.run(
            ["niri", "msg", *args],
            capture_output=True,
            text=True,
            timeout=5,
            env=proc.env(),
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_monitors(outputs_json: str) -> list[Monitor]:
    """Parse `niri msg -j outputs` stdout into (name, make, model) tuples."""
    try:
        raw = json.loads(outputs_json)
    except json.JSONDecodeError:
        return []
    monitors = []
    for name, info in raw.items():
        if not isinstance(info, dict):
            continue
        monitors.append((name, str(info.get("make", "")), str(info.get("model", ""))))
    return monitors


def list_monitors() -> list[Monitor]:
    """Return connected monitors via niri, or [] if niri is missing/fails."""
    data = _run_niri(["-j", "outputs"])
    if data is None:
        return []
    return parse_monitors(json.dumps(data))


def focused_monitor() -> str | None:
    """Return the output name of the currently focused niri output."""
    data = _run_niri(["-j", "focused-output"])
    if data is None:
        return None
    return data.get("name")


def _run_grim(args: list[str], delay: int = 0) -> QPixmap:
    if delay > 0:
        time.sleep(delay)
    cmd = ["grim"]
    cmd.extend(args)
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10, env=proc.env())
    except FileNotFoundError:
        raise RuntimeError(GRIM_NOT_FOUND)
    if result.returncode != 0:
        raise RuntimeError(f"grim failed (exit {result.returncode}): {result.stderr.decode().strip()}")
    pm = QPixmap()
    if not pm.loadFromData(result.stdout):
        raise RuntimeError("Failed to decode grim output")
    return pm


def capture_region(
    left: int,
    top: int,
    right: int,
    bottom: int,
    delay: int = 0,
    include_cursor: bool = False,
) -> QPixmap:
    w = right - left
    h = bottom - top
    args = []
    if include_cursor:
        args.append("--cursor")
    args.extend(["-g", f"{left},{top} {w}x{h}", "-"])
    return _run_grim(args, delay)


def capture_fullscreen(delay: int = 0, include_cursor: bool = False) -> QPixmap:
    args = ["--cursor"] if include_cursor else []
    args.append("-")
    return _run_grim(args, delay)


def capture_monitor(output: str, delay: int = 0, include_cursor: bool = False) -> QPixmap:
    """Capture a single output with grim -o <output>."""
    args = ["--cursor"] if include_cursor else []
    args.extend(["-o", output, "-"])
    return _run_grim(args, delay)


def capture_async(receiver, capture_fn, on_success, on_error):
    """Run capture_fn (which blocks on grim) in a background thread and post the
    result to the Qt main thread via the dispatcher."""

    def _work():
        try:
            pm = capture_fn()
            post(receiver, on_success, pm)
        except Exception as e:  # noqa: BLE001 - forwarded to UI thread
            post(receiver, on_error, e)

    threading.Thread(target=_work, daemon=True).start()
