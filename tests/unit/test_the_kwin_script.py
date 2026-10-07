"""The script syncrain loads into KWin, run against a stand-in KWin in Node (syncrain/hidden.py).

KWin runs the script in Qt's JavaScript engine; Node runs the same plain JavaScript. The stand-in
has KWin 6's names (workspace.windowList, screens, clientArea, the window properties and signals
the script uses), so what is tested is the script's own decisions: which windows count as covering
which screen, and that it tells syncrain only when an answer changes. The real KWin runs it in the
kwin lane (tests/kwin/).
"""
from __future__ import annotations

import json
import shutil
import subprocess

from syncrain.hidden import is_hidden, script_source
from tests.conftest import need

HARNESS = r"""
const vm = require("vm");
const steps = [];
function signal() {
  const fns = [];
  return { connect: f => fns.push(f), emit: (...a) => fns.forEach(f => f(...a)) };
}
const D1 = { id: "desk-1" }, D2 = { id: "desk-2" };
const A = { name: "DP-1", geometry: { x: 0, y: 0, width: 1920, height: 1080 }, geometryChanged: signal() };
const B = { name: "HDMI-A-1", geometry: { x: 1920, y: 0, width: 2560, height: 1440 }, geometryChanged: signal() };
const windows = [];
let listed = 0;                                   // how often the script looked at the window list
const workspace = {
  screens: [A, B], currentDesktop: D1, currentActivity: "act-1",
  windowList: () => { listed++; return windows.slice(); },
  windowAdded: signal(), windowRemoved: signal(), currentDesktopChanged: signal(),
  currentActivityChanged: signal(), screensChanged: signal(),
  // the work area: the screen less a 44 px panel at the bottom
  clientArea: (option, o, d) => ({ x: o.geometry.x, y: o.geometry.y, width: o.geometry.width,
                                   height: o.geometry.height - 44 }),
};
const SIGNALS = ["fullScreenChanged", "maximizedChanged", "minimizedChanged", "hiddenChanged",
                 "frameGeometryChanged", "desktopsChanged", "activitiesChanged", "outputChanged",
                 "opacityChanged"];
function win(props) {
  const w = Object.assign({ deleted: false, specialWindow: false, popupWindow: false, minimized: false,
    hidden: false, opacity: 1, onAllDesktops: false, desktops: [D1], activities: [], fullScreen: false,
    maximizeMode: 0, frameGeometry: { x: 100, y: 100, width: 800, height: 600 } }, props);
  SIGNALS.forEach(s => { w[s] = signal(); });
  return w;
}
function add(w) { windows.push(w); workspace.windowAdded.emit(w); return w; }
function change(w, props, sig) { Object.assign(w, props); w[sig].emit(); }
// KWin's QTimer on a clock the test moves (tick): start() restarts a running timer, as Qt's does.
let clock = 0;
const timers = [];
function QTimer() { this.singleShot = false; this.interval = 0; this.active = false; this.due = 0;
                    this.timeout = signal(); timers.push(this); }
QTimer.prototype.start = function () { this.active = true; this.due = clock + this.interval; };
function tick(ms) {
  const end = clock + ms;
  for (;;) {
    const next = timers.filter(t => t.active && t.due <= end).sort((a, b) => a.due - b.due)[0];
    if (!next) break;
    clock = next.due;
    next.active = false;
    next.timeout.emit();
  }
  clock = end;
}
function flush() { tick(1000); }
const said = [];
const context = { workspace, QTimer, KWin: { MaximizeArea: 2 },
  callDBus: (service, path, iface, method, screen, covered) => said.push([service, path, iface, method, screen, covered]),
  print: m => said.push(["print", m]) };
vm.createContext(context);
vm.runInContext(SCRIPT, context);
function mark(name) { flush(); steps.push([name, said.splice(0)]); }
mark("start");
const full = add(win({ fullScreen: true, frameGeometry: { x: 0, y: 0, width: 1920, height: 1080 } }));
mark("full-screen on DP-1");
change(full, { minimized: true }, "minimizedChanged"); mark("minimized");
change(full, { minimized: false }, "minimizedChanged"); mark("restored");
change(full, { fullScreen: false, maximizeMode: 3, frameGeometry: { x: 0, y: 0, width: 1920, height: 1036 } },
       "fullScreenChanged"); mark("full-screen to maximized");
change(full, { desktops: [D2] }, "desktopsChanged"); mark("sent to desktop 2");
workspace.currentDesktop = D2; workspace.currentDesktopChanged.emit(D1, D2, A); mark("desktop 2 shown");
change(full, { opacity: 0.8 }, "opacityChanged"); mark("made translucent");
change(full, { opacity: 1, activities: ["act-2"] }, "activitiesChanged"); mark("other activity");
add(win({ specialWindow: true, frameGeometry: { x: 1920, y: 0, width: 2560, height: 1440 } })); mark("a dock");
add(win({ desktops: [D2], frameGeometry: { x: 1920, y: 0, width: 2560, height: 1440 } })); mark("our own layer");
const half = add(win({ maximizeMode: 3, desktops: [D2], frameGeometry: { x: 1920, y: 0, width: 1280, height: 1396 } }));
mark("maximized but half");
change(half, { frameGeometry: { x: 1920, y: 0, width: 2560, height: 1396 } }, "frameGeometryChanged");
mark("maximized on HDMI-A-1");
change(half, { hidden: true }, "hiddenChanged"); mark("hidden");
workspace.currentDesktop = D1;                                      // KWin 6.7: a desktop per screen,
workspace.currentDesktopForScreen = o => (o === A ? D1 : D2);      // and HDMI-A-1 still shows desktop 2
change(half, { hidden: false }, "hiddenChanged"); mark("per-screen desktops");
// A maximized window over DP-1 is dragged by its title bar: KWin un-maximizes it as the drag
// starts, then it moves every 5 ms for a second. DP-1 shows again at once, not when the drag ends,
// and the script looks at the windows about every 50 ms meanwhile, not 200 times.
workspace.currentDesktop = D1;
const dragged = add(win({ maximizeMode: 3, frameGeometry: { x: 0, y: 0, width: 1920, height: 1036 } }));
mark("maximized over DP-1");
const before = listed;
change(dragged, { maximizeMode: 0, frameGeometry: { x: 100, y: 100, width: 800, height: 600 } }, "maximizedChanged");
let shownAt = null;
for (let i = 1; i <= 200; i++) {
  tick(5);
  change(dragged, { frameGeometry: { x: 100 + i, y: 100, width: 800, height: 600 } }, "frameGeometryChanged");
  if (shownAt === null && said.some(c => c[4] === "DP-1" && c[5] === false)) shownAt = i * 5;
}
const looks = listed - before;
mark("the drag");
steps.push(["the drag, measured", [["drag", shownAt, looks]]]);
console.log(JSON.stringify(steps));
"""


