"""The wallpaper on Wayland: a layer-shell surface in a headless Sway, looked at with grim.

This is the path the operator's desktop takes (KDE Plasma is Wayland; it gets the bottom layer).
It is drawn by the native wallpaper (syncrain/native/), which this lane builds, and by the GTK host
with --host gtk; both must draw the same frame. Needs sway, grim, gtk4-layer-shell's typelib where
the test Python finds it (GI_TYPELIB_PATH) and what the native build needs
(`docs/agent/ENVIRONMENT.md`). The compositor's empty screen is taken first, so "the desktop is
given back" can be checked against what this compositor shows when nothing covers it.
"""
from __future__ import annotations

import json
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
from tests.support import (GL_NONE, GL_ONLY_ES, MOMENT, brightness, grab, grab_settled, headless_sway,
                           mean_abs_diff, said_when_stopped)


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
        assert line.startswith(build.describe() + ":") and "1 screen" in line, line + said_when_stopped(proc)
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


SYMBOLS = '{"balance": "glyphs", "sets": [{"name": "a", "chars": "Ж★ΩअДあ", "weight": 2}, {"name": "b", "chars": "𓆙λ", "share": 0.3}]}'


@pytest.mark.parametrize("look", [[], ["--speed", "2", "--density", "0.5", "--glow", "0", "--bloom", "1.5",
                                        "--bg-gain", "0.5", "--snow", "off", "--hieroglyphs", "1"], ["--glyphs"],
                                  ["--logo"]],
                         ids=["defaults", "every-option", "a-symbols-file", "a-look-of-one-s-own"])
def test_the_native_wallpaper_draws_the_gtk_host_s_frame(root, sway, tmp_path, look):
    """The same moment, drawn by each host on the same screen, is the same picture to the pixel."""
    session, empty = sway
    if look == ["--glyphs"]:
        (tmp_path / "glyphs.json").write_text(SYMBOLS, encoding="utf-8")
        look = ["--glyphs", str(tmp_path / "glyphs.json")]
    if look == ["--logo"]:                    # colours, flavours, a picture as the logo, words of one's own
        from PIL import Image, ImageDraw
        picture = Image.new("RGBA", (300, 200), (0, 0, 0, 0))
        ImageDraw.Draw(picture).ellipse((20, 20, 180, 180), fill=(230, 60, 40, 255))
        picture.save(tmp_path / "picture.png")
        look = ["--preset", "matrix", "--rain-colors", "#202040,#8040c0,0.9/0.7/1,#ffffff", "--flavours", "9",
                "--flavour-layout", "wave", "--cycle", "30", "--logo", str(tmp_path / "picture.png"),
                "--logo-size", "0.3", "--background-colors", "#050008,#0a0010,#200838", "--vignette", "0.2",
                "--words", "HELLO,SYNC", "--glow-color", "#6030a0", "--logo-color", "#ffaa33"]
    shots = {}
    for host in ("native", "gtk"):
        proc, line = start(root, wallpaper_env(root, session), "--time", str(MOMENT), "--host",
                           "auto" if host == "native" else "gtk", *look)
        try:
            assert HOSTS[host] in line, line + said_when_stopped(proc)
            shots[host] = tmp_path / f"{host}.png"
            grab_settled(session, shots[host], unlike=empty)
        finally:
            proc.send_signal(signal.SIGTERM)
            proc.communicate(timeout=30)
    assert mean_abs_diff(shots["native"], shots["gtk"]) == 0


@pytest.mark.parametrize("scale", [1.25, 2], ids=["fractional-1.25", "double"])
def test_a_scaled_screen_shows_the_frame_a_scale_of_one_does(root, sway, tmp_path, scale):
    """A screen at 1.25 or 2 has as many pixels as one at 1 here (1280x720), so it shows the same
    frame: drawn at the screen's own pixels, not scaled up from fewer (or, as once at a fractional
    scale after an integer one, scaled twice). The native wallpaper (Wayland's default) to the pixel,
    against itself at 1; the GTK host to the pixel at a whole scale, and at a fractional one within a
    level (GtkGLArea's framebuffer follows the next whole scale, to GTK 4.22 at least, and Sway
    scales it down; the GTK host draws the screen's own pixels into it)."""
    session, empty = sway
    shots = {}
    with headless_sway(tmp_path / "run", scale=scale) as scaled:
        empty_scaled = tmp_path / "empty-scaled.png"
        grab(scaled, empty_scaled)
        for where, s, blank in (("one", session, empty), ("scaled", scaled, empty_scaled)):
            for host in ("native", "gtk") if where == "scaled" else ("native",):
                proc, line = start(root, wallpaper_env(root, s), "--time", str(MOMENT), "--host",
                                   "auto" if host == "native" else "gtk")
                try:
                    assert HOSTS[host] in line, line + said_when_stopped(proc)
                    shots[where, host] = tmp_path / f"{where}-{host}.png"
                    grab_settled(s, shots[where, host], unlike=blank)
                finally:
                    proc.send_signal(signal.SIGTERM)
                    proc.communicate(timeout=30)
    from PIL import Image
    assert Image.open(shots["scaled", "native"]).size == (1280, 720)
    assert mean_abs_diff(shots["scaled", "native"], shots["one", "native"]) == 0
    if scale == int(scale):
        assert mean_abs_diff(shots["scaled", "gtk"], shots["one", "native"]) == 0
    else:
        # the compositor still shrinks GtkGLArea's framebuffer (a whole scale's) to the screen; the
        # frame in it is the screen's, each pixel blown up whole, so that lands within a level (2.6 before)
        assert mean_abs_diff(shots["scaled", "gtk"], shots["one", "native"]) < 0.5


