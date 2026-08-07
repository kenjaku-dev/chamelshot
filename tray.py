# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import os

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402  # pyright: ignore[reportAttributeAccessIssue]
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QImage, QPixmap  # noqa: E402

SNI_IFACE = "org.kde.StatusNotifierItem"
WATCHER_NAME = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"
PROPS_IFACE = "org.freedesktop.DBus.Properties"

DBUSMENU_IFACE = "com.canonical.dbusmenu"
MENU_PATH = "/MenuBar"

DBUSMENU_XML = f"""<node>
  <interface name="{DBUSMENU_IFACE}">
    <method name="GetLayout">
      <arg type="i" name="parentId" direction="in"/>
      <arg type="i" name="recursionDepth" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="u" name="revision" direction="out"/>
      <arg type="(ia{{sv}}av)" name="layout" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="a(ia{{sv}})" name="properties" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="name" direction="in"/>
      <arg type="v" name="value" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="eventId" direction="in"/>
      <arg type="v" name="data" direction="in"/>
      <arg type="u" name="timestamp" direction="in"/>
    </method>
    <method name="EventGroup">
      <arg type="a(isvu)" name="events" direction="in"/>
    </method>
    <method name="AboutToShow">
      <arg type="i" name="id" direction="in"/>
      <arg type="b" name="needUpdate" direction="out"/>
    </method>
    <method name="AboutToShowGroup">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="a(ib)" name="updatesNeeded" direction="out"/>
    </method>
    <signal name="LayoutUpdated">
      <arg type="u" name="revision"/>
      <arg type="i" name="parent"/>
    </signal>
    <signal name="ItemsPropertiesUpdated">
      <arg type="a(ia{{sv}})" name="updatedProps"/>
      <arg type="a(ias)" name="removedProps"/>
    </signal>
    <property name="Version" type="u" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
  </interface>
  <interface name="{PROPS_IFACE}">
    <method name="GetAll">
      <arg type="s" name="interface_name" direction="in"/>
      <arg type="a{{sv}}" name="properties" direction="out"/>
    </method>
    <method name="Get">
      <arg type="s" name="interface_name" direction="in"/>
      <arg type="s" name="property_name" direction="in"/>
      <arg type="v" name="value" direction="out"/>
    </method>
    <method name="Set">
      <arg type="s" name="interface_name" direction="in"/>
      <arg type="s" name="property_name" direction="in"/>
      <arg type="v" name="value" direction="in"/>
    </method>
  </interface>
</node>"""

SNI_XML = f"""<node>
  <interface name="{SNI_IFACE}">
    <method name="Activate">
      <arg type="i" name="x" direction="in"/>
      <arg type="i" name="y" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg type="i" name="x" direction="in"/>
      <arg type="i" name="y" direction="in"/>
    </method>
    <method name="ContextMenu">
      <arg type="i" name="x" direction="in"/>
      <arg type="i" name="y" direction="in"/>
    </method>
    <method name="Scroll">
      <arg type="i" name="delta" direction="in"/>
      <arg type="s" name="orientation" direction="in"/>
    </method>
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionMovieName" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewAttentionIcon"/>
    <signal name="NewOverlayIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus"/>
  </interface>
  <interface name="{PROPS_IFACE}">
    <method name="GetAll">
      <arg type="s" name="interface_name" direction="in"/>
      <arg type="a{{sv}}" name="properties" direction="out"/>
    </method>
    <method name="Get">
      <arg type="s" name="interface_name" direction="in"/>
      <arg type="s" name="property_name" direction="in"/>
      <arg type="v" name="value" direction="out"/>
    </method>
    <method name="Set">
      <arg type="s" name="interface_name" direction="in"/>
      <arg type="s" name="property_name" direction="in"/>
      <arg type="v" name="value" direction="in"/>
    </method>
  </interface>
</node>"""


