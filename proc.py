# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import os
import sys

# PyInstaller bundles set LD_LIBRARY_PATH to point at the app's own libs, so
# external helpers (grim, slurp, notify-send, wl-copy, xdg-open) load the
# wrong shared objects and fail. Strip bundle-only vars for subprocesses in
# frozen builds.
_BUNDLE_VARS = ("LD_LIBRARY_PATH", "LD_PRELOAD", "LD_LIBRARY_PATH_ORIG")


def env() -> dict:
    if not getattr(sys, "frozen", False):
        return dict(os.environ)
    clean = {k: v for k, v in os.environ.items() if k not in _BUNDLE_VARS}
    original = os.environ.get("LD_LIBRARY_PATH_ORIG")
    if original:
        clean["LD_LIBRARY_PATH"] = original
    return clean