def test_the_native_wallpaper_keeps_neither_python_nor_gtk(root, sway):
    """syncrain replaces its own process with the native program: the pid stays, the interpreter and
    the toolkit go."""
    session, _ = sway
    proc, line = start(root, wallpaper_env(root, session))
    try:
        assert HOSTS["native"] in line, line + said_when_stopped(proc)
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
            assert line.startswith(build.describe() + ":") and HOSTS[host] in line, line + said_when_stopped(proc)

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
            assert HOSTS[host] in line, line + said_when_stopped(proc)
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
            assert HOSTS["native"] in line, line + said_when_stopped(proc)
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
            assert HOSTS[host] in line, line + said_when_stopped(proc)
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
            assert HOSTS["native"] in line, line + said_when_stopped(proc)
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


def test_a_screen_that_never_draws_holds_no_memory_back(root, tmp_path):
    """One of two screens is off before the wallpaper starts (sway never asks it for a second frame):
    the other hands memory back after its first frames, and the trims go on every few minutes (here
    half a second), as the record shows."""
    need(shutil.which("sway") is not None and shutil.which("swaymsg") is not None, "no sway and swaymsg")
    state = tmp_path / "state"
    with headless_sway(tmp_path / "run", screen="320x180") as session:
        sway_env = dict(os.environ, **session)
        subprocess.run(["swaymsg", "-q", "create_output"], env=sway_env, check=True)
        outputs = json.loads(subprocess.run(["swaymsg", "-r", "-t", "get_outputs"], env=sway_env, check=True,
                                            capture_output=True, text=True).stdout)
        subprocess.run(["swaymsg", "-q", "output", outputs[-1]["name"], "power", "off"], env=sway_env, check=True)
        env = wallpaper_env(root, session, SYNCRAIN_MEMORY_SECONDS="0.5", XDG_STATE_HOME=str(state))
        proc, line = start(root, env)
        record = state / "syncrain" / "memory.log"
        try:
            assert HOSTS["native"] in line and "2 screens" in line, line + said_when_stopped(proc)
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline and len(record.read_text().splitlines() if record.exists() else []) < 2:
                time.sleep(0.5)
            assert len(record.read_text().splitlines() if record.exists() else []) >= 2, "no trims"
        finally:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=30)
    assert proc.returncode == 0


def test_opengl_made_anew_gives_the_driver_s_memory_back_and_keeps_the_picture(root, tmp_path):
    """NVIDIA's driver (615.71.09, 615.78.08) keeps about 16 bytes for every sync object it makes, and
    it makes them inside eglSwapBuffers; only eglTerminate gives them back: the operator's wallpaper
    grew about 6 MiB an hour that way. Once the C heap holds 32 MiB more than it did when the screens
    had drawn, the native wallpaper gives back everything EGL holds and makes it anew between two
    frames, on the same Wayland surfaces, from the shaders' kept sources and the textures read back
    from the card. Here (SYNCRAIN_RENEW_MIB=0) that happens every round, each second, on two screens
    with the clock still: every grab, before, during and after, is the first one to the pixel, and
    the record has each renewal and the heap once the new context has drawn. A screen plugged in
    after renewals gets its surface from the new context, and the renewals go on."""
    need(shutil.which("sway") is not None and shutil.which("grim") is not None and shutil.which("swaymsg") is not None,
         "no sway, grim and swaymsg")
    state = tmp_path / "state"
    with headless_sway(tmp_path / "run", screen="320x180") as session:
        sway_env = dict(os.environ, **session)
        subprocess.run(["swaymsg", "-q", "create_output"], env=sway_env, check=True)
        env = wallpaper_env(root, session, SYNCRAIN_MEMORY_SECONDS="1", SYNCRAIN_RENEW_MIB="0",
                            XDG_STATE_HOME=str(state))
        proc, line = start(root, env, "--time", str(MOMENT))
        record = state / "syncrain" / "memory.log"

        def lines(word):
            return [text for text in (record.read_text().splitlines() if record.exists() else []) if word in text]

        try:
            assert HOSTS["native"] in line and "2 screens" in line, line + said_when_stopped(proc)
            first = tmp_path / "first.png"
            grab_settled(session, first)
            grabs = 0
            deadline = time.monotonic() + 60
            while len(lines("after renewal")) < 3 and time.monotonic() < deadline:
                shot = tmp_path / "shot.png"
                grab(session, shot)
                grabs += 1
                assert mean_abs_diff(shot, first) == 0, f"grab {grabs} is not the first frame: {lines('renewal')}"
            made, judged = lines("OpenGL made anew"), lines("after renewal")
            assert len(judged) >= 3, record.read_text() if record.exists() else "no record"
            assert all(re.search(r"OpenGL made anew in \d+ ms \(renewal \d+\): malloc [\d.]+ MiB in use "
                                 r"\(-?[\d.]+ grown before\); [\d.]+ MiB resident \([\d.]+ before\)$", text)
                       for text in made), made
            assert all(re.search(r"after renewal \d+, drawing again: malloc [\d.]+ MiB in use \([\d.]+ once the "
                                 r"screens had first drawn\)$", text) for text in judged), judged
            subprocess.run(["swaymsg", "-q", "create_output"], env=sway_env, check=True)
            before = len(judged)
            deadline = time.monotonic() + 60
            while len(lines("after renewal")) < before + 3 and time.monotonic() < deadline:
                time.sleep(0.5)
            assert len(lines("after renewal")) >= before + 3 and proc.poll() is None, record.read_text()
            assert not lines("no more renewals") and not lines("could not"), record.read_text()
        finally:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=30)
    assert proc.returncode == 0
