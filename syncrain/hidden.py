"""Which screens a window hides, as KWin (KDE Plasma's compositor) knows it.

KWin keeps asking a wallpaper for frames while a full-screen window covers it: after each frame it
sends a frame callback to every surface on that screen that is shown at all, covered or not
(`src/scene/item.cpp`, `Item::framePainted`), so on Plasma syncrain drew at full rate behind a
full-screen window (the operator's sweep, build 4: 60 frames a second, +11 W, nothing on screen).
Sway stops asking a hidden surface for frames, and GTK then stops drawing by itself.

KWin's scripting API knows every window's state. `Watch` loads a small script into KWin over D-Bus
that reports, per screen and whenever it changes, whether a full-screen window (and, by default, a
maximized one) covers that screen; syncrain stops drawing a covered screen until it shows again.
The script only reads, and is unloaded when syncrain stops. KWin's "show desktop" hides every
window, so while it is on nothing counts as covered. A locked screen needs nothing here: KWin
stops asking any window but the lock screen for frames while it is locked.

KWin 6 only: KWin 5's script API names things differently, and the script then reports nothing,
which the app treats as "not watching" (the wallpaper draws as before).

KWin numbers a loaded script by how many scripts it holds (`Scripting::loadScript`), so after an
earlier script was unloaded the number can be one a running script already has, and the request to
run the new one reaches the old one. `Watch.retry` asks KWin to run every loaded script that is not
running (`Scripting.start`) when the script has not answered. A syncrain that died without unloading
its script (a crash, SIGKILL) leaves its file in `$XDG_RUNTIME_DIR`; the next one unloads those
scripts whose process is gone.
"""
from __future__ import annotations

import glob
import json
import os
import re

#: What syncrain answers to on the session bus; KWin's script calls Covered(screen, covered).
PATH = "/org/syncrain/Watch"
INTERFACE = "org.syncrain.Watch"
INTROSPECTION = f"""<node>
  <interface name="{INTERFACE}">
    <method name="Covered">
      <arg type="s" name="screen" direction="in"/>
      <arg type="b" name="covered" direction="in"/>
    </method>
  </interface>
</node>"""

#: --pause-under: which windows stop the drawing of the screen they cover.
POLICIES = ("maximized", "fullscreen", "never")

#: The script KWin runs. @SERVICE@ and @MAXIMIZED@ are filled in by script_source.
SCRIPT = r"""
"use strict";
// Loaded into KWin by syncrain (syncrain/hidden.py) and unloaded when syncrain stops. It only
// reads: which screens a full-screen (or maximized) window covers, sent to syncrain over D-Bus.
var SERVICE = @SERVICE@;
var MAXIMIZED = @MAXIMIZED@;
var MAXIMIZE_FULL = 3;
var said = {};

function fills(r, a) {
    return r.x <= a.x + 1 && r.y <= a.y + 1 &&
        r.x + r.width >= a.x + a.width - 1 && r.y + r.height >= a.y + a.height - 1;
}
function desktopOf(output) {
    return typeof workspace.currentDesktopForScreen === "function" ?
        workspace.currentDesktopForScreen(output) : workspace.currentDesktop;
}
function onDesktop(w, desktop) {
    if (w.onAllDesktops) return true;
    var ds = w.desktops || [];
    for (var i = 0; i < ds.length; i++) {
        if (desktop && ds[i] && ds[i].id === desktop.id) return true;
    }
    return false;
}
function onActivity(w) {
    var a = w.activities || [];
    return a.length === 0 || a.indexOf(workspace.currentActivity) >= 0;
}
function covers(w, output) {
    // Most windows are neither full-screen nor maximized: two property reads and out.
    if (!w) return false;
    var full = w.fullScreen, maximized = MAXIMIZED && w.maximizeMode == MAXIMIZE_FULL;
    if (!full && !maximized) return false;
    if (w.deleted || w.specialWindow || w.popupWindow || w.minimized || w.hidden) return false;
    if (!(w.opacity >= 0.999)) return false;
    var desktop = desktopOf(output);
    if (!onDesktop(w, desktop) || !onActivity(w)) return false;
    if (full) return fills(w.frameGeometry, output.geometry);
    return fills(w.frameGeometry, workspace.clientArea(KWin.MaximizeArea, output, desktop));
}
function update() {
    try {
        var outputs = workspace.screens, windows = workspace.windowList();
        for (var i = 0; i < outputs.length; i++) {
            var o = outputs[i], covered = false;
            for (var j = 0; j < windows.length && !covered; j++) covered = covers(windows[j], o);
            if (said[o.name] !== covered) {
                said[o.name] = covered;
                callDBus(SERVICE, "@PATH@", "@INTERFACE@", "Covered", o.name, covered);
            }
        }
    } catch (e) {
        print("syncrain watch: " + e);
    }
}
// Changes come in bursts (a dragged window moves on every step of the pointer), and KWin runs this
// on its own main thread, so a burst is answered at most every COALESCE_MS. The timer is started
// only when it is not running: QTimer.start() restarts a running timer, so starting it on every
// change would put the answer off until the pointer rested, and a screen uncovered by a drag would
// stay paused until then.
var COALESCE_MS = 50;
var settle = new QTimer();
settle.singleShot = true;
settle.interval = COALESCE_MS;
settle.timeout.connect(update);
function later() { if (!settle.active) settle.start(); }
var WINDOW_SIGNALS = ["fullScreenChanged", "maximizedChanged", "minimizedChanged", "hiddenChanged",
                      "frameGeometryChanged", "desktopsChanged", "activitiesChanged", "outputChanged",
                      "opacityChanged"];
function watchWindow(w) {
    for (var i = 0; i < WINDOW_SIGNALS.length; i++) {
        if (w[WINDOW_SIGNALS[i]]) w[WINDOW_SIGNALS[i]].connect(later);
    }
}
function watchScreens() {
    var outputs = workspace.screens;
    for (var i = 0; i < outputs.length; i++) {
        if (outputs[i].geometryChanged) outputs[i].geometryChanged.connect(later);
    }
}
workspace.windowList().forEach(watchWindow);
watchScreens();
workspace.windowAdded.connect(function (w) { watchWindow(w); later(); });
workspace.windowRemoved.connect(later);
workspace.currentDesktopChanged.connect(later);
workspace.currentActivityChanged.connect(later);
workspace.screensChanged.connect(function () { said = {}; watchScreens(); later(); });
update();
"""


