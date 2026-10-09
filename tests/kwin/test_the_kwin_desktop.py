"""syncrain on KDE Plasma's compositor: KWin 6 headless, the wallpaper on its layer, covered screens.

The operator's desktop is KDE Plasma on Wayland. This lane runs the KWin of the current Plasma (6.7.5
from nixpkgs; `SYNCRAIN_KWIN` names its kwin_wayland) with its virtual backend: no graphics card,
KWin composites in software, every screen refreshes at 60 Hz, and D-Bus is a private session bus.
Plasma's shell is not here (no panel, no desktop); KWin is, with the scripting API the wallpaper's
pause uses (syncrain/hidden.py). Build 4's sweep found KWin asking a covered wallpaper for frames
at full rate on the operator's desktop; the first test shows KWin still does, and the rest hold
build 5's answer: a screen under a maximized or full-screen window is not drawn until it shows.
The wallpaper is the native one (syncrain/native/, built by the lane), as on the operator's
desktop; the full-screen pause is also checked with the GTK host (--host gtk), and build 4's frame
timer (--pacing timer), which the GTK host keeps, is timed beside the pacer.

The frame timing is judged by the median of six 2-second reports. KWin composites in software here
and the wallpaper draws with llvmpipe on the same two processors, so a frame now and then takes
three times as long as usual; a median rides over those moments, a minimum does not.

Needs KWin 6 (SYNCRAIN_KWIN, or kwin_wayland on PATH), dbus-daemon and dbus-send, gtk4-layer-shell's
typelib, and two processors or more (docs/agent/ENVIRONMENT.md).
"""
from __future__ import annotations

import ctypes.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from statistics import median

import pytest

from tests.conftest import ROOT, need

WINDOW = str(ROOT / "tests" / "kwin" / "window.py")
FPS = re.compile(r"syncrain: ([0-9.]+) fps at \d+x\d+ \(area (\d+)\)"
                 r"(?:, spacing (\d+) refresh(?:es)? (\d+)%, steady (\d+)%, lead ([0-9.]+) ms)?")


class Proc:
    """A process whose output lines are kept with the moment they arrived."""

    def __init__(self, argv, env):
        self.lines: list[tuple[float, str]] = []
        self.proc = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, start_new_session=True)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            self.lines.append((time.monotonic(), line.rstrip("\n")))

    def wait_for(self, pattern, timeout=45.0, after=0.0):
        """The first line at or after `after` matching `pattern`: (when, line)."""
        rx = re.compile(pattern)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for t, line in list(self.lines):
                if t >= after and rx.search(line):
                    return t, line
            if self.proc.poll() is not None:
                break
            time.sleep(0.05)
        tail = "\n".join(line for _, line in self.lines[-25:])
        pytest.fail(f"no line matching {pattern!r} within {timeout} s; the output ended with:\n{tail}")

    def reports(self, after, before=None):
        """(area, fps, spacing, even %, steady %) for every frame-rate report between two moments."""
        out = []
        for t, line in list(self.lines):
            m = FPS.match(line)
            if m and t >= after and (before is None or t < before):
                out.append((int(m.group(2)), float(m.group(1)), int(m.group(3) or 0), int(m.group(4) or -1),
                            int(m.group(5) or -1)))
        return out

    def stop(self):
        if self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGTERM)
        try:
            return self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(self.proc.pid, signal.SIGKILL)
            return self.proc.wait(timeout=10)


#: KWin's own record of a 320x180 screen with a custom mode, as `kscreen-doctor
#: output.Virtual-0.addCustomMode.320.180.144000.full` and `output.Virtual-0.mode.2` leave it in
#: kwinoutputconfig.json (the mode's own timing makes it 141.33 Hz). KWin applies it at start, which
#: gives the lane a fast screen without kscreen-doctor.
FAST_SCREEN = [
    {"name": "outputs", "data": [{"connectorName": "Virtual-0",
                                   "customModes": [{"flags": 8, "width": 320, "height": 180, "refreshRate": 144000}],
                                   "mode": {"flags": 10, "width": 320, "height": 180, "refreshRate": 141332},
                                   "scale": 1}]},
    {"name": "setups", "data": [{"lidClosed": False, "outputs": [{"enabled": True, "outputIndex": 0,
                                                                  "position": {"x": 0, "y": 0}, "priority": 1,
                                                                  "replicationSource": ""}]}]},
]


