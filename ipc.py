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

from dispatcher import post

PING = "ping"


class IpcServer:
    def __init__(self, socket_path, receiver, on_command):
        self.socket_path = socket_path
        self.receiver = receiver
        self.on_command = on_command
        self._sock = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)

    def start(self):
        os.makedirs(os.path.dirname(self.socket_path), exist_ok=True)
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(self.socket_path))
        self._sock.listen(4)
        self._thread.start()

    def _accept_loop(self):
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
                    post(self.receiver, self.on_command, cmd)
                except (ValueError, UnicodeDecodeError):
                    continue

    def stop(self):
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass
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
    except (FileNotFoundError, ConnectionRefusedError, OSError):
        return False
    finally:
        sock.close()


def clean_stale_socket(socket_path):
    try:
        os.unlink(socket_path)
    except OSError:
        pass
