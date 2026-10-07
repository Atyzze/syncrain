"""The wallpaper on Wayland: a layer-shell surface in a headless Sway, looked at with grim.

This is the path the operator's desktop takes (KDE Plasma is Wayland; it gets the bottom layer).
Needs sway, grim and gtk4-layer-shell's typelib where the test Python finds it (GI_TYPELIB_PATH;
`docs/agent/ENVIRONMENT.md`). The compositor's empty screen is taken first, so "the desktop is
given back" can be checked against what this compositor shows when nothing covers it.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time

import pytest

from syncrain import build
from tests.conftest import need
from tests.support import GL_NONE, GL_ONLY_ES, brightness, mean_abs_diff


@pytest.fixture(scope="module")
def sway(tmp_path_factory, root):
    need(shutil.which("sway") is not None and shutil.which("grim") is not None, "no sway and grim for a Wayland session")
    probe = subprocess.run([sys.executable, "-c", "import gi; gi.require_version('Gtk4LayerShell', '1.0')"],
                           capture_output=True, text=True)
    need(probe.returncode == 0, "gtk4-layer-shell's typelib is not importable (set GI_TYPELIB_PATH)")
    run = tmp_path_factory.mktemp("xdg")
    run.chmod(0o700)
    (run / "sway.conf").write_text("output HEADLESS-1 resolution 1280x720\ndefault_border none\n")
    env = dict(os.environ, XDG_RUNTIME_DIR=str(run), WLR_BACKENDS="headless", WLR_LIBINPUT_NO_DEVICES="1",
               WLR_RENDERER="pixman")
    env.pop("WAYLAND_DISPLAY", None)
    env.pop("DISPLAY", None)
    proc = subprocess.Popen(["sway", "-c", str(run / "sway.conf")], env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.monotonic() + 20
    while not list(run.glob("wayland-*[0-9]")):
        if proc.poll() is not None or time.monotonic() > deadline:
            proc.kill()
            pytest.fail("headless sway did not start")
        time.sleep(0.1)
    socket = sorted(p.name for p in run.glob("wayland-*[0-9]"))[0]
    session = {"XDG_RUNTIME_DIR": str(run), "WAYLAND_DISPLAY": socket}
    empty = run / "empty.png"
    grab(session, empty)
    try:
        yield session, empty
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def grab(session, path):
    subprocess.run(["grim", str(path)], env=dict(os.environ, **session), check=True, timeout=30)


def wallpaper_env(root, session, **extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("DISPLAY", "GDK_DEBUG", "GDK_DISABLE", "LD_PRELOAD", "SYNCRAIN_REEXEC", "PYOPENGL_PLATFORM")}
    env.update(session, GDK_BACKEND="wayland", PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE="1",
               XDG_CURRENT_DESKTOP="sway")
    env.update(extra)
    return env


def start(root, env, *args):
    proc = subprocess.Popen([sys.executable, "-m", "syncrain", *args], cwd=root, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.monotonic() + 60
    line = ""
    while time.monotonic() < deadline and not line.startswith("syncrain build"):
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
    return proc, line


@pytest.mark.parametrize("extra, args", [({}, []), (GL_ONLY_ES, []), ({}, ["--layer", "bottom"])],
                         ids=["default", "opengl-es-only", "bottom-layer"])
def test_the_wallpaper_is_on_screen_and_stops_cleanly(root, sway, tmp_path, extra, args):
    session, empty = sway
    proc, line = start(root, wallpaper_env(root, session, **extra), *args)
    try:
        assert line.startswith(build.describe() + ":") and "1 screen" in line, line + proc.stderr.read()
        time.sleep(2.0)
        shot = tmp_path / "screen.png"
        grab(session, shot)
        assert mean_abs_diff(shot, empty) > 5, "the screen still shows the empty compositor"
        assert 5 < brightness(shot) < 100, f"not the night-sky rain: brightness {brightness(shot):.1f}"
    finally:
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=30)
    assert proc.returncode == 0 and "Traceback" not in err, err


def test_without_opengl_the_desktop_is_given_back(root, sway, tmp_path):
    session, empty = sway
    done = subprocess.run([sys.executable, "-m", "syncrain"], cwd=root, env=wallpaper_env(root, session, **GL_NONE),
                          capture_output=True, text=True, timeout=90)
    assert done.returncode == 69, done.stdout + done.stderr
    after = tmp_path / "after.png"
    grab(session, after)
    assert mean_abs_diff(after, empty) < 1, "something is still covering the desktop"