def scenario(maximized=True):
    need(shutil.which("node") is not None, "no node to run the KWin script in")
    source = HARNESS.replace("SCRIPT", json.dumps(script_source(":1.42", maximized)), 1)
    done = subprocess.run(["node", "-e", source], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return {name: [tuple(c) for c in calls] for name, calls in json.loads(done.stdout)}


def covered(calls):
    """The Covered(screen, covered) calls, as (screen, covered)."""
    return [(c[4], c[5]) for c in calls if c[3] == "Covered"]


def test_the_script_says_which_screen_a_window_covers_and_only_when_it_changes():
    s = scenario()
    assert all(c[:4] == (":1.42", "/org/syncrain/Watch", "org.syncrain.Watch", "Covered")
               for name, calls in s.items() if name != "the drag, measured" for c in calls if c[0] != "print"), \
        "only syncrain, only Covered"
    assert not any(c[0] == "print" for calls in s.values() for c in calls), s
    assert covered(s["start"]) == [("DP-1", False), ("HDMI-A-1", False)], "every screen once at the start"
    assert covered(s["full-screen on DP-1"]) == [("DP-1", True)]
    assert covered(s["minimized"]) == [("DP-1", False)]
    assert covered(s["restored"]) == [("DP-1", True)]
    assert covered(s["full-screen to maximized"]) == [], "maximized still covers: nothing to say"
    assert covered(s["sent to desktop 2"]) == [("DP-1", False)]
    assert covered(s["desktop 2 shown"]) == [("DP-1", True)]
    assert covered(s["made translucent"]) == [("DP-1", False)], "a see-through window does not count"
    assert covered(s["other activity"]) == [], "still uncovered: on another activity"
    assert covered(s["a dock"]) == [], "panels and docks never count"
    assert covered(s["our own layer"]) == [], "a screen-sized window that is neither maximized nor full-screen"
    assert covered(s["maximized but half"]) == [], "maximized has to fill the work area"
    assert covered(s["maximized on HDMI-A-1"]) == [("HDMI-A-1", True)]
    assert covered(s["hidden"]) == [("HDMI-A-1", False)]
    assert covered(s["per-screen desktops"]) == [("HDMI-A-1", True)], "HDMI-A-1 shows desktop 2"
    assert covered(s["maximized over DP-1"]) == [("DP-1", True)]
    assert covered(s["the drag"]) == [("DP-1", False)]
    (_, shown_at, looks), = s["the drag, measured"]
    assert shown_at is not None and shown_at <= 60, f"DP-1 shown {shown_at} ms into the drag, not within 50 ms"
    assert 15 <= looks <= 25, f"{looks} looks at the windows in a one-second drag: about one every 50 ms"


def test_with_pause_under_fullscreen_a_maximized_window_does_not_count():
    s = scenario(maximized=False)
    assert covered(s["full-screen on DP-1"]) == [("DP-1", True)]
    assert covered(s["full-screen to maximized"]) == [("DP-1", False)]
    assert covered(s["maximized on HDMI-A-1"]) == []


def test_a_viewport_is_hidden_only_when_every_screen_it_shows_is_covered():
    assert is_hidden(("DP-1",), {"DP-1": True}, showing_desktop=False)
    assert not is_hidden(("DP-1",), {"DP-1": True}, showing_desktop=True), "show desktop uncovers everything"
    assert not is_hidden(("DP-1", "HDMI-A-1"), {"DP-1": True}, showing_desktop=False)
    assert not is_hidden((), {"DP-1": True}, showing_desktop=False), "a window is never hidden"
    assert not is_hidden(("DP-1",), {}, showing_desktop=False), "nothing heard: drawn"


def test_the_script_names_whom_it_tells_as_a_javascript_string():
    source = script_source(':1.42"; evil()', True)
    assert 'var SERVICE = ":1.42\\"; evil()";' in source
    assert "var MAXIMIZED = true;" in source and "var MAXIMIZED = false;" in script_source(":1.1", False)


def test_scripts_left_by_syncrains_that_died_are_found_and_only_those(tmp_path):
    import os

    from syncrain.hidden import leftovers
    for name in (f"syncrain-watch-{os.getpid()}.js", "syncrain-watch-101.js", "syncrain-watch-202.js",
                 "syncrain-watch-x.js", "other-303.js"):
        (tmp_path / name).write_text("// a script\n")
    found = leftovers(str(tmp_path), alive=lambda pid: pid == 202)
    assert found == [(101, str(tmp_path / "syncrain-watch-101.js"))], "ours, a live one and strangers stay"


def test_a_pid_counts_as_a_living_syncrain_only_when_its_command_is_one():
    """A crashed syncrain's pid can be taken over; `journalctl -fu syncrain` mentions syncrain too."""
    import sys
    import time

    from syncrain.hidden import _alive
    nap = "import time; time.sleep(30)"
    procs = [subprocess.Popen(argv) for argv in (["sleep", "30"],
                                                 [sys.executable, "-c", nap, "journalctl", "-fu", "syncrain"],
                                                 [sys.executable, "-c", nap, "-m", "syncrain"])]
    try:
        time.sleep(0.3)
        assert [_alive(p.pid) for p in procs] == [False, False, True]
    finally:
        for p in procs:
            p.kill()
            p.wait()
    assert not _alive(procs[2].pid), "gone once it has exited"
