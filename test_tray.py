# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Tests for the com.canonical.dbusmenu export (tray.py).

Run under a private session bus:
    dbus-run-session -- pytest test_tray.py

The menu server runs in a subprocess, mirroring production: objects on the
main thread, DBus served by the GLib main loop. Clients are subprocesses too
— exactly how a real SNI host (waybar, Plasma, ...) talks to us.
Same-process blocking DBus calls would deadlock the serving loop, so
everything stays cross-process.
"""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

from tray import DBUSMENU_IFACE, MENU_PATH  # noqa: E402

PY = sys.executable
SERVICE = "org.example.ChamelShotMenu"
SPEC = "/tmp/opencode/chamelshot-menu-spec.json"
LOG = "/tmp/opencode/chamelshot-menu-log.json"

SERVER_CODE = r"""
import json
import os
import sys

sys.path.insert(0, %(srcdir)r)
import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

from tray import DbusMenu, MENU_PATH

SPEC = %(spec)r
LOG = %(log)r

def builder():
    with open(SPEC) as f:
        spec = json.load(f)
    return [
        {
            **item,
            "callback": (
                (lambda cb_id=item["callback"]: on_clicked(cb_id))
                if item.get("callback")
                else None
            ),
        }
        for item in spec
    ]

def on_clicked(cb_id):
    try:
        with open(LOG) as f:
            log = json.load(f)
    except FileNotFoundError:
        log = []
    log.append(cb_id)
    with open(LOG, "w") as f:
        json.dump(log, f)

loop = GLib.MainLoop()

def on_bus_acquired(connection, name):
    DbusMenu(connection, MENU_PATH, builder)

Gio.bus_own_name(
    Gio.BusType.SESSION, %(service)r,
    Gio.BusNameOwnerFlags.NONE, on_bus_acquired, None, None,
)
loop.run()
"""


def _write_spec(items: list) -> None:
    with open(SPEC, "w") as f:
        json.dump(items, f)


@pytest.fixture(scope="module")
def menu_server():
    _write_spec(
        [
            {"label": "  \u25fb  Capture Region", "callback": "region"},
            {"label": "  \u25ad  Capture Window", "callback": "window"},
            {"type": "separator"},
            {"label": "  \u23f1  14:22:01", "callback": "history"},
            {"label": "  \u2014  No screenshots", "callback": None},
            {"type": "separator"},
            {"label": "  \u2699  Settings", "callback": "settings"},
            {"label": "  \u2715  Kill", "callback": "kill"},
        ]
    )
    for f in (LOG,):
        try:
            os.unlink(f)
        except FileNotFoundError:
            pass

    code = SERVER_CODE % {
        "srcdir": os.path.dirname(os.path.abspath(__file__)),
        "spec": SPEC,
        "log": LOG,
        "service": SERVICE,
    }
    server = subprocess.Popen([PY, "-c", code])
    try:
        time.sleep(1.5)
        yield
    finally:
        server.terminate()
        server.wait(timeout=10)


def _client(script: str) -> dict:
    """Run a DBus client in a subprocess (like a real SNI host) and return its JSON output."""
    code = (
        "import json, dbus\n"
        f"bus = dbus.SessionBus()\n"
        f"proxy = bus.get_object('{SERVICE}', '{MENU_PATH}')\n"
        f"iface = dbus.Interface(proxy, '{DBUSMENU_IFACE}')\n" + script + "\nprint(json.dumps(RESULT))"
    )
    out = subprocess.run(
        [PY, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return json.loads(out.stdout.strip())


def _wait_log(n: int, timeout=5.0) -> list:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with open(LOG) as f:
                log = json.load(f)
            if len(log) >= n:
                return log
        except FileNotFoundError:
            pass
        time.sleep(0.05)
    return log if "log" in locals() else []


def test_get_layout_root(menu_server):
    result = _client(
        "rev, layout = iface.GetLayout(0, -1, dbus.Array([], signature='s'))\n"
        "root_id, props, children = layout\n"
        "RESULT = {'rev': rev, 'root_id': root_id, 'type': props['type'],\n"
        "          'display': props['children-display'],\n"
        "          'children': [c[0] for c in children]}"
    )
    assert result["rev"] > 0
    assert result["root_id"] == 0
    assert result["type"] == "root"
    assert result["display"] == "submenu"
    assert result["children"] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_get_layout_item_props(menu_server):
    result = _client(
        "_, layout = iface.GetLayout(0, -1, dbus.Array([], signature='s'))\n"
        "children = list(layout[2])\n"
        "item1 = children[0][1]\n"
        "sep = children[2][1]\n"
        "disabled = children[4][1]\n"
        "RESULT = {'label': item1['label'], 'item1_enabled': bool(item1['enabled']),\n"
        "          'sep_type': sep['type'], 'disabled_enabled': bool(disabled['enabled'])}"
    )
    assert result["label"] == "  \u25fb  Capture Region"
    assert result["item1_enabled"] is True
    assert result["sep_type"] == "separator"
    assert result["disabled_enabled"] is False


def test_event_dispatch(menu_server):
    _client("iface.Event(1, 'clicked', '0', 0)\niface.Event(8, 'clicked', '0', 0)\nRESULT = {}")
    log = _wait_log(2)
    assert log == ["region", "kill"]


def test_event_ignores_non_clicked(menu_server):
    before = _wait_log(0)
    _client(
        "iface.Event(2, 'opened', '0', 0)\n"
        "iface.Event(99, 'clicked', '0', 0)\n"  # unknown id
        "RESULT = {}"
    )
    time.sleep(0.5)
    assert _wait_log(len(before) + 1, timeout=1) == before


def test_about_to_show_refresh(menu_server):
    # Fresh menu: AboutToShow reports no change.
    result = _client("RESULT = {'need': bool(iface.AboutToShow(0))}")
    assert result["need"] is False

    # Simulate a new screenshot appearing in history.
    _write_spec(
        [
            {"label": "  \u25fb  Capture Region", "callback": "region"},
            {"type": "separator"},
            {"label": "  \u23f1  15:00:00", "callback": "history2"},
        ]
    )

    result = _client(
        "need = bool(iface.AboutToShow(0))\n"
        "rev, layout = iface.GetLayout(0, -1, dbus.Array([], signature='s'))\n"
        "children = list(layout[2])\n"
        "item = children[2][1]\n"
        "RESULT = {'need': need, 'children': [c[0] for c in children], 'label': item['label']}"
    )
    assert result["need"] is True
    assert result["children"] == [1, 2, 3]
    assert result["label"] == "  \u23f1  15:00:00"


def test_get_group_properties(menu_server):
    result = _client(
        "groups = iface.GetGroupProperties([1, 3], dbus.Array([], signature='s'))\n"
        "RESULT = {'ids': [g[0] for g in groups],\n"
        "          'label': groups[0][1]['label']}"
    )
    assert result["ids"] == [1, 3]
    assert result["label"] == "  \u25fb  Capture Region"


def test_about_to_show_group(menu_server):
    result = _client("out = iface.AboutToShowGroup([0])\nRESULT = {'id': out[0][0], 'need': bool(out[0][1])}")
    assert result["id"] == 0
    assert result["need"] is False


def test_dbusmenu_properties(menu_server):
    result = _client(
        "props = iface.GetAll('com.canonical.dbusmenu', dbus_interface='org.freedesktop.DBus.Properties')\n"
        "RESULT = {'version': props['Version'], 'status': props['Status']}"
    )
    assert result["version"] == 3
    assert result["status"] == "normal"
