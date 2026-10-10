"""The wallpaper on Wayland: a layer-shell surface in a headless Sway, looked at with grim.

This is the path the operator's desktop takes (KDE Plasma is Wayland; it gets the bottom layer).
It is drawn by the native wallpaper (syncrain/native/), which this lane builds, and by the GTK host
with --host gtk; both must draw the same frame. Needs sway, grim, gtk4-layer-shell's typelib where
the test Python finds it (GI_TYPELIB_PATH) and what the native build needs
(`docs/agent/ENVIRONMENT.md`). The compositor's empty screen is taken first, so "the desktop is
given back" can be checked against what this compositor shows when nothing covers it.
"""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from syncrain import build
from tests.conftest import need
from tests.support import GL_NONE, GL_ONLY_ES, MOMENT, brightness, grab, headless_sway, mean_abs_diff


@pytest.fixture(autouse=True, scope="module")
def native(native_wallpaper):
    """Every syncrain this lane starts finds the native wallpaper (SYNCRAIN_WALLPAPER)."""
    return native_wallpaper


#: What the startup line names as the host: the native wallpaper, or GTK's renderer.
HOSTS = {"native": ", native wallpaper, ", "gtk": ", GTK renderer "}


@pytest.fixture(scope="module")
def sway(tmp_path_factory, root):
    need(shutil.which("sway") is not None and shutil.which("grim") is not None, "no sway and grim for a Wayland session")
    probe = subprocess.run([sys.executable, "-c", "import gi; gi.require_version('Gtk4LayerShell', '1.0')"],
                           capture_output=True, text=True)
    need(probe.returncode == 0, "gtk4-layer-shell's typelib is not importable (set GI_TYPELIB_PATH)")
    with headless_sway(tmp_path_factory.mktemp("sway") / "run") as session:
        empty = Path(session["XDG_RUNTIME_DIR"]) / "empty.png"
        grab(session, empty)
        yield session, empty


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


@pytest.mark.parametrize("extra, args, host", [({}, [], "native"), (GL_ONLY_ES, [], "native"),
                                               ({}, ["--layer", "bottom"], "native"), ({}, ["--host", "gtk"], "gtk"),
                                               (GL_ONLY_ES, ["--host", "gtk"], "gtk")],
                         ids=["default", "opengl-es-only", "bottom-layer", "gtk-host", "gtk-host-opengl-es-only"])
def test_the_wallpaper_is_on_screen_and_stops_cleanly(root, sway, tmp_path, extra, args, host):
    session, empty = sway
    proc, line = start(root, wallpaper_env(root, session, **extra), *args)
    try:
        assert line.startswith(build.describe() + ":") and "1 screen" in line, line + proc.stderr.read()
        assert HOSTS[host] in line, line
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
    """The native wallpaper finds no OpenGL and hands over to the GTK host, which finds none either."""
    session, empty = sway
    done = subprocess.run([sys.executable, "-m", "syncrain"], cwd=root, env=wallpaper_env(root, session, **GL_NONE),
                          capture_output=True, text=True, timeout=90)
    assert done.returncode == 69, done.stdout + done.stderr
    assert "the GTK host takes over" in done.stderr and done.stderr.count("nothing can be drawn") == 1, done.stderr
    after = tmp_path / "after.png"
    grab(session, after)
    assert mean_abs_diff(after, empty) < 1, "something is still covering the desktop"


@pytest.mark.parametrize("look", [[], ["--speed", "2", "--density", "0.5", "--glow", "0", "--bloom", "1.5",
                                        "--bg-gain", "0.5", "--snow", "off", "--hieroglyphs", "1"]],
                         ids=["defaults", "every-option"])
def test_the_native_wallpaper_draws_the_gtk_host_s_frame(root, sway, tmp_path, look):
    """The same moment, drawn by each host on the same screen, is the same picture to the pixel."""
    session, _ = sway
    shots = {}
    for host in ("native", "gtk"):
        proc, line = start(root, wallpaper_env(root, session), "--time", str(MOMENT), "--host",
                           "auto" if host == "native" else "gtk", *look)
        try:
            assert HOSTS[host] in line, line + proc.stderr.read()
            time.sleep(2.0)
            shots[host] = tmp_path / f"{host}.png"
            grab(session, shots[host])
        finally:
            proc.send_signal(signal.SIGTERM)
            proc.communicate(timeout=30)
    assert mean_abs_diff(shots["native"], shots["gtk"]) == 0


