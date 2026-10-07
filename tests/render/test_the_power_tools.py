"""The benchmark and the power sweep, run for real on the test display.

The sweep's power comes from a stand-in command here (no graphics card in a test machine); what is
tested is that every phase runs a real wallpaper, the table and the file come out, and nothing is
left running.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time

from syncrain import build, power
from syncrain.power import running_wallpapers
from syncrain.renderer import Renderer
from tests.conftest import app_env


def running_processes():
    """(pid, argv joined) for every process, read the way the sweep reads them."""
    from pathlib import Path
    out = []
    for path in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            argv = [a.decode(errors="replace") for a in path.read_bytes().split(b"\0") if a]
        except OSError:
            continue
        if len(argv) >= 3 and argv[1] == "-m":
            out.append((int(path.parent.name), " ".join(argv)))
    return out


def test_the_benchmark_times_every_pass(app):
    done = app(["--benchmark", "--size", "320x180", "--time", "1791331207"])
    assert done.returncode == 0, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    assert lines[0] == f"{build.describe()} --benchmark"
    assert "320x180, 120 frames, timed by" in lines[1]
    for name in Renderer.PASSES:
        assert any(line.split()[:1] == [name] and float(line.split()[1]) >= 0 for line in lines), name
    assert any(line.startswith("host CPU") for line in lines)


def test_the_startup_line_names_gtk_s_renderer_and_it_is_opengl_by_default(app, tmp_path):
    done = app(["--window", "--size", "320x180", "--screenshot", str(tmp_path / "f.png")])
    assert "GTK renderer gl," in done.stdout, done.stdout


def test_a_power_sweep_runs_every_phase_and_leaves_nothing_behind(x_display, root, tmp_path):
    env = app_env(x_display, SYNCRAIN_POWER_COMMAND="echo 42.5", HOME=str(tmp_path))
    done = subprocess.run([sys.executable, "-m", "syncrain", "--power-sweep", "--sweep-seconds", "4"],
                          cwd=root, env=env, capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
    saved = list(tmp_path.glob("syncrain-power-*.json"))
    assert len(saved) == 1
    record = json.loads(saved[0].read_text())
    assert record["build"] == build.BUILD_NUMBER and record["stream"] == build.stream_id()
    phases = record["phases"]
    assert len(phases) == len(power.phases(4)) and all(p.get("watts") == 42.5 for p in phases), phases
    assert all(p["startup"].startswith("syncrain build") for p in phases[1:]), [p.get("startup") for p in phases]
    time.sleep(1)
    left = running_wallpapers() + [p for p in running_processes() if "syncrain.cover" in p[1]]
    assert not left, f"a phase's wallpaper outlived the sweep: {left}"


def test_the_sweep_will_not_measure_beside_another_wallpaper(x_display, root, tmp_path):
    env = app_env(x_display, SYNCRAIN_POWER_COMMAND="echo 1", HOME=str(tmp_path))
    other = subprocess.Popen([sys.executable, "-m", "syncrain", "--window", "--size", "160x90"], cwd=root, env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(2)
        done = subprocess.run([sys.executable, "-m", "syncrain", "--power-sweep"], cwd=root, env=env,
                              capture_output=True, text=True, timeout=120)
        assert done.returncode == 1
        assert f"pid {other.pid}" in done.stdout and "systemctl --user stop syncrain" in done.stdout
    finally:
        other.terminate()
        other.wait(timeout=30)