def _icon_data(pixmap):
    """Return the IconPixmap value ``a(iiay)`` for a QPixmap."""
    img = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    w, h = img.width(), img.height()
    if w > 64 or h > 64:
        img = img.scaled(
            64,
            64,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        w, h = img.width(), img.height()
    raw = bytes(img.constBits())
    return GLib.Variant("a(iiay)", [(w, h, raw)])


def _props_variants(props: dict) -> dict:
    """Convert ``{name: (type, value)}`` to ``{name: GLib.Variant}``.

    ``value`` may already be a GLib.Variant (container types). The result is
    meant to be embedded directly in struct/array/tuple constructions —
    prebuilt ``a{{sv}}`` variants get unboxed by gi when iterated.
    """
    out = {}
    for name, spec in props.items():
        if isinstance(spec, GLib.Variant):
            out[name] = spec
            continue
        vtype, value = spec
        if isinstance(value, GLib.Variant):
            out[name] = value
        elif vtype == "b":
            out[name] = GLib.Variant("b", bool(value))
        else:
            out[name] = GLib.Variant(vtype, value)
    return out


def _props_a_sv(props: dict) -> GLib.Variant:
    """Standalone ``a{{sv}}`` variant for a props dict."""
    return GLib.Variant("a{sv}", _props_variants(props))


def _fingerprint_items(items: list) -> tuple:
    """Recursive fingerprint of a menu item list (label/type/callback + children)."""
    return tuple(
        (
            i.get("type", "standard"),
            i.get("label", ""),
            i.get("callback") is not None,
            _fingerprint_items(i.get("children") or []),
        )
        for i in items
    )


class DbusMenu:
    """com.canonical.dbusmenu export (spec-exact) so the SNI host (waybar,
    Plasma, gnome-shell, ...) renders our context menu natively.

    The host renders a GTK menu attached to its own surface and sends
    Event(id, "clicked", ...) on selection — no xdg_popup from our process,
    so it works on Wayland compositors (niri, sway, ...) that reject popups
    whose transient parent never received input.

    Implemented with Gio/GVariant because dbus-python cannot marshal the
    required reply types: GetLayout must return ``(u(ia{sv}av))`` with
    children as variant-wrapped structs, which dbus-python 1.4 fails on
    ("Expected a string or unicode object" — nested structs and
    variant-wrapped containers in replies are broken). GVariant builds
    them natively and byte-exactly.

    IMPORTANT: DBus dispatch is driven by the GLib default main context,
    which the Qt event loop services (QEventDispatcherGlib) — so this
    object must be created on the main thread and served inside app.exec().
    A GLib main loop in a worker thread never dispatches Gio/dbus sources
    once a QCoreApplication exists (verified empirically).

    Item entries produced by ``builder`` are dicts:
      {"label": str, "callback": callable | None, "type": "standard"|"separator",
       "children": [same-typed dicts] | None, "tooltip": str | None}
    A missing/None callback yields a disabled item (e.g. "No screenshots").
    Items with children are rendered as submenus: ``children-display: submenu``
    and GetLayout returns their nested children under their own parent id.
    An optional ``tooltip`` is exposed on the wire as the (non-standard,
    host-ignored-if-unsupported) ``tooltip-text`` property.
    """

    def __init__(self, connection: Gio.DBusConnection, path: str, builder):
        self._connection = connection
        self._path = path
        self._builder = builder
        self._by_id: dict[int, dict] = {}
        self._children_of: dict[int, list[int]] = {}
        self._root_children: list[int] = []
        self._revision = 1
        self._fingerprint = self._fingerprint_of(builder())
        node = Gio.DBusNodeInfo.new_for_xml(DBUSMENU_XML)
        connection.register_object(path, node.interfaces[0], self._on_method_call, None, None)
        self._refresh()

    # ------------------------------------------------------------ internals

    def _refresh(self):
        """Rebuild the item id tree from the builder callback, bump revision.

        Ids are assigned depth-first (pre-order): root items keep ids 1..N
        in their list order, then each submenu's children follow their
        parent's id. test_tray.py's flat layout therefore keeps root ids
        1..N unchanged while nested additions live deep in the tree.
        """
        items = self._builder()
        self._by_id = {}
        self._children_of = {}
        self._root_children = []
        counter = 0

        def walk(list_items, out):
            nonlocal counter
            for it in list_items:
                it = {"type": "separator"} if it.get("type") == "separator" else it
                counter += 1
                self._by_id[counter] = it
                out.append(counter)
                kids = it.get("children")
                if kids:
                    parent = counter
                    self._children_of[parent] = walk(kids, [])
            return out

        walk(items, self._root_children)
        self._revision += 1

    def _layout_props(self, item_id: int) -> dict:
        """Props dict {name: (type, value)} for one menu item (0 = root)."""
        if item_id == 0:
            return {
                "type": ("s", "root"),
                "children-display": ("s", "submenu"),
            }
        item = self._by_id.get(item_id)
        if item is None:
            return {}
        if item.get("type") == "separator":
            return {"type": ("s", "separator"), "visible": ("b", True)}
        is_submenu = item_id in self._children_of
        props = {
            "label": ("s", item.get("label", "")),
            "enabled": ("b", True if is_submenu else item.get("callback") is not None),
            "visible": ("b", True),
            "type": ("s", "standard"),
        }
        tooltip = item.get("tooltip")
        if tooltip:
            props["tooltip-text"] = ("s", tooltip)
        if is_submenu:
            props["children-display"] = ("s", "submenu")
        return props

    def _children_ids(self, item_id: int) -> list[int]:
        """Top-level ids for the root parent, nested ids for a submenu parent."""
        if item_id == 0:
            return self._root_children
        return self._children_of.get(item_id, [])

    def _child_variant(self, item_id: int, depth: int = -1) -> GLib.Variant:
        """One GetLayout child: a variant holding a ``(ia{sv}av)`` struct.

        ``depth`` recurses into nested children (-1 = all, 0 = none).
        """
        children = []
        if depth != 0:
            children = [self._child_variant(c, depth - 1 if depth > 0 else depth) for c in self._children_ids(item_id)]
        return GLib.Variant(
            "(ia{sv}av)",
            (item_id, _props_variants(self._layout_props(item_id)), children),
        )

    # ------------------------------------------------------------- dispatch

    def _on_method_call(self, connection, sender, object_path, interface_name, method_name, parameters, invocation):
        try:
            if interface_name == PROPS_IFACE:
                self._on_properties(method_name, parameters, invocation)
                return
            handler = getattr(self, f"_m_{method_name}", None)
            if handler is None:
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownMethod",
                    f"Unknown method {interface_name}.{method_name}",
                )
                return
            handler(parameters, invocation)
        except Exception as e:  # pragma: no cover - defensive
            invocation.return_dbus_error("org.freedesktop.DBus.Error.Failed", str(e))

    def _on_properties(self, method_name, parameters, invocation):
        if method_name == "GetAll":
            iface = parameters.unpack()[0]
            if str(iface) == DBUSMENU_IFACE:
                props = {
                    "Version": ("u", 3),
                    "Status": ("s", "normal"),
                    "TextDirection": ("s", "ltr"),
                    "IconThemePath": ("as", []),
                }
            else:
                props = {}
            invocation.return_value(GLib.Variant("(a{sv})", (_props_variants(props),)))
        elif method_name == "Get":
            _iface, name = parameters.unpack()
            props = {
                "Version": ("u", 3),
                "Status": ("s", "normal"),
                "TextDirection": ("s", "ltr"),
                "IconThemePath": ("as", []),
            }
            value = _props_a_sv(props).lookup_value(str(name), None)
            if value is None:
                value = GLib.Variant("s", "")
            invocation.return_value(GLib.Variant("(v)", (value,)))
        elif method_name == "Set":
            invocation.return_dbus_error("org.freedesktop.DBus.Error.PropertyReadOnly", "Read-only")

    # ------------------------------------------------------------- DBusMenu

    def _m_GetLayout(self, parameters, invocation):  # noqa: N802
        parent_id, recursion_depth, _names = parameters.unpack()
        parent_id, recursion_depth = int(parent_id), int(recursion_depth)
        if recursion_depth != 0:
            children = [
                self._child_variant(c, recursion_depth - 1 if recursion_depth > 0 else recursion_depth)
                for c in self._children_ids(parent_id)
            ]
        else:
            children = []
        layout = (
            parent_id,
            _props_variants(self._layout_props(parent_id)),
            children,
        )
        invocation.return_value(GLib.Variant("(u(ia{sv}av))", (self._revision, layout)))

    def _m_GetGroupProperties(self, parameters, invocation):  # noqa: N802
        ids, _names = parameters.unpack()
        out = []
        for item_id in ids:
            props = self._layout_props(int(item_id))
            if props:
                out.append((int(item_id), _props_variants(props)))
        invocation.return_value(GLib.Variant("(a(ia{sv}))", (out,)))

    def _m_GetProperty(self, parameters, invocation):  # noqa: N802
        item_id, name = parameters.unpack()
        props = self._layout_props(int(item_id))
        value = _props_a_sv(props).lookup_value(str(name), None)
        if value is None:
            value = GLib.Variant("s", "")
        invocation.return_value(GLib.Variant("(v)", (value,)))

    def _m_Event(self, parameters, invocation):  # noqa: N802
        item_id, event_id, _data, _timestamp = parameters.unpack()
        self._handle_event(int(item_id), str(event_id))
        invocation.return_value(None)

    def _m_EventGroup(self, parameters, invocation):  # noqa: N802
        events = parameters.unpack()[0]
        for item_id, event_id, _data, _timestamp in events:
            self._handle_event(int(item_id), str(event_id))
        invocation.return_value(None)

    def _m_AboutToShow(self, parameters, invocation):  # noqa: N802
        item_id = int(parameters.unpack()[0])
        need = self._check_refresh(item_id)
        invocation.return_value(GLib.Variant("(b)", (need,)))

    def _m_AboutToShowGroup(self, parameters, invocation):  # noqa: N802
        ids = parameters.unpack()[0]
        out = [(int(i), self._check_refresh(int(i))) for i in ids]
        invocation.return_value(GLib.Variant("(a(ib))", (out,)))

    def _check_refresh(self, item_id: int) -> bool:
        """Rebuild + emit LayoutUpdated when the menu changed; True if so."""
        if item_id != 0:
            return False
        fp = self._fingerprint_of(self._builder())
        if fp != self._fingerprint:
            self._fingerprint = fp
            self._refresh()
            self.emit_layout_updated()
            return True
        return False

    # ------------------------------------------------------------- signals

    def emit_layout_updated(self):
        self._connection.emit_signal(
            None,
            self._path,
            DBUSMENU_IFACE,
            "LayoutUpdated",
            GLib.Variant("(ui)", (self._revision, 0)),
        )

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _fingerprint_of(items: list) -> tuple:
        return _fingerprint_items(items)

    def _handle_event(self, item_id: int, event_id: str):
        if event_id != "clicked":
            return
        item = self._by_id.get(item_id)
        if not item:
            return
        callback = item.get("callback")
        if callback:
            callback()


