# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Thread-safe dispatch of callbacks from background threads to the Qt main thread."""

import threading

from PySide6.QtCore import QCoreApplication, QEvent, QObject


class CallEvent(QEvent):
    def __init__(self, fn, args):
        super().__init__(QEvent.Type.User)
        self.fn = fn
        self.args = args


class EventReceiver(QObject):
    """Permanent receiver object. QCoreApplication.postEvent is thread-safe,
    so any thread can post a CallEvent here; the event loop of the thread that
    owns this receiver (the main thread) will execute the callback."""

    def event(self, event):
        if isinstance(event, CallEvent):
            event.fn(*event.args)
            return True
        return super().event(event)


def post(receiver, fn, *args):
    QCoreApplication.postEvent(receiver, CallEvent(fn, args))


def run_async(receiver, work, on_ok=None, on_error=None):
    """Run work() (blocking I/O) in a background thread and deliver its result
    to the Qt main thread via post(). on_ok receives the return value,
    on_error receives the exception. Receiver must be a QObject owned by the
    main thread."""

    def _work():
        try:
            result = work()
            if on_ok:
                post(receiver, on_ok, result)
        except Exception as e:  # noqa: BLE001 - delivered to the UI thread
            if on_error:
                post(receiver, on_error, e)

    threading.Thread(target=_work, daemon=True).start()
