"""The app itself, on a real X display (a private Xvfb unless SYNCRAIN_TEST_DISPLAY is set).

The first case is the operator's report on build 2, replayed: with only OpenGL ES on offer (what
GTK 4.14 and later hand out by default, and all that a driver refusing to share contexts across
the two APIs leaves), build 2 found no context and left a grey screen behind.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

import pytest

from syncrain import build
from tests.conftest import app_env
from tests.support import GL_NONE, GL_ONLY_DESKTOP, GL_ONLY_ES, MOMENT, brightness, mean_abs_diff

CASES = {"whatever GTK prefers": ({}, None), "OpenGL ES only": (GL_ONLY_ES, "OpenGL ES "),
         "desktop OpenGL only": (GL_ONLY_DESKTOP, "OpenGL ")}


@pytest.mark.parametrize("case", list(CASES))
def test_it_draws_with_whatever_opengl_gtk_offers(app, tmp_path, case):
    env, api = CASES[case]
    shot = tmp_path / "frame.png"
    done = app(["--window", "--size", "960x540", "--time", str(MOMENT), "--screenshot", str(shot)], **env)
    assert done.returncode == 0, done.stdout + done.stderr
    started = next((line for line in done.stdout.splitlines() if line.startswith(build.describe() + ":")), "")
    assert started, f"no startup line in {done.stdout!r}"
    if api == "OpenGL ":
        assert ": OpenGL " in started and "OpenGL ES" not in started, started
    elif api:
        assert api in started, started
    assert brightness(shot) > 5, "the frame is black"


def test_es_and_desktop_opengl_draw_the_same_frame(app, tmp_path):
    shots = {}
    for name, env in (("es", GL_ONLY_ES), ("gl", GL_ONLY_DESKTOP)):
        shots[name] = tmp_path / f"{name}.png"
        done = app(["--window", "--size", "960x540", "--time", str(MOMENT), "--screenshot", str(shots[name])], **env)
        assert done.returncode == 0, done.stderr
    assert mean_abs_diff(shots["es"], shots["gl"]) < 0.5


def test_without_opengl_it_gives_the_desktop_back_at_once(app):
    started = time.monotonic()
    done = app(["--window"], timeout=90, **GL_NONE)
    assert done.returncode == 69, done.stdout + done.stderr
    assert done.stderr.count("nothing can be drawn") == 1, done.stderr
    assert "syncrain --diagnose" in done.stderr
    assert time.monotonic() - started < 60


def test_as_an_x11_wallpaper_it_covers_the_screen(app, tmp_path):
    shot = tmp_path / "desktop.png"
    done = app(["--time", str(MOMENT), "--screenshot", str(shot)])
    assert done.returncode == 0, done.stderr
    assert "1 screen" in done.stdout and "(1920x1080)" in done.stdout, done.stdout


def test_the_same_moment_draws_the_same_frame_and_the_next_one_differs(app, tmp_path):
    a, b, c = (tmp_path / f"{n}.png" for n in "abc")
    for path, moment in ((a, MOMENT), (b, MOMENT), (c, MOMENT + 1)):
        assert app(["--window", "--size", "640x360", "--time", str(moment), "--screenshot", str(path)]).returncode == 0
    assert mean_abs_diff(a, b) == 0
    assert mean_abs_diff(a, c) > 0.2


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
def test_ctrl_c_and_a_service_stop_end_it_cleanly(x_display, root, sig):
    """Build 2 printed a KeyboardInterrupt traceback on Ctrl+C."""
    proc = subprocess.Popen([sys.executable, "-m", "syncrain", "--window", "--size", "320x180"], cwd=root,
                            env=app_env(x_display), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + 60
    line = ""
    while time.monotonic() < deadline and not line.startswith("syncrain build"):
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
    assert line.startswith("syncrain build"), proc.stderr.read()
    time.sleep(1.0)
    os.kill(proc.pid, sig)
    out, err = proc.communicate(timeout=30)
    assert proc.returncode == 0, err
    assert "Traceback" not in err, err


FAILING_FRAME = """
import sys
from syncrain import renderer
real = renderer.Renderer.render
calls = [0]
def render(self, *a, **k):
    calls[0] += 1
    if calls[0] == 5:
        raise RuntimeError("a frame that fails, on purpose")
    return real(self, *a, **k)
renderer.Renderer.render = render
from syncrain.app import main
sys.exit(main(["--window", "--size", "320x180"]))
"""


def test_a_frame_that_fails_does_not_stop_the_wallpaper(x_display, root):
    """Each frame asks for the next one (syncrain/pacing.py); a frame that raises must still ask,
    or the wallpaper would stand still for good."""
    proc = subprocess.Popen([sys.executable, "-c", FAILING_FRAME], cwd=root,
                            env=app_env(x_display, SYNCRAIN_DEBUG_FPS="1"), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    try:
        time.sleep(8)
    finally:
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=30)
    assert "a frame that fails, on purpose" in err, err
    reports = [line for line in out.splitlines() if " fps at 320x180" in line]
    assert len(reports) >= 4 and float(reports[-1].split()[1]) > 5, out


def test_diagnose_says_what_it_found(app):
    done = app(["--diagnose"])
    assert done.returncode == 0, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    assert lines[0] == f"{build.describe()} --diagnose"
    assert lines[1].startswith("verdict: OK, syncrain can draw here (OpenGL"), lines[1]
    assert "GTK hands out: OpenGL" in done.stdout and "test frame: 640x360" in done.stdout


def test_diagnose_without_opengl_says_so_first(app):
    done = app(["--diagnose"], **GL_NONE)
    assert done.returncode == 69
    assert done.stdout.splitlines()[1].startswith("verdict: no OpenGL context:"), done.stdout