def test_the_native_wallpaper_keeps_neither_python_nor_gtk(root, sway):
    """syncrain replaces its own process with the native program: the pid stays, the interpreter and
    the toolkit go."""
    session, _ = sway
    proc, line = start(root, wallpaper_env(root, session))
    try:
        assert HOSTS["native"] in line, line + proc.stderr.read()
        exe = os.path.basename(os.readlink(f"/proc/{proc.pid}/exe"))
        maps = open(f"/proc/{proc.pid}/maps", encoding="utf-8", errors="replace").read()
        assert exe == "syncrain-wallpaper", exe
        assert "libpython" not in maps and "libgtk-4" not in maps and "gtk4-layer-shell" not in maps
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.communicate(timeout=30)
    assert proc.returncode == 0


def resident_mib(pid):
    with open(f"/proc/{pid}/status", encoding="ascii") as fh:
        return next(int(line.split()[1]) for line in fh if line.startswith("VmRSS:")) / 1024


@pytest.mark.parametrize("host", ["native", "gtk"])
def test_screens_that_come_and_go_leave_nothing_behind(root, tmp_path, host):
    """A screen unplugged or plugged in (or a DisplayPort screen waking from sleep, which looks the
    same to the compositor) rebuilds every screen's window. Build 7 made a new set of programs and
    textures for each new window and never deleted the old ones, which belong to every context GTK
    shares objects between and so outlive their window: about 120 MiB a change here. Now the shared
    ones are made once and each screen's own are deleted with its window. GTK and Mesa keep some of
    their own after the first change (a bare GTK window with a GLArea keeps more), so that change is
    not counted."""
    need(shutil.which("sway") is not None and shutil.which("swaymsg") is not None, "no sway and swaymsg")
    with headless_sway(tmp_path / "run", screen="320x180") as session:
        proc, line = start(root, wallpaper_env(root, session), "--host", "auto" if host == "native" else "gtk")
        try:
            assert line.startswith(build.describe() + ":") and HOSTS[host] in line, line + proc.stderr.read()

            def plug_and_unplug(n):
                subprocess.run(["swaymsg", "-q", "create_output"], env=dict(os.environ, **session), check=True)
                time.sleep(2.5)
                subprocess.run(["swaymsg", "-q", "output", f"HEADLESS-{n}", "unplug"], env=dict(os.environ, **session),
                               check=True)
                time.sleep(2.5)

            plug_and_unplug(2)
            before = resident_mib(proc.pid)
            for n in (3, 4, 5):
                plug_and_unplug(n)
            grown = resident_mib(proc.pid) - before
            assert grown < 30, f"three screen changes left {grown:.0f} MiB behind (build 7: about 120 MiB each)"
        finally:
            proc.send_signal(signal.SIGTERM)
            out, err = proc.communicate(timeout=30)
        assert proc.returncode == 0 and "Traceback" not in err, err


@pytest.mark.parametrize("host", ["native", "gtk"])
def test_when_the_compositor_goes_the_wallpaper_stops_with_an_error(root, tmp_path, host):
    """A compositor that crashes, or restarts as Plasma's does, takes the wallpaper's connection with
    it. GTK exits with status 1 then, and the native wallpaper does the same: the service restarts
    the wallpaper only after a failure, and a status 0 would leave the desktop without it."""
    need(shutil.which("sway") is not None, "no sway")
    with headless_sway(tmp_path / "run", screen="320x180") as session:
        proc, line = start(root, wallpaper_env(root, session), "--host", "auto" if host == "native" else "gtk")
        try:
            assert HOSTS[host] in line, line + proc.stderr.read()
            time.sleep(1.0)
            session.compositor.kill()
            session.compositor.wait(timeout=10)
            _, err = proc.communicate(timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=10)
    assert proc.returncode == 1, (proc.returncode, err)


def native_with_failing_swaps(root, tmp_path, failures, seconds):
    """The native wallpaper on its own small screen, with swaps `failures` ("FIRST:COUNT") failing as
    a driver's can, stopped after `seconds` unless it stops by itself: (exit status, output, errors)."""
    with headless_sway(tmp_path / "run", screen="320x180") as session:
        env = wallpaper_env(root, session, SYNCRAIN_TEST_SWAP_FAILURES=failures, SYNCRAIN_DEBUG_FPS="1")
        proc, line = start(root, env)
        try:
            assert HOSTS["native"] in line, line + proc.stderr.read()
            try:
                proc.wait(timeout=seconds)
            except subprocess.TimeoutExpired:
                proc.send_signal(signal.SIGTERM)
            out, err = proc.communicate(timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=10)
    return proc.returncode, line + out, err


