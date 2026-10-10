"""The power sweep's parts that need no display: reading the card's power, finding other wallpapers,
and what each phase runs. The whole sweep runs in the render lane, with a stand-in power reading."""
from __future__ import annotations

import os
import signal
import threading
import time

import pytest

from syncrain import power
from syncrain.app import parse_args


def test_a_streamed_nvidia_smi_line_is_read_and_anything_else_is_not():
    assert power.parse_nvidia_line("0, 38.21, P2, 1590, 7001, 3\n") == {
        "index": "0", "watts": 38.21, "pstate": "P2", "gr": "1590", "mem": "7001", "util": "3"}
    for junk in ("index, power.draw [W], pstate", "0, [N/A], P8, 210, 405, 0", ""):
        assert power.parse_nvidia_line(junk) is None


def test_the_amdgpu_sensor_is_found_and_read_in_watts(tmp_path, monkeypatch):
    hw = tmp_path / "card1/device/hwmon/hwmon4"
    hw.mkdir(parents=True)
    (hw / "power1_average").write_text("35500000\n")
    (tmp_path / "card1/device/gpu_busy_percent").write_text("7\n")
    monkeypatch.delenv("SYNCRAIN_POWER_COMMAND", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "no-tools-here"))
    source = power.detect_power_source(str(tmp_path))
    assert isinstance(source, power.Hwmon)
    assert source.sample() == (35.5, {"busy": "7%"})


def test_a_named_command_wins_over_every_driver(monkeypatch):
    monkeypatch.setenv("SYNCRAIN_POWER_COMMAND", "echo 12.25")
    source = power.detect_power_source("/nonexistent")
    assert isinstance(source, power.Command) and source.sample() == (12.25, {})


