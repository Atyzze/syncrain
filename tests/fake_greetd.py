"""A stand-in for greetd's socket, as a greeter sees it (greetd-ipc(7)): one user and password,
a PAM conversation of an info line and the password prompt, and a record of every request.
`delay` is how long checking a password takes (a slow PAM module)."""
from __future__ import annotations

import json
import socket
import struct
import threading
import time
from pathlib import Path


class FakeGreetd:
    def __init__(self, path: Path, user: str = "op", password: str = "right", info: str = "Welcome",
                 delay: float = 0.0):
        self.path, self.user, self.password, self.info = str(path), user, password, info
        self.delay = delay
        self.requests: list[dict] = []
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.path)
        self.server.listen(4)
        threading.Thread(target=self._serve, daemon=True).start()

    def started(self) -> list[dict]:
        return [r for r in self.requests if r.get("type") == "start_session"]

    def close(self):
        self.server.close()

    @staticmethod
    def _read(conn, n):
        out = b""
        while len(out) < n:
            chunk = conn.recv(n - len(out))
            if not chunk:
                raise EOFError
            out += chunk
        return out

    def _serve(self):
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            threading.Thread(target=self._talk, args=(conn,), daemon=True).start()

    def _talk(self, conn):
        user, step = None, 0
        with conn:
            while True:
                try:
                    (size,) = struct.unpack("=I", self._read(conn, 4))
                    req = json.loads(self._read(conn, size))
                except (EOFError, OSError, ValueError):
                    return
                self.requests.append(req)
                kind = req.get("type")
                if kind == "create_session":
                    user, step = req.get("username"), 1
                    reply = {"type": "auth_message", "auth_message_type": "info", "auth_message": self.info}
                elif kind == "post_auth_message_response" and step == 1:
                    step = 2
                    reply = {"type": "auth_message", "auth_message_type": "secret", "auth_message": "Password:"}
                elif kind == "post_auth_message_response" and step == 2:
                    time.sleep(self.delay)
                    step = 3 if (user == self.user and req.get("response") == self.password) else 0
                    reply = {"type": "success"} if step == 3 else \
                        {"type": "error", "error_type": "auth_error", "description": "pam_authenticate: AUTH_ERR"}
                elif kind == "start_session" and step == 3:
                    reply = {"type": "success"}
                elif kind == "cancel_session":
                    step, reply = 0, {"type": "success"}
                else:
                    reply = {"type": "error", "error_type": "error", "description": f"unexpected {kind}"}
                data = json.dumps(reply).encode()
                conn.sendall(struct.pack("=I", len(data)) + data)
