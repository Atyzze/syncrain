"""greetd's IPC, as a greeter speaks it: JSON messages, each after its length (a native-endian u32),
over the socket greetd names in GREETD_SOCK. greetd does the logging in (PAM) and starts the
session; a greeter only passes on what the user typed (github.com/kennylevinsen/greetd, greetd-ipc).
"""
from __future__ import annotations

import json
import os
import socket
import struct


class GreetdError(Exception):
    pass


class Greetd:
    def __init__(self, path: str | None = None, timeout: float = 60.0):
        self.path = path or os.environ.get("GREETD_SOCK", "")
        self.timeout = timeout

    def _exchange(self, sock, message: dict) -> dict:
        data = json.dumps(message).encode()
        sock.sendall(struct.pack("=I", len(data)) + data)
        head = self._read(sock, 4)
        (size,) = struct.unpack("=I", head)
        return json.loads(self._read(sock, size).decode())

    @staticmethod
    def _read(sock, n: int) -> bytes:
        out = b""
        while len(out) < n:
            chunk = sock.recv(n - len(out))
            if not chunk:
                raise GreetdError("greetd closed the connection")
            out += chunk
        return out

    def login(self, user: str, password: str, cmd: list[str], env: list[str]) -> tuple[bool, str]:
        """Log `user` in and have greetd start `cmd` once this greeter exits: (done, what to show).
        A secret prompt (the password) gets `password`; a visible one gets the user name; info and
        error messages are passed on in the answer."""
        if not self.path:
            return False, "not started by greetd (no GREETD_SOCK)"
        notes = []
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                sock.connect(self.path)
                reply = self._exchange(sock, {"type": "create_session", "username": user})
                while reply.get("type") == "auth_message":
                    kind, text = reply.get("auth_message_type"), reply.get("auth_message", "")
                    if kind in ("info", "error"):
                        notes.append(text.strip())
                        answer = None
                    else:
                        answer = password if kind == "secret" else user
                    reply = self._exchange(sock, {"type": "post_auth_message_response", "response": answer})
                if reply.get("type") != "success":
                    self._cancel(sock)
                    return False, self._said(reply, notes)
                reply = self._exchange(sock, {"type": "start_session", "cmd": cmd, "env": env})
                if reply.get("type") != "success":
                    self._cancel(sock)
                    return False, self._said(reply, notes)
                return True, "\n".join(n for n in notes if n)
        except (OSError, ValueError, GreetdError) as e:
            self._cancel_anew()
            return False, f"greetd: {e}"

    def _cancel_anew(self):
        """After a conversation that broke off (a timeout), greetd may still hold the half-made
        session; dropping it over a new connection lets the next try start clean."""
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(3)
                sock.connect(self.path)
                self._exchange(sock, {"type": "cancel_session"})
        except (OSError, ValueError, GreetdError):
            pass

    def _cancel(self, sock):
        try:
            self._exchange(sock, {"type": "cancel_session"})
        except (OSError, ValueError, GreetdError):
            pass

    @staticmethod
    def _said(reply: dict, notes) -> str:
        if reply.get("error_type") == "auth_error":
            text = "Wrong password"
        else:
            text = reply.get("description") or "The login did not go through"
        return "\n".join([*[n for n in notes if n], text])