def test_without_any_reading_there_is_no_source(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNCRAIN_POWER_COMMAND", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert power.detect_power_source(str(tmp_path)) is None


def fake_proc(tmp_path, processes):
    for pid, argv in processes.items():
        (tmp_path / str(pid)).mkdir()
        (tmp_path / str(pid) / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    return str(tmp_path)


def test_other_wallpapers_are_found_however_they_were_started(tmp_path):
    proc = fake_proc(tmp_path, {
        101: ["/usr/bin/python3", "-m", "syncrain", "--channel", "public"],            # the installer's launcher
        102: ["/nix/store/x-python3/bin/python3.13", "/nix/store/y-syncrain/bin/.syncrain-wrapped"],   # Nix
        103: ["python3", "-m", "syncrain", "--diagnose"],                              # a tool, not a wallpaper
        104: ["nvim", "syncrain"],                                                    # a folder of that name
        105: ["python3", "-m", "syncrain", "--power-sweep"],                           # the sweep itself
        106: ["/opt/syncrain/syncrain/native/syncrain-wallpaper", "--scene", "3", "--fps", "30.0"],  # exec'd
        107: ["/usr/bin/syncrain-wallpaper-editor"],                                  # a name that only starts so
    })
    assert sorted(pid for pid, _ in power.running_wallpapers(proc)) == [101, 102, 106]
    assert power.running_wallpapers(proc, exclude={101, 102, 106}) == []


def test_every_phase_is_named_once_and_the_sweep_starts_from_nothing():
    plan = power.phases(25)
    names = [p["name"] for p in plan]
    assert len(set(names)) == len(names)
    assert names[0].startswith("nothing") and plan[0]["child"] is False
    assert {p.get("cover") for p in plan} >= {"maximized", "fullscreen"}, "behind both kinds of window"
    assert any(p.get("args") == ["--pacing", "timer"] for p in plan), "build 4's frame timer, for comparison"
    assert names[1].startswith("as installed") and plan[1]["args"] == []
    assert plan[2]["args"] == ["--host", "gtk"], "the Python and GTK host right after, to compare with"


def test_the_phases_run_with_the_wallpaper_s_own_options():
    args = parse_args(["--power-sweep", "--channel", "friends", "--rainbow", "all"])
    assert power.base_args(args) == ["--channel", "friends", "--rainbow", "all"]
    assert power.base_args(parse_args(["--power-sweep"])) == []
    assert power.base_args(parse_args(["--power-sweep", "--pause-under", "fullscreen"])) == \
        ["--pause-under", "fullscreen"]
    assert power.base_args(parse_args(["--power-sweep", "--host", "gtk"])) == ["--host", "gtk"]


def test_each_phase_says_what_drew_it():
    assert power.drawn_by("syncrain build 8 (stream x): OpenGL ES 3.2 on y, native wallpaper, 2 screens") == "native"
    assert power.drawn_by("syncrain build 8 (stream x): OpenGL 4.6 on y, GTK renderer gl, 2 screens") == "gl"
    assert power.drawn_by("") == ""


def test_the_wallpaper_s_processor_time_and_memory_are_read_from_proc():
    child = power.Child.__new__(power.Child)
    child.proc = type("Proc", (), {"pid": os.getpid()})()
    before = child.cpu_seconds()
    deadline = time.monotonic() + 10
    while child.cpu_seconds() == before and time.monotonic() < deadline:
        sum(i * i for i in range(20_000))
    assert before is not None and child.cpu_seconds() > before
    assert 1 < child.resident_mib() < 4096
    child.proc.pid = 2 ** 22 + 1                      # above the kernel's largest pid: no such process
    assert child.cpu_seconds() is None and child.resident_mib() is None


def test_the_frame_rate_reports_are_read_per_screen():
    child = power.Child.__new__(power.Child)
    child.lines = ["syncrain build 4 (stream x): OpenGL ES 3.2 on y, GTK renderer gl, 2 screens",
                   "syncrain: 30.1 fps at 2560x1440 (area 0)", "syncrain: 29.9 fps at 2560x1440 (area 1)",
                   "syncrain: 29.9 fps at 2560x1440 (area 0)", "syncrain: 30.1 fps at 2560x1440 (area 1)"]
    child.started = threading.Event()
    child.started.set()
    assert child.fps_since(1) == 60.0
    assert child.fps_since(len(child.lines)) == 0.0, "started, but nothing drawn since: covered, not missing"
    assert child.timing_since(1) == {}, "build 4's reports say nothing about timing"


def test_the_timing_reports_are_averaged_over_the_screens():
    child = power.Child.__new__(power.Child)
    child.lines = ["syncrain: 30.0 fps at 2560x1440 (area 0), spacing 2 refreshes 100%, steady 100%, lead 14.3 ms",
                   "syncrain: 28.8 fps at 3840x2160 (area 1), spacing 5 refreshes 90%, steady 96%, lead 8.5 ms",
                   "syncrain: 60.0 fps at 1920x1080 (area 2), spacing 1 refresh 80%, steady 50%, lead 14.3 ms",
                   "syncrain: Virtual-0 covered, drawing stops"]
    child.started = threading.Event()
    child.started.set()
    assert child.fps_since(0) == 118.8
    assert child.timing_since(0) == {"spacing": "1/2/5", "even": 90.0, "steady": 82.0, "lead_ms": 12.4}
    child.lines = ["syncrain: 30.0 fps at 2560x1440 (area 0), spacing 2 refreshes 100%, steady 100%"]
    assert child.timing_since(0) == {"spacing": "2", "even": 100.0, "steady": 100.0}, "build 5's reports"


def test_the_sweep_warns_before_it_turns_every_screen_black():
    """The operator, after build 8's sweep: it "should have a warning message in it that in the last
    two tests, all your screens might go black for a while"."""
    warning = power.cover_warning(power.phases(25), 25)
    assert warning.startswith("Warning: in the last two phases (behind a maximized window, behind a full-screen "
                              "window) a black window covers every screen"), warning
    assert "all your screens go black for about 25 s in each" in warning, warning
    assert "(Alt+Tab) and press Ctrl+C" in warning and "Alt+F4" not in warning, warning
    assert power.cover_warning([p for p in power.phases(25) if not p.get("cover")], 25) is None


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGHUP, signal.SIGTERM], ids=["ctrl-c", "closed-terminal", "kill"])
def test_a_closed_terminal_stops_the_sweep_as_ctrl_c_does(sig):
    """The black windows must not outlive the sweep: SIGHUP and SIGTERM end its phases the way Ctrl+C
    does (its children are stopped on the way out), and the handlers that were there come back."""
    started = {s: signal.getsignal(s) for s in power.STOPPING}
    try:
        for s in power.STOPPING:              # as a terminal starts it, even when pytest runs under nohup
            signal.signal(s, signal.default_int_handler if s == signal.SIGINT else signal.SIG_DFL)
        before = [signal.getsignal(s) for s in power.STOPPING]
        with pytest.raises(KeyboardInterrupt):
            with power.interrupted_by_hangup():
                try:
                    os.kill(os.getpid(), sig)
                    time.sleep(5)
                except KeyboardInterrupt:
                    # stopping the children: a second signal of any kind must not cut that short
                    for again in power.STOPPING:
                        os.kill(os.getpid(), again)
                    time.sleep(0.2)
                    raise
        assert [signal.getsignal(s) for s in power.STOPPING] == before
    finally:
        for s, handler in started.items():
            signal.signal(s, handler)


def test_a_sweep_started_with_nohup_outlives_its_terminal():
    """`nohup` leaves SIGHUP ignored; the sweep keeps it so."""
    before = signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        with power.interrupted_by_hangup():
            os.kill(os.getpid(), signal.SIGHUP)
            time.sleep(0.2)
        assert signal.getsignal(signal.SIGHUP) is signal.SIG_IGN
    finally:
        signal.signal(signal.SIGHUP, before)


def test_the_results_are_saved_even_when_the_table_cannot_be_printed(tmp_path, monkeypatch):
    """A closed terminal makes every print fail; the JSON is written before the first one."""
    import builtins

    class Gone(OSError):
        pass

    def no_terminal(*args, **kwargs):
        raise Gone(5, "Input/output error")

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(builtins, "print", no_terminal)
    with pytest.raises(Gone):
        power.report([{"phase": "nothing (your desktop alone)", "watts": 50.0}], "echo 1", interrupted=True)
    saved = list(tmp_path.glob("syncrain-power-*.json"))
    assert len(saved) == 1 and '"interrupted": true' in saved[0].read_text()