def script_template(maximized: bool) -> str:
    """The script with everything but whom to tell filled in ("@SERVICE@" stays): what the native
    wallpaper's scene carries, since only it knows its own bus name."""
    return (SCRIPT.replace("@MAXIMIZED@", "true" if maximized else "false")
                  .replace("@PATH@", PATH).replace("@INTERFACE@", INTERFACE))


def script_source(service: str, maximized: bool) -> str:
    """The script for one syncrain process: whom to tell, and whether maximized windows count."""
    return script_template(maximized).replace("@SERVICE@", json.dumps(service))


SCRIPT_FILE = re.compile(r"^syncrain-watch-(\d+)\.js$")


def leftovers(runtime_dir: str, alive=None) -> list[tuple[int, str]]:
    """(pid, path) of the script files of syncrain processes that are gone: what a crash leaves."""
    alive = alive or _alive
    found = []
    for path in sorted(glob.glob(os.path.join(runtime_dir, "syncrain-watch-*.js"))):
        m = SCRIPT_FILE.match(os.path.basename(path))
        if m and int(m.group(1)) != os.getpid() and not alive(int(m.group(1))):
            found.append((int(m.group(1)), path))
    return found


def _alive(pid: int) -> bool:
    """A syncrain process with this pid still runs. A pid taken over by another program does not
    count, even one whose arguments mention syncrain (`journalctl -fu syncrain`, an editor)."""
    from .power import is_syncrain_command
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            argv = [a.decode(errors="replace") for a in f.read().split(b"\0") if a]
    except OSError:
        return False
    return is_syncrain_command(argv)


def is_hidden(screens, covered, showing_desktop) -> bool:
    """Whether a viewport that shows these screens cannot be seen: every one of them covered, and
    KWin not showing the desktop. A viewport on no named screen (a window) is never hidden."""
    return bool(screens) and not showing_desktop and all(covered.get(s, False) for s in screens)


