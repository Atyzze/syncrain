"""The login screen (build 16) end to end, as greetd runs it: syncrain/login/login.sh starts KWin
(headless here, two screens), the rain draws, the box comes up, a wrong password and then the right
one are typed, and greetd (a stand-in on its socket, tests/fake_greetd.py) is asked to start Plasma
with the environment SDDM gives it. On the operator's desktop KWin takes the graphics card (--drm)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

from tests.conftest import ROOT
from tests.fake_greetd import FakeGreetd
from tests.kwin.test_the_kwin_desktop import needs

PLASMA = "/usr/lib/plasma-dbus-run-session-if-needed /usr/bin/startplasma-wayland"


def sessions(share):
    folder = share / "wayland-sessions"
    folder.mkdir(parents=True)
    (folder / "plasma.desktop").write_text(f"[Desktop Entry]\nExec={PLASMA}\nDesktopNames=KDE\nName=Plasma (Wayland)\n")
    (folder / "sway.desktop").write_text("[Desktop Entry]\nExec=sway\nDesktopNames=sway;wlroots\nName=Sway\n")
    (folder / "gone.desktop").write_text("[Desktop Entry]\nExec=gone\nTryExec=/nonexistent/gone\nName=Gone\n")


def run_login(tmp_path, typed):
    """login.sh as greetd runs it, KWin headless with two screens; (exit status, log, greetd stand-in)."""
    needs()
    kwin = os.environ.get("SYNCRAIN_KWIN") or shutil.which("kwin_wayland")
    run = tmp_path / "run"
    run.mkdir(mode=0o700)
    sessions(tmp_path / "share")
    (tmp_path / "login.json").write_text(json.dumps({"user": "op", "rain": ["--theme", "matrix", "--fps", "10"]}))
    greetd = FakeGreetd(tmp_path / "greetd.sock")
    text = tmp_path / "text-login"
    text.write_text(f"#!/bin/sh\necho \"$@\" > {tmp_path}/text-login.ran\n")
    text.chmod(0o755)
    env = {k: v for k, v in os.environ.items()
           if k not in ("DISPLAY", "WAYLAND_DISPLAY", "LD_PRELOAD", "SYNCRAIN_REEXEC", "DBUS_SESSION_BUS_ADDRESS",
                        "GDK_BACKEND", "XDG_CURRENT_DESKTOP")}
    env.update(XDG_RUNTIME_DIR=str(run), HOME=str(tmp_path / "home"), GREETD_SOCK=greetd.path,
               XDG_DATA_DIRS=str(tmp_path / "share"), SYNCRAIN_LOGIN_CONFIG=str(tmp_path / "login.json"),
               SYNCRAIN_LOGIN_STATE=str(tmp_path / "state"), SYNCRAIN_LOGIN_KWIN=kwin,
               SYNCRAIN_LOGIN_KWIN_ARGS="--virtual --width 320 --height 180 --output-count 2 --no-lockscreen "
                                        "--no-global-shortcuts --no-kactivities --socket wayland-login",
               SYNCRAIN_LOGIN_TEXT=str(text), SYNCRAIN_DEBUG_FPS="1", GTK_A11Y="none",
               SYNCRAIN_PYTHON=sys.executable, SYNCRAIN_GREETER_TEST_INPUT=json.dumps(typed))
    try:
        done = subprocess.run(["sh", str(ROOT / "syncrain" / "login" / "login.sh")], env=env, cwd=tmp_path,
                              capture_output=True, text=True, timeout=180)
    finally:
        greetd.close()
    log = (tmp_path / "state" / "login.log").read_text()
    assert done.returncode == 0, f"{done.stdout}{done.stderr}\n{log[-4000:]}"
    return log, greetd


def test_a_login_through_the_box_starts_plasma(tmp_path, native_wallpaper):
    log, greetd = run_login(tmp_path, [{"password": "wrong", "wait": 4}, {"password": "right"}])
    assert not (tmp_path / "text-login.ran").exists(), log[-4000:]
    assert re.search(r"syncrain-login: [0-9:.]+ rain started", log)
    assert re.search(r"syncrain-login: [0-9:.]+ box shown", log)
    assert "native wallpaper, 2 screens" in log, f"the rain never drew:\n{log[-4000:]}"
    assert re.search(r"syncrain-login: [0-9:.]+ not logged in: Welcome / Wrong password", log)
    assert greetd.started() == [{"type": "start_session", "cmd": PLASMA.split(),
                                 "env": ["XDG_SESSION_TYPE=wayland", "XDG_SESSION_DESKTOP=KDE",
                                         "XDG_CURRENT_DESKTOP=KDE"]}]
    assert {"type": "cancel_session"} in greetd.requests
    assert json.loads((tmp_path / "state" / "last.json").read_text()) == {"user": "op", "session": "plasma.desktop"}
    assert (tmp_path / "state" / "logged-in").read_text() == "plasma.desktop\n"


def test_text_login_in_the_box_hands_over_to_greetd_s_own(tmp_path, native_wallpaper):
    log, greetd = run_login(tmp_path, [{"text": True, "wait": 1}])
    assert re.search(r"syncrain-login: [0-9:.]+ text login asked for", log), log[-4000:]
    assert not greetd.started()
    assert (tmp_path / "text-login.ran").read_text().startswith("--cmd env XDG_SESSION_TYPE=wayland")
