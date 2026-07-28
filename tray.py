# SnapCap - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import os
import threading

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmap, QImage

SNI_IFACE = "org.kde.StatusNotifierItem"
WATCHER_NAME = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"


def _icon_data(pixmap):
    img = pixmap.toImage().convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    raw = bytes(img.constBits().asarray(img.sizeInBytes()))
    return [w, h, list(raw)]


class _SNIObject(dbus.service.Object):
    def __init__(self, bus_name, path, callbacks):
        self._callbacks = callbacks
        self._icon_pm = None
        super().__init__(bus_name, path)

    def set_icon(self, pixmap):
        self._icon_pm = pixmap

    @dbus.service.method(SNI_IFACE, in_signature="ii", out_signature="")
    def Activate(self, x, y):
        cb = self._callbacks.get("activate")
        if cb:
            QTimer.singleShot(0, cb)

    @dbus.service.method(SNI_IFACE, in_signature="ii", out_signature="")
    def SecondaryActivate(self, x, y):
        cb = self._callbacks.get("settings")
        if cb:
            QTimer.singleShot(0, cb)

    @dbus.service.method(SNI_IFACE, in_signature="ii", out_signature="")
    def ContextMenu(self, x, y):
        cb = self._callbacks.get("menu")
        if cb:
            QTimer.singleShot(0, lambda: cb(x, y))

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        icon = _icon_data(self._icon_pm) if self._icon_pm else [0, 0, []]
        return {
            "Category": "Utility",
            "Id": "snapcap",
            "Title": "SnapCap",
            "Status": "Active",
            "IconThemePath": dbus.Array([], signature="s"),
            "IconPixmap": icon,
            "ItemIsMenu": False,
            "IconName": "",
        }


class SnapCapTray:
    def __init__(self, icon_pixmap: QPixmap, on_activate=None, on_settings=None, on_menu=None):
        self._icon = icon_pixmap
        self._callbacks = {
            "activate": on_activate,
            "settings": on_settings,
            "menu": on_menu,
        }
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self._loop = GLib.MainLoop()

        pid = os.getpid()
        bus_name = dbus.service.BusName(
            f"org.kde.StatusNotifierItem-{pid}-1",
            bus=dbus.SessionBus(),
        )
        self._obj = _SNIObject(bus_name, "/StatusNotifierItem", self._callbacks)
        self._obj.set_icon(self._icon)

        try:
            watcher = dbus.SessionBus().get_object(WATCHER_NAME, WATCHER_PATH)
            watcher.RegisterStatusNotifierItem(
                f"org.kde.StatusNotifierItem-{pid}-1",
                dbus_interface=WATCHER_NAME,
            )
        except Exception:
            pass

        self._loop.run()

    def stop(self):
        if hasattr(self, "_loop"):
            self._loop.quit()

    def update_icon(self, pixmap: QPixmap):
        self._icon = pixmap
        if hasattr(self, "_obj"):
            self._obj.set_icon(pixmap)