def test_a_frame_the_driver_cannot_show_is_drawn_again(root, tmp_path):
    """A swap that fails (after a resume, or a reset of the card) commits nothing, so no callback
    comes for that frame. The native wallpaper drops what it asked of the compositor for it and draws
    the next frame at its time, instead of waiting for good on a callback that never comes."""
    code, out, err = native_with_failing_swaps(root, tmp_path, "20:10", seconds=5)
    assert code == 0, err
    assert "EGL error 0x3003); the next frame tries again" in err and "frames are shown again" in err, err
    rates = [float(m.group(1)) for m in re.finditer(r"syncrain: ([0-9.]+) fps at", out)]
    assert len(rates) >= 3 and rates[-1] > 20, out           # a report a second, and still at full rate


def test_frames_that_cannot_be_shown_for_seconds_end_it_with_an_error(root, tmp_path):
    """When no frame can be shown for 5 s, the wallpaper stops with status 1, so its service starts
    it afresh, with a new connection to the driver."""
    code, _, err = native_with_failing_swaps(root, tmp_path, "20:1000000", seconds=30)
    assert code == 1, err
    assert "again and again for 5 s; the wallpaper stops with status 1" in err, err


def test_when_the_first_frame_cannot_be_shown_the_gtk_host_draws(root, tmp_path):
    """Before any frame was shown, a swap that fails hands over to the GTK host, as anything else
    that stops the native wallpaper before its first frame does."""
    code, out, err = native_with_failing_swaps(root, tmp_path, "1:1", seconds=8)
    assert code == 0, err
    assert "a frame could not be shown (EGL error 0x3003)" in err and "the GTK host takes over" in err, err
    assert HOSTS["gtk"] in out, out


@pytest.mark.parametrize("host", ["native", "gtk"])
def test_memory_is_handed_back_after_the_first_frames_and_after_a_screen_change(root, tmp_path, host):
    """What starting leaves free in the C heap (the shader compiler's working space above all, much of
    it with a cold shader cache) goes back to the system once every screen has drawn its first
    frames, and again once a new screen has."""
    need(shutil.which("sway") is not None and shutil.which("swaymsg") is not None, "no sway and swaymsg")
    settled = "memory handed back after the first frames"
    with headless_sway(tmp_path / "run", screen="320x180") as session:
        env = wallpaper_env(root, session, SYNCRAIN_DEBUG_FPS="5")
        proc, line = start(root, env, "--host", "auto" if host == "native" else "gtk")
        lines: list[str] = []

        def read():
            for text in iter(proc.stdout.readline, ""):
                lines.append(text)

        threading.Thread(target=read, daemon=True).start()

        def wait_for_settles(count):
            deadline = time.monotonic() + 30
            while sum(settled in text for text in lines) < count and time.monotonic() < deadline:
                time.sleep(0.2)
            return sum(settled in text for text in lines)

        try:
            assert HOSTS[host] in line, line + proc.stderr.read()
            assert wait_for_settles(1) == 1, "".join(lines)
            subprocess.run(["swaymsg", "-q", "create_output"], env=dict(os.environ, **session), check=True)
            assert wait_for_settles(2) == 2, "".join(lines)
        finally:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=30)
    assert proc.returncode == 0


def test_the_native_wallpaper_keeps_a_memory_record_and_trims_as_it_goes(root, tmp_path):
    """Freed memory goes back every few minutes (here half a second), and the record says how it went:
    a line once the first frames are drawn, then one every twelfth time. --diagnose shows the
    running wallpaper with the environment it got, and the record's end."""
    need(shutil.which("sway") is not None, "no sway")
    state = tmp_path / "state"
    with headless_sway(tmp_path / "run", screen="320x180") as session:
        env = wallpaper_env(root, session, SYNCRAIN_MEMORY_SECONDS="0.5", XDG_STATE_HOME=str(state))
        proc, line = start(root, env)
        record = state / "syncrain" / "memory.log"
        try:
            assert HOSTS["native"] in line, line + proc.stderr.read()
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline and len(record.read_text().splitlines() if record.exists() else []) < 2:
                time.sleep(0.5)
            lines = record.read_text().splitlines()
            assert len(lines) >= 2, lines
            assert all(re.search(r"pid \d+, up \d+ min, \d+ frames: [\d.]+ MiB resident \([\d.]+ before handing back\), "
                                 r"malloc [\d.]+ MiB in use$", text) for text in lines), lines
            report = subprocess.run([sys.executable, "-c", "from syncrain import diagnose; "
                                     "print(chr(10).join(diagnose.running_lines()))"],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=60).stdout
            assert re.search(rf"pid {proc.pid}: the native wallpaper, up [\d.]+ h, \d+ MiB resident, "
                             r"__NV_DISABLE_EXPLICIT_SYNC=1, __GL_YIELD=USLEEP", report), report
            assert "memory record (" in report and lines[-1] in report, report
        finally:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=30)
    assert proc.returncode == 0