class Session:
    """A private session bus and a headless KWin on it, with `screens` screens of `size` (and KWin's
    output settings `outputs`, as kwinoutputconfig.json holds them, if given)."""

    def __init__(self, tmp, screens, size, outputs=None):
        self.tmp = tmp
        run = tmp / "run"
        run.mkdir(mode=0o700)
        self.run = run
        if outputs is not None:
            (tmp / "config").mkdir(exist_ok=True)
            (tmp / "config" / "kwinoutputconfig.json").write_text(json.dumps(outputs), encoding="utf-8")
        self.bus = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1",
                                     f"--address=unix:path={run}/bus"], stdout=subprocess.PIPE, text=True,
                                    start_new_session=True)
        self.address = self.bus.stdout.readline().strip()
        base = {k: v for k, v in os.environ.items()
                if k not in ("DISPLAY", "WAYLAND_DISPLAY", "GDK_DEBUG", "GDK_DISABLE", "GSK_RENDERER", "LD_PRELOAD",
                             "SYNCRAIN_REEXEC", "PYOPENGL_PLATFORM", "DBUS_SESSION_BUS_ADDRESS")}
        base.update(XDG_RUNTIME_DIR=str(run), DBUS_SESSION_BUS_ADDRESS=self.address, HOME=str(tmp / "home"),
                    XDG_CONFIG_HOME=str(tmp / "config"), XDG_CACHE_HOME=str(tmp / "cache"))
        self.base = base
        kwin = os.environ.get("SYNCRAIN_KWIN") or shutil.which("kwin_wayland")
        self.log = open(tmp / "kwin.log", "w")
        w, h = size
        self.kwin = subprocess.Popen([kwin, "--virtual", "--width", str(w), "--height", str(h),
                                      "--output-count", str(screens), "--no-lockscreen", "--no-global-shortcuts",
                                      "--no-kactivities", "--socket", "wayland-kwin"],
                                     env=base, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + 40
        while not ((run / "wayland-kwin").exists() and self.has_owner("org.kde.KWin")):
            if self.kwin.poll() is not None or time.monotonic() > deadline:
                self.stop()
                pytest.fail(f"KWin did not start; its log:\n{(tmp / 'kwin.log').read_text()[-3000:]}")
            time.sleep(0.2)

    def env(self, **extra):
        env = dict(self.base, WAYLAND_DISPLAY="wayland-kwin", GDK_BACKEND="wayland", XDG_CURRENT_DESKTOP="KDE",
                   GTK_A11Y="none", PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")
        env.update(extra)
        return env

    def send(self, dest, path, method, *args):
        done = subprocess.run(["dbus-send", "--session", "--print-reply", f"--dest={dest}", path, method, *args],
                              env=self.base, capture_output=True, text=True, timeout=30)
        return done.stdout

    def has_owner(self, name):
        return "boolean true" in self.send("org.freedesktop.DBus", "/org/freedesktop/DBus",
                                           "org.freedesktop.DBus.NameHasOwner", f"string:{name}")

    def syncrain(self, *args, **extra):
        return Proc([sys.executable, "-m", "syncrain", *args], self.env(**{"SYNCRAIN_DEBUG_FPS": "1", **extra}))

    def window(self, state, screen=0):
        extra = {}
        if state == "desktop":
            extra["LD_PRELOAD"] = ctypes.util.find_library("gtk4-layer-shell") or ""
        p = Proc([sys.executable, WINDOW, state, str(screen)], self.env(**extra))
        p.wait_for(f"^window {state}$", timeout=30)
        return p

    def stop(self):
        for p in (self.kwin, self.bus):
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
                try:
                    p.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)
                    p.wait(timeout=5)
        self.log.close()


def needs():
    kwin = os.environ.get("SYNCRAIN_KWIN") or shutil.which("kwin_wayland")
    need(kwin is not None and os.access(kwin, os.X_OK), "no KWin 6 (set SYNCRAIN_KWIN to the path of kwin_wayland)")
    need(shutil.which("dbus-daemon") is not None and shutil.which("dbus-send") is not None, "no dbus-daemon")
    probe = subprocess.run([sys.executable, "-c", "import gi; gi.require_version('Gtk4LayerShell', '1.0')"],
                           capture_output=True, text=True)
    need(probe.returncode == 0, "gtk4-layer-shell's typelib is not importable (set GI_TYPELIB_PATH)")


@pytest.fixture(scope="module")
def two(tmp_path_factory, native_wallpaper):
    """Two small screens: software rendering here takes about 6 ms a frame at 320x180, so two screens
    at 30 fps leave the processors room for KWin, and the timing measured is the pacing's."""
    needs()
    session = Session(tmp_path_factory.mktemp("kwin2"), screens=2, size=(320, 180))
    yield session
    session.stop()


@pytest.fixture(scope="module")
def fast(tmp_path_factory, native_wallpaper):
    """One small screen at 141 Hz, where a frame has 7 ms instead of 16.7 in which to reach KWin."""
    needs()
    session = Session(tmp_path_factory.mktemp("kwinfast"), screens=1, size=(320, 180), outputs=FAST_SCREEN)
    yield session
    session.stop()


@pytest.fixture(scope="module")
def one(tmp_path_factory, native_wallpaper):
    """One small screen, like `two`: at 640x360 a frame takes 18 ms here, more than half a refresh."""
    needs()
    session = Session(tmp_path_factory.mktemp("kwin1"), screens=1, size=(320, 180))
    yield session
    session.stop()


def drawing(p, area, after, timeout=30.0):
    """Wait until `area` reports frames drawn after `after`."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(a == area and fps > 1 for a, fps, *_ in p.reports(after)):
            return
        time.sleep(0.1)
    pytest.fail(f"area {area} drew nothing after {after:.1f}: " + "\n".join(line for _, line in p.lines[-15:]))


def started(p, screens):
    p.wait_for(rf"^syncrain build \d+ \(stream [0-9a-f]+\): .*, {screens} screens?$")
    t, _ = p.wait_for(r"^syncrain: drawing pauses on a screen under")
    for area in range(screens):
        drawing(p, area, t)


def test_kwin_still_asks_a_covered_wallpaper_for_frames(two):
    """What build 4 measured on the operator's desktop: without the pause, a wallpaper under a
    full-screen window draws on at full rate, because KWin keeps asking it for frames."""
    p = two.syncrain("--pause-under", "never")
    try:
        p.wait_for(r"^syncrain build ")
        drawing(p, 0, 0)
        cover = Proc([sys.executable, "-m", "syncrain.cover"], two.env())
        try:
            t, _ = cover.wait_for(r"^syncrain cover: 2 screens covered \(full-screen\)")
            time.sleep(4)
            under = [fps for area, fps, *_ in p.reports(t + 1.5) if area == 0]
            assert under and min(under) > 5, f"KWin stopped asking a covered wallpaper for frames: {under}"
        finally:
            cover.stop()
    finally:
        assert p.stop() == 0


@pytest.mark.parametrize("host", ["auto", "gtk"], ids=["native", "gtk-host"])
def test_a_full_screen_window_stops_the_drawing_until_it_goes(two, host):
    p = two.syncrain("--host", host)
    cover = None
    try:
        started(p, 2)
        cover = Proc([sys.executable, "-m", "syncrain.cover"], two.env())
        cover.wait_for(r"covered \(full-screen\)")
        t0, _ = p.wait_for(r"^syncrain: Virtual-0 covered, drawing stops$")
        t1, _ = p.wait_for(r"^syncrain: Virtual-1 covered, drawing stops$")
        quiet = max(t0, t1) + 0.5                    # a frame GTK had already been asked for may still come
        time.sleep(3.5)
        assert p.reports(quiet) == [], "frames drawn on a covered screen"
        cover.stop()
        t2, _ = p.wait_for(r"^syncrain: Virtual-0 shown again, drawing resumes$", after=quiet)
        p.wait_for(r"^syncrain: Virtual-1 shown again, drawing resumes$", after=quiet)
        drawing(p, 0, t2)
        drawing(p, 1, t2)
    finally:
        if cover:
            cover.stop()
        assert p.stop() == 0


def test_a_maximized_window_stops_only_the_screen_it_covers(two):
    p = two.syncrain()
    try:
        started(p, 2)
        win = two.window("maximized", 1)
        try:
            t, _ = p.wait_for(r"^syncrain: Virtual-1 covered, drawing stops$")
            time.sleep(3.5)
            later = p.reports(t + 0.5)
            assert {area for area, *_ in later} == {0}, f"the uncovered screen stopped, or the covered one drew: {later}"
        finally:
            win.stop()
        p.wait_for(r"^syncrain: Virtual-1 shown again, drawing resumes$", after=t)
    finally:
        assert p.stop() == 0


def test_a_minimized_window_gives_the_screen_back(two):
    p = two.syncrain()
    try:
        started(p, 2)
        win = two.window("minimized", 0)                 # maximized, then minimized half a second later
        try:
            t, _ = p.wait_for(r"^syncrain: Virtual-0 covered, drawing stops$")
            t2, _ = p.wait_for(r"^syncrain: Virtual-0 shown again, drawing resumes$", after=t)
            drawing(p, 0, t2)
        finally:
            win.stop()
    finally:
        assert p.stop() == 0


def test_with_pause_under_fullscreen_a_maximized_window_is_drawn_behind(two):
    p = two.syncrain("--pause-under", "fullscreen")
    try:
        p.wait_for(r"^syncrain: drawing pauses on a screen under full-screen windows \(KWin\)$")
        drawing(p, 0, 0)
        win = two.window("maximized", 0)               # full screen for a moment on the way (window.py)
        try:
            t = time.monotonic()
            time.sleep(3.5)
            said = [line for _, line in p.lines if line.startswith("syncrain: Virtual-0 ")]
            assert not said or said[-1].endswith("shown again, drawing resumes"), "paused under a maximized window"
            assert any(area == 0 for area, *_ in p.reports(t + 1)), "screen 0 stopped drawing"
        finally:
            win.stop()
    finally:
        assert p.stop() == 0


def test_while_kwin_shows_the_desktop_nothing_counts_as_covered(two):
    """KWin's show desktop hides every window, so a maximized one no longer covers anything. It also
    hides syncrain's own surface: to KWin a layer-shell surface is a window of the type its
    namespace names, and "syncrain" names no type, so it is a normal window, not the desktop
    (docs/ROADMAP.md). Show desktop lasts while whoever asked for it stays on the bus (Plasma's
    shell, in a session), so the test asks over a connection it keeps open."""
    from gi.repository import Gio, GLib
    p = two.syncrain()
    bus = win = None
    try:
        started(p, 2)
        win = two.window("maximized", 0)
        t, _ = p.wait_for(r"^syncrain: Virtual-0 covered, drawing stops$")
        bus = Gio.DBusConnection.new_for_address_sync(
            two.address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, None)

        def show(on):
            bus.call_sync("org.kde.KWin", "/KWin", "org.kde.KWin", "showDesktop", GLib.Variant("(b)", (on,)), None,
                          Gio.DBusCallFlags.NONE, 10000, None)
        show(True)
        t2, _ = p.wait_for(r"^syncrain: Virtual-0 shown again, drawing resumes$", after=t)
        time.sleep(3)
        assert p.reports(t2 + 1) == [], "KWin no longer hides a layer-shell surface named syncrain"
        show(False)
        p.wait_for(r"^syncrain: Virtual-0 covered, drawing stops$", after=t2)
        drawing(p, 1, t2)
    finally:
        if bus is not None:
            bus.close_sync(None)
        if win is not None:
            win.stop()
        assert p.stop() == 0


def test_the_script_leaves_kwin_with_the_wallpaper(two):
    p = two.syncrain()
    started(p, 2)
    plugin = f"syncrain-watch-{p.proc.pid}"
    loaded = lambda: "boolean true" in two.send("org.kde.KWin", "/Scripting",  # noqa: E731
                                                "org.kde.kwin.Scripting.isScriptLoaded", f"string:{plugin}")
    assert loaded(), "the script is not in KWin while the wallpaper runs"
    assert (two.run / f"{plugin}.js").exists()
    assert p.stop() == 0
    assert not loaded(), "the script stayed in KWin after the wallpaper stopped"
    assert not list(two.run.glob("syncrain-watch-*.js")), "the script file was left behind"


def settled_timing(session, *args, skip=6.0, count=6):
    """Reports after the pacer has had `skip` seconds to find the screen's timing."""
    p = session.syncrain(*args, SYNCRAIN_DEBUG_FPS="2")
    try:
        t, _ = p.wait_for(r"^syncrain: drawing pauses")
        deadline = time.monotonic() + 60
        while len(p.reports(t + skip)) < count and time.monotonic() < deadline:
            time.sleep(0.2)
        return p.reports(t + skip)[:count]
    finally:
        assert p.stop() == 0


def test_frames_land_on_every_second_refresh_drawn_for_the_moment_they_are_shown(one):
    """30 fps on a 60 Hz screen: each frame two refreshes after the one before, and drawn for the
    refresh it is shown on. Build 4's timer (`--pacing timer`, compared here) drew each frame for
    the moment the timer fired, anywhere up to a refresh before it was shown, so the motion stepped
    unevenly even when the frames were evenly spaced."""
    paced = settled_timing(one, skip=3.0)
    assert len(paced) == 6, paced
    assert all(r[2] == 2 for r in paced) and 29.0 <= median([r[1] for r in paced]) <= 31.0, paced
    even, calm = median([r[3] for r in paced]), median([r[4] for r in paced])
    assert even >= 85 and calm >= 90, f"frames off the cadence or off the moment drawn for: {paced}"
    timer = settled_timing(one, "--pacing", "timer", skip=3.0)
    assert median([r[4] for r in timer]) < 70, f"build 4's timer was as steady as the pacer: {timer}"


def test_diagnose_says_what_kwin_reports_and_the_screens_refresh_rates(two):
    done = subprocess.run([sys.executable, "-m", "syncrain", "--diagnose"], cwd=ROOT, env=two.env(),
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stdout + done.stderr
    out = done.stdout
    assert "screens:\n  Virtual-0: 320x180 at 0,0, scale 1, 60.00 Hz\n  Virtual-1: 320x180 at 320,0" in out, out
    covering = out.split("covering windows:\n", 1)[1]
    assert covering.startswith("  KWin answers: drawing pauses on a screen under maximized and full-screen windows")
    assert "  Virtual-0: not covered\n  Virtual-1: not covered" in covering, out


def test_the_power_sweep_on_kwin_draws_nothing_behind_windows(two, tmp_path):
    """Build 5's sweep end to end on the operator's compositor, with a stand-in power reading: the
    phases behind a maximized and a full-screen window draw no frames, the others are timed."""
    import json
    env = two.env(SYNCRAIN_POWER_COMMAND="echo 42.5", HOME=str(tmp_path))
    done = subprocess.run([sys.executable, "-m", "syncrain", "--power-sweep", "--sweep-seconds", "7"], cwd=ROOT,
                          env=env, capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
    record = json.loads(next(tmp_path.glob("syncrain-power-*.json")).read_text())
    rows = {p["phase"]: p for p in record["phases"]}
    assert rows["behind a maximized window"]["fps"] == 0.0, rows["behind a maximized window"]
    assert rows["behind a full-screen window"]["fps"] == 0.0, rows["behind a full-screen window"]
    installed, timer = rows["as installed (30 fps)"], rows["build 4's frame timer"]
    # The absolute steadiness is the timing test's (one screen, more reports); here, with two screens
    # and the sweep's own sampling sharing two processors, the comparison is what holds.
    assert installed["fps"] > 50, installed
    assert installed["timing"]["steady"] >= timer["timing"]["steady"] + 20, (timer, installed)
    assert "drawing pauses on a screen under maximized and full-screen windows" in installed["pause"]
    assert "behind a maximized window" in done.stdout and " steady " in done.stdout
    assert "a black window covers every screen, so all your screens go black" in done.stdout
    assert "[7/8] behind a maximized window ... (every screen goes black now, for about 7 s)" in done.stdout


def test_frames_stay_on_time_on_a_141_hz_screen(fast):
    """At 141 Hz a frame has 7 ms in which to reach KWin, and where those 7 ms lie depends on how long
    drawing takes. Build 5 asked a fixed half refresh and 6 ms ahead: here 74 to 84% of frames were
    steady (build 4's timer: about 55%). Build 6 moves the lead by what the compositor reports
    (syncrain/pacing.py; the native wallpaper's port of it: syncrain/native/timing.c)."""
    paced = settled_timing(fast)
    assert len(paced) == 6, paced
    assert all(r[2] == 5 for r in paced), f"not every 5th refresh at a 30 fps cap: {paced}"
    assert 27.5 <= median([r[1] for r in paced]) <= 29.0, paced
    even, calm = median([r[3] for r in paced]), median([r[4] for r in paced])
    assert even >= 80 and calm >= 85, f"frames off the moment drawn for at 141 Hz: {paced}"
    timer = settled_timing(fast, "--pacing", "timer", skip=3.0)
    assert median([r[4] for r in timer]) <= calm - 15, (timer, paced)


def test_the_pause_starts_when_kwin_gives_the_script_a_number_in_use(two, tmp_path):
    """KWin numbers a script by how many it holds. With an earlier script unloaded, syncrain's gets the
    number of one still running, and asking that number to run reaches the other script; syncrain
    then asks KWin to start every script not yet running (syncrain/hidden.py, Watch.retry)."""
    def scripting(method, *args):
        return two.send("org.kde.KWin", "/Scripting", f"org.kde.kwin.Scripting.{method}", *args)

    first, second = tmp_path / "first.js", tmp_path / "second.js"
    first.write_text("// nothing\n")
    second.write_text("// nothing\n")
    ids = []
    for path, name in ((first, "lane-first"), (second, "lane-second")):
        ids.append(int(re.search(r"int32 (-?\d+)", scripting("loadScript", f"string:{path}", f"string:{name}")).group(1)))
        two.send("org.kde.KWin", f"/Scripting/Script{ids[-1]}", "org.kde.kwin.Script.run")
    scripting("unloadScript", "string:lane-first")              # the next script gets lane-second's number
    p = two.syncrain()
    try:
        started(p, 2)
        win = two.window("maximized", 0)
        try:
            p.wait_for(r"^syncrain: Virtual-0 covered, drawing stops$")
        finally:
            win.stop()
        assert not any("reported nothing" in line for _, line in p.lines), p.lines[-5:]
    finally:
        assert p.stop() == 0
        scripting("unloadScript", "string:lane-second")


def test_a_script_left_by_a_killed_syncrain_is_unloaded_by_the_next(two):
    loaded = lambda pid: "boolean true" in two.send(  # noqa: E731
        "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.isScriptLoaded", f"string:syncrain-watch-{pid}")
    first = two.syncrain()
    started(first, 2)
    pid = first.proc.pid
    os.killpg(first.proc.pid, signal.SIGKILL)                   # no chance to unload anything
    first.proc.wait(timeout=30)
    assert loaded(pid) and (two.run / f"syncrain-watch-{pid}.js").exists()
    second = two.syncrain()
    try:
        started(second, 2)
        assert not loaded(pid), "the dead syncrain's script is still in KWin"
        assert not (two.run / f"syncrain-watch-{pid}.js").exists()
    finally:
        assert second.stop() == 0


DRAG = """
// Un-maximize the lane's window and move it every 5 ms for 1.5 s, as a drag by its title bar does.
var target = null;
var all = workspace.windowList();
for (var i = 0; i < all.length; i++) {
    if (all[i].caption === "kwin lane maximized") target = all[i];
}
if (target) {
    target.setMaximize(false, false);
    var n = 0;
    var mover = new QTimer();
    mover.interval = 5;
    mover.timeout.connect(function () {
        n++;
        target.frameGeometry = {x: 20 + n % 40, y: 20, width: 160, height: 100};
        if (n >= 300) mover.stop();
    });
    mover.start();
}
"""


def test_a_screen_uncovered_by_a_drag_draws_again_during_the_drag(two, tmp_path):
    """A maximized window dragged off a screen: KWin un-maximizes it as the drag starts. The script
    answers changes at most every 50 ms, so the screen draws again while the window still moves
    (build 6's script waited for 50 ms without a move, which a drag never gives)."""
    script = tmp_path / "drag.js"
    script.write_text(DRAG)
    p = two.syncrain()
    win = None
    try:
        started(p, 2)
        win = two.window("maximized", 0)
        t, _ = p.wait_for(r"^syncrain: Virtual-0 covered, drawing stops$")
        reply = two.send("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.loadScript", f"string:{script}",
                         "string:lane-drag")
        number = int(re.search(r"int32 (-?\d+)", reply).group(1))
        dragged = time.monotonic()
        two.send("org.kde.KWin", f"/Scripting/Script{number}", "org.kde.kwin.Script.run")
        shown, _ = p.wait_for(r"^syncrain: Virtual-0 shown again, drawing resumes$", after=t, timeout=10)
        assert shown - dragged < 0.6, f"shown again {shown - dragged:.2f} s after the drag began, not during it"
    finally:
        two.send("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.unloadScript", "string:lane-drag")
        if win is not None:
            win.stop()
        assert p.stop() == 0