class Watch:
    """Asks KWin which screens are covered; calls on_change() whenever the answer may have changed.

    Uses GLib's own D-Bus (Gio), so it needs nothing beyond PyGObject, and runs in the app's GLib
    main loop. start() returns None when the script is loaded, or why it is not.
    """

    KWIN = "org.kde.KWin"

    def __init__(self, on_change, maximized=True):
        self.on_change = on_change
        self.maximized = maximized
        self.covered: dict[str, bool] = {}
        self.showing_desktop = False
        self.answered = False                  # the script has reported at least once
        self.plugin = f"syncrain-watch-{os.getpid()}"
        self._bus = self._registration = self._subscription = None
        self._kwin_owner = None
        self._path = None

    # -- set-up and tear-down ------------------------------------------------------------------

    def start(self):
        from gi.repository import Gio, GLib
        self._Gio, self._GLib = Gio, GLib
        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            owner = self._call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                               "NameHasOwner", GLib.Variant("(s)", (self.KWIN,)), "(b)")
            if not owner[0]:
                return "KWin is not on the session bus"
            self._kwin_owner = self._call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                                          "GetNameOwner", GLib.Variant("(s)", (self.KWIN,)), "(s)")[0]
            info = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION).interfaces[0]
            self._registration = self._bus.register_object(PATH, info, self._on_call, None, None)
            self._subscription = self._bus.signal_subscribe(
                self.KWIN, self.KWIN, "showingDesktopChanged", "/KWin", None, Gio.DBusSignalFlags.NONE,
                self._on_showing_desktop)
            try:
                self.showing_desktop = bool(self._call(self.KWIN, "/KWin", "org.freedesktop.DBus.Properties", "Get",
                                                       GLib.Variant("(ss)", (self.KWIN, "showingDesktop")),
                                                       "(v)")[0])
            except GLib.Error:
                self.showing_desktop = False
            runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
            for pid, path in leftovers(runtime):        # scripts of syncrains that died without unloading
                self._unload(f"syncrain-watch-{pid}")
                try:
                    os.unlink(path)
                except OSError:
                    pass
            self._path = os.path.join(runtime, f"{self.plugin}.js")
            fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(script_source(self._bus.get_unique_name(), self.maximized))
            self._unload()                      # a script of a process with this pid that never unloaded
            script_id = self._call(self.KWIN, "/Scripting", "org.kde.kwin.Scripting", "loadScript",
                                   GLib.Variant("(ss)", (self._path, self.plugin)), "(i)")[0]
            if script_id < 0:
                self.stop()
                return "KWin did not load the script"
            self._call(self.KWIN, f"/Scripting/Script{script_id}", "org.kde.kwin.Script", "run", None, None)
        except GLib.Error as e:
            self.stop()
            return f"KWin's scripting did not answer ({e.message})"
        return None

    def stop(self):
        if self._bus is None:
            return
        self._unload()
        if self._registration:
            self._bus.unregister_object(self._registration)
            self._registration = None
        if self._subscription is not None:
            self._bus.signal_unsubscribe(self._subscription)
            self._subscription = None
        if self._path:
            try:
                os.unlink(self._path)
            except OSError:
                pass
            self._path = None

    def retry(self):
        """The script has not answered: perhaps `run` reached another script that had the same number
        (see the module's docstring). Ask KWin to run every loaded script that is not running."""
        try:
            self._call(self.KWIN, "/Scripting", "org.kde.kwin.Scripting", "start", None, None)
        except self._GLib.Error:
            pass

    def _unload(self, plugin=None):
        try:
            self._call(self.KWIN, "/Scripting", "org.kde.kwin.Scripting", "unloadScript",
                       self._GLib.Variant("(s)", (plugin or self.plugin,)), "(b)")
        except self._GLib.Error:
            pass

    def _call(self, name, path, interface, method, params, reply):
        result = self._bus.call_sync(name, path, interface, method, params,
                                     self._GLib.VariantType(reply) if reply else None,
                                     self._Gio.DBusCallFlags.NONE, 3000, None)
        return result.unpack() if reply else None

    # -- what KWin says --------------------------------------------------------------------------

    def _on_call(self, _conn, sender, _path, _interface, method, params, invocation):
        if sender != self._kwin_owner or method != "Covered":   # only KWin's script may say this
            invocation.return_dbus_error("org.freedesktop.DBus.Error.AccessDenied", "not KWin")
            return
        screen, covered = params.unpack()
        invocation.return_value(None)
        self.answered = True
        if self.covered.get(screen) != covered:
            self.covered[screen] = covered
            self.on_change()

    def _on_showing_desktop(self, _conn, _sender, _path, _interface, _signal, params):
        showing = bool(params.unpack()[0])
        if showing != self.showing_desktop:
            self.showing_desktop = showing
            self.on_change()

    def hidden(self, screens) -> bool:
        return is_hidden(screens, self.covered, self.showing_desktop)