class _SNIObject:
    def __init__(self, connection, path, callbacks):
        self._callbacks = callbacks
        self._icon_pm = None
        node = Gio.DBusNodeInfo.new_for_xml(SNI_XML)
        connection.register_object(path, node.interfaces[0], self._on_method_call, None, None)

    def set_icon(self, pixmap):
        self._icon_pm = pixmap

    def _on_method_call(self, connection, sender, object_path, interface_name, method_name, parameters, invocation):
        try:
            if interface_name == PROPS_IFACE:
                self._on_properties(method_name, parameters, invocation)
                return
            if method_name == "Activate":
                x, y = parameters.unpack()
                self._dispatch("activate", x, y)
            elif method_name == "SecondaryActivate":
                x, y = parameters.unpack()
                self._dispatch("settings", x, y)
            elif method_name == "ContextMenu":
                x, y = parameters.unpack()
                self._dispatch("menu", x, y)
            else:
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownMethod",
                    f"Unknown method {interface_name}.{method_name}",
                )
                return
            invocation.return_value(None)
        except Exception as e:  # pragma: no cover - defensive
            invocation.return_dbus_error("org.freedesktop.DBus.Error.Failed", str(e))

    def _dispatch(self, key, *args):
        cb = self._callbacks.get(key)
        if cb:
            cb(*args)

    def _on_properties(self, method_name, parameters, invocation):
        if method_name == "GetAll":
            iface = parameters.unpack()[0]
            props = self._props() if str(iface) == SNI_IFACE else {}
            invocation.return_value(GLib.Variant("(a{sv})", (_props_variants(props),)))
        elif method_name == "Get":
            _iface, name = parameters.unpack()
            value = _props_a_sv(self._props()).lookup_value(str(name), None)
            if value is None:
                value = GLib.Variant("s", "")
            invocation.return_value(GLib.Variant("(v)", (value,)))
        elif method_name == "Set":
            invocation.return_dbus_error("org.freedesktop.DBus.Error.PropertyReadOnly", "Read-only")

    def _props(self):
        icon = _icon_data(self._icon_pm) if self._icon_pm else GLib.Variant("a(iiay)", [])
        return {
            "Category": ("s", "Utility"),
            "Id": ("s", "chamelshot"),
            "Title": ("s", "ChamelShot"),
            "Status": ("s", "Active"),
            "WindowId": ("i", 0),
            "IconName": ("s", ""),
            "IconPixmap": ("a(iiay)", icon),
            "OverlayIconPixmap": ("a(iiay)", GLib.Variant("a(iiay)", [])),
            "AttentionIconName": ("s", ""),
            "AttentionIconPixmap": ("a(iiay)", GLib.Variant("a(iiay)", [])),
            "AttentionMovieName": ("s", ""),
            "ToolTip": ("(sa(iiay)ss)", ("", [], "", "")),
            "ItemIsMenu": ("b", True),
            "Menu": ("o", GLib.Variant("o", MENU_PATH)),
            "IconThemePath": ("as", []),
        }


