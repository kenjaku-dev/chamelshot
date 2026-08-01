# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Single-instance enforcement + command forwarding over a Unix domain socket.

First instance binds the socket and becomes the daemon. Any later invocation
connects, sends its command (capture / settings / menu / ...), and exits.
"""

import json
import os
import socket
import threading

PING = "ping"


class AlreadyRunningError(Exception):
    """Another daemon holds the socket and is alive."""


class IpcServer:
    def __init__(self, socket_path, receiver, on_command):
        self.socket_path = socket_path
        self.receiver = receiver
        self.on_command = on_command
        self._sock: socket.socket | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)

    def start(self):
        os.makedirs(os.path.dirname(self.socket_path), exist_ok=True)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(str(self.socket_path))
        except OSError:
            # Socket exists. Race: two instances can both unlink a stale
            # socket, then both try to bind — the loser must not crash.
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                probe.connect(str(self.socket_path))
                probe.close()
                raise AlreadyRunningError("another instance holds the socket")  # noqa: TRY003 - internal
            except AlreadyRunningError:
                sock.close()
                raise
            except OSError:
                pass
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass
            try:
                sock.bind(str(self.socket_path))
            except OSError:
                sock.close()
                raise AlreadyRunningError("socket bind failed")  # noqa: TRY003 - internal
        self._sock = sock
        self._sock.listen(4)
        self._thread.start()

    def _accept_loop(self):
        if self._sock is None:
            return
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except OSError:
                break
            with conn:
                try:
                    data = conn.recv(4096)
                except OSError:
                    continue
                if not data:
                    continue
                try:
                    msg = json.loads(data.decode("utf-8"))
                    cmd = msg.get("cmd", "")
                    # Imported lazily: `import ipc` must stay PySide6-free so
                    # CLI forwarding (`chamelshot --capture`) skips Qt import.
                    from dispatcher import post

                    post(self.receiver, self.on_command, cmd)
                except (ValueError, UnicodeDecodeError) as _:
                    continue

    def stop(self):
        self._stop.set()
        if self._sock is not None:
            self._sock.close()
        try:
            os.unlink(self.socket_path)
        except OSError:
            pass


def send_command(socket_path, cmd) -> bool:
    """Connect to a running daemon and send a command. Returns True on success."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(str(socket_path))
        sock.sendall(json.dumps({"cmd": cmd}).encode("utf-8"))
        return True
    except (FileNotFoundError, ConnectionRefusedError, OSError) as _:
        return False
    finally:
        sock.close()


def clean_stale_socket(socket_path):
    try:
        os.unlink(socket_path)
    except OSError:
        pass
