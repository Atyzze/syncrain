"""Shared fixtures: the tree, the build, and the environments the lanes need.

A lane that needs something this machine lacks (a display, a browser, Nix) skips with the reason,
unless SYNCRAIN_REQUIRE_ALL=1, which `tools/test_suite.py --require-all` sets for the release:
then a missing environment fails, because a test that skips on the release machine never ran.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REQUIRE_ALL = os.environ.get("SYNCRAIN_REQUIRE_ALL") == "1"
sys.path.insert(0, str(ROOT))


def need(ok: bool, what: str) -> None:
    """Skip without `what`, or fail when the release requires every lane."""
    if ok:
        return
    if REQUIRE_ALL:
        pytest.fail(f"{what} (SYNCRAIN_REQUIRE_ALL=1: the release runs every lane)")
    pytest.skip(what)


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def build_number() -> int:
    return int((ROOT / "BUILD_NUMBER").read_text(encoding="utf-8").strip())


def _free_display() -> int:
    for n in range(91, 130):
        if not Path(f"/tmp/.X11-unix/X{n}").exists() and not Path(f"/tmp/.X{n}-lock").exists():
            return n
    raise RuntimeError("no free X display number between :91 and :129")


@pytest.fixture(scope="session")
def x_display():
    """An X server for the render lane: SYNCRAIN_TEST_DISPLAY if given, else a private Xvfb."""
    given = os.environ.get("SYNCRAIN_TEST_DISPLAY")
    if given:
        yield given
        return
    xvfb = shutil.which("Xvfb")
    need(xvfb is not None, "no Xvfb to draw into (install xorg-server-xvfb / xvfb, or set SYNCRAIN_TEST_DISPLAY)")
    n = _free_display()
    proc = subprocess.Popen([xvfb, f":{n}", "-screen", "0", "1920x1080x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.monotonic() + 15
    while not Path(f"/tmp/.X11-unix/X{n}").exists():
        if proc.poll() is not None or time.monotonic() > deadline:
            proc.kill()
            pytest.fail(f"Xvfb :{n} did not start")
        time.sleep(0.1)
    try:
        yield f":{n}"
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def native_build_tools() -> str | None:
    """What building the native wallpaper lacks here, or None (syncrain/native/build.sh's needs)."""
    for tool in (os.environ.get("CC", "cc"), "pkg-config"):
        if not shutil.which(tool):
            return f"no {tool}"
    if not shutil.which("wayland-scanner"):
        probe = subprocess.run(["pkg-config", "--variable=wayland_scanner", "wayland-scanner"], capture_output=True,
                               text=True)
        if probe.returncode != 0 or not probe.stdout.strip():
            return "no wayland-scanner"
    for lib in ("wayland-client", "wayland-egl", "dbus-1"):
        if subprocess.run(["pkg-config", "--exists", lib]).returncode != 0:
            return f"no {lib} headers (pkg-config {lib})"
    return None


@pytest.fixture(scope="session")
def native_wallpaper(tmp_path_factory):
    """The native wallpaper built from this tree, and SYNCRAIN_WALLPAPER naming it for every process
    the tests start from here on, so `python -m syncrain` on a Wayland session draws with it."""
    missing = native_build_tools()
    need(missing is None, f"the native wallpaper cannot be built here: {missing}")
    out = tmp_path_factory.mktemp("native") / "syncrain-wallpaper"
    done = subprocess.run(["sh", str(ROOT / "syncrain" / "native" / "build.sh"), str(out)], capture_output=True,
                          text=True, timeout=600)
    assert done.returncode == 0, f"the native wallpaper did not build:\n{done.stdout[-2000:]}{done.stderr[-4000:]}"
    before = os.environ.get("SYNCRAIN_WALLPAPER")
    os.environ["SYNCRAIN_WALLPAPER"] = str(out)
    yield out
    if before is None:
        os.environ.pop("SYNCRAIN_WALLPAPER", None)
    else:
        os.environ["SYNCRAIN_WALLPAPER"] = before


def app_env(display: str, **extra: str) -> dict:
    """The environment the app runs in for a test: X11 on the given display, nothing inherited
    that would steer GTK's choice of OpenGL, so each case sets exactly what it tests."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("WAYLAND_DISPLAY", "GDK_DEBUG", "GDK_DISABLE", "GSK_RENDERER", "PYOPENGL_PLATFORM",
                        "SYNCRAIN_REEXEC", "LD_PRELOAD")}
    env.update(DISPLAY=display, GDK_BACKEND="x11", PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(ROOT))
    env.update(extra)
    return env


def run_app(args: list[str], env: dict, timeout: float = 120) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "syncrain", *args], cwd=ROOT, env=env, text=True,
                          capture_output=True, timeout=timeout)


@pytest.fixture
def app(x_display):
    """Run the app against the test display: app(args, **env) -> CompletedProcess."""
    def _run(args, timeout=120, **extra):
        return run_app(list(args), app_env(x_display, **extra), timeout=timeout)
    return _run

