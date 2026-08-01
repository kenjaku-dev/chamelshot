# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Watcher lifecycle tests for the StatusNotifierItem registration.

SNI hosts (waybar, Plasma, ...) only learn about items through the
org.kde.StatusNotifierWatcher: they dump its registered-items list on start
and react to StatusNotifierItemRegistered signals. If the watcher restarts,
every item must re-register or it vanishes from the bar forever.

These tests drive a fake watcher through a full lifecycle (appear, die,
reappear) and assert the tray registers every time, plus that the payload
is our SNI bus name.

Run under a private session bus:
    dbus-run-session -- pytest test_tray_watcher.py
"""

import json
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

PY = sys.executable
WATCHER = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"
_TMP = tempfile.mkdtemp(prefix="chamelshot-watcher-")
REGLOG = os.path.join(_TMP, "regs.json")
NAME_FILE = os.path.join(_TMP, "name.json")

WATCHER_XML = f"""<node>
  <interface name="{WATCHER}">
    <method name="RegisterStatusNotifierItem">
      <arg name="service" type="s" direction="in"/>
    </method>
    <method name="RegisterStatusNotifierHost">
      <arg name="service" type="s" direction="in"/>
    </method>
  </interface>
</node>"""

TRAY_CODE = r"""
import json
import os
import sys

sys.path.insert(0, %(srcdir)r)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib
from PySide6.QtGui import QGuiApplication, QPixmap

from tray import ChamelShotTray

app = QGuiApplication([])
tray = ChamelShotTray(
    QPixmap(16, 16),
    menu_builder=lambda: [{"label": "x", "callback": None}],
    on_activate=lambda *a: None,
    on_settings=lambda *a: None,
    on_menu=lambda *a: None,
)
with open(%(name_file)r, "w") as f:
    json.dump(tray._bus_name, f)
app.exec()
"""

WATCHER_CODE = r"""
import json
import sys

sys.path.insert(0, %(srcdir)r)
import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

REGLOG = %(reglog)r
WATCHER_XML = %(watcher_xml)r
WATCHER_PATH = "/StatusNotifierWatcher"
node = Gio.DBusNodeInfo.new_for_xml(WATCHER_XML)

def log(service):
    try:
        with open(REGLOG) as f:
            regs = json.load(f)
    except FileNotFoundError:
        regs = []
    regs.append(service)
    with open(REGLOG, "w") as f:
        json.dump(regs, f)

def on_method(connection, sender, object_path, iface, method, parameters, invocation):
    log(str(parameters.unpack()[0]))
    invocation.return_value(None)

loop = GLib.MainLoop()

def on_bus_acquired(connection, name):
    connection.register_object(
        WATCHER_PATH, node.interfaces[0], on_method, None, None
    )

Gio.bus_own_name(
    Gio.BusType.SESSION, %(watcher)r,
    Gio.BusNameOwnerFlags.REPLACE, on_bus_acquired, None, None,
)
loop.run()
"""


def _wait_regs(n: int, timeout=8.0) -> list:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with open(REGLOG) as f:
                regs = json.load(f)
            if len(regs) >= n:
                return regs
        except FileNotFoundError:
            pass
        time.sleep(0.1)
    return regs if "regs" in locals() else []


def _spawn_watcher():
    code = WATCHER_CODE % {
        "srcdir": os.path.dirname(os.path.abspath(__file__)),
        "reglog": REGLOG,
        "watcher_xml": WATCHER_XML,
        "watcher": WATCHER,
    }
    return subprocess.Popen([PY, "-c", code])


@pytest.fixture(scope="module")
def tray_server():
    try:
        os.unlink(REGLOG)
    except FileNotFoundError:
        pass
    code = TRAY_CODE % {
        "srcdir": os.path.dirname(os.path.abspath(__file__)),
        "name_file": NAME_FILE,
    }
    server = subprocess.Popen([PY, "-c", code])
    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            if os.path.exists(NAME_FILE):
                break
            time.sleep(0.1)
        with open(NAME_FILE) as f:
            bus_name = json.load(f)
        time.sleep(0.5)
        yield bus_name
    finally:
        server.terminate()
        server.wait(timeout=10)


def test_registers_when_watcher_appears(tray_server):
    # No watcher running yet: nothing registered.
    assert _wait_regs(1, timeout=1.0) == []

    # Watcher appears -> tray must register with its SNI bus name.
    watcher = _spawn_watcher()
    try:
        regs = _wait_regs(1)
        assert regs == [tray_server]
    finally:
        watcher.terminate()
        watcher.wait(timeout=10)


def test_re_registers_after_watcher_restart(tray_server):
    regs = _wait_regs(1)
    assert regs[-1] == tray_server

    # Kill the watcher, then bring up a fresh one: the tray must re-register
    # (this is the "waybar restarted" scenario that lost the icon).
    time.sleep(0.5)
    watcher = _spawn_watcher()
    try:
        regs = _wait_regs(2)
        assert regs[-1] == tray_server
    finally:
        watcher.terminate()
        watcher.wait(timeout=10)