class ChamelShotTray:
    """Registers the StatusNotifierItem + DBusMenu on the main thread.

    Gio uses the GLib default main context, which the Qt event loop drives
    (QEventDispatcherGlib) — so there is no background thread: the host's
    calls (Activate, ContextMenu, GetLayout, Event, ...) arrive inside
    app.exec() and callbacks run on the main thread directly.
    """

    def __init__(self, icon_pixmap: QPixmap, menu_builder=None, on_activate=None, on_settings=None, on_menu=None):
        self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        pid = os.getpid()
        self._bus_name = f"org.kde.StatusNotifierItem-{pid}-1"
        self._registered = False
        self._retry_id = None
        self._retry_left = 0

        self._name_owner = Gio.bus_own_name(
            Gio.BusType.SESSION,
            self._bus_name,
            Gio.BusNameOwnerFlags.NONE,
            None,
            self._on_name_acquired,
            self._on_name_lost,
        )
        self._obj = _SNIObject(
            self._bus,
            "/StatusNotifierItem",
            {"activate": on_activate, "settings": on_settings, "menu": on_menu},
        )
        self._obj.set_icon(icon_pixmap)

        self._menu = None
        if menu_builder is not None:
            self._menu = DbusMenu(self._bus, MENU_PATH, menu_builder)

        # SNI hosts (waybar, Plasma, ...) only learn about items through the
        # StatusNotifierWatcher: they dump its registered-items list when they
        # (re)start and listen for StatusNotifierItemRegistered signals. A
        # single registration attempt at startup is therefore not enough — if
        # the watcher restarts (waybar restart, crash, ...) the item vanishes
        # from the bar for good. Watch the watcher name and (re)register
        # whenever it appears, like Qt/KDE SNI implementations do.
        self._watcher_watch = Gio.bus_watch_name(
            Gio.BusType.SESSION,
            WATCHER_NAME,
            Gio.BusNameWatcherFlags.NONE,
            self._on_watcher_appeared,
            self._on_watcher_vanished,
        )

    # ---------------------------------------------------------- registration

    def _on_name_acquired(self, connection, name):
        self._register_with_watcher()

    def _on_name_lost(self, connection, name):
        self._registered = False

    def _on_watcher_appeared(self, connection, name, owner):
        self._register_with_watcher()

    def _on_watcher_vanished(self, connection, name):
        self._registered = False
        if self._retry_id is not None:
            GLib.source_remove(self._retry_id)
            self._retry_id = None
            self._retry_left = 0

    def _register_with_watcher(self):
        if self._registered:
            return
        try:
            watcher = Gio.DBusProxy.new_sync(
                self._bus,
                Gio.DBusProxyFlags.NONE,
                None,
                WATCHER_NAME,
                WATCHER_PATH,
                WATCHER_NAME,
                None,
            )
            watcher.call_sync(
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", (self._bus_name,)),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
            self._registered = True
        except GLib.Error:
            # The watcher can own its name before its object is exported
            # (waybar does exactly this). Retry briefly instead of giving up.
            if self._retry_id is None and self._retry_left < 20:
                self._retry_left += 1
                self._retry_id = GLib.timeout_add(300, self._retry_register)

    def _retry_register(self):
        self._retry_id = None
        self._register_with_watcher()
        return False
