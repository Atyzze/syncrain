"""A window for the KWin lane: `python tests/kwin/window.py STATE [SCREEN]`.

STATE is maximized, fullscreen, normal, minimized (maximized, then minimized) or desktop (a
layer-shell surface KWin takes for the desktop, the part of Plasma's shell that holds the focus
while KWin shows the desktop; it needs gtk4-layer-shell preloaded). The window goes to screen
SCREEN (default 0): xdg-shell lets a client choose a screen only for full screen, so it goes full
screen there first. It prints "window STATE" once it is in that state and stays until SIGTERM.
"""
import signal
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

state = sys.argv[1]
screen = int(sys.argv[2]) if len(sys.argv) > 2 else 0
Gtk.init()
monitor = Gdk.Display.get_default().get_monitors().get_item(screen)
loop = GLib.MainLoop()
win = Gtk.Window(title=f"kwin lane {state}")
win.set_default_size(320, 200)
if state == "desktop":
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gtk4LayerShell as LayerShell
    LayerShell.init_for_window(win)
    LayerShell.set_namespace(win, "desktop")
    LayerShell.set_layer(win, LayerShell.Layer.BACKGROUND)
    LayerShell.set_monitor(win, monitor)
    for edge in (LayerShell.Edge.LEFT, LayerShell.Edge.RIGHT, LayerShell.Edge.TOP, LayerShell.Edge.BOTTOM):
        LayerShell.set_anchor(win, edge, True)
    LayerShell.set_keyboard_mode(win, LayerShell.KeyboardMode.ON_DEMAND)
elif state != "normal":
    win.fullscreen_on_monitor(monitor)
win.present()


def settle():
    if state in ("maximized", "minimized"):
        win.unfullscreen()
        win.maximize()
    if state == "minimized":
        GLib.timeout_add(500, lambda: (win.minimize(), say())[1])
    else:
        say()
    return GLib.SOURCE_REMOVE


def say():
    print(f"window {state}", flush=True)
    return GLib.SOURCE_REMOVE


GLib.timeout_add(600, settle)
signal.signal(signal.SIGINT, signal.SIG_DFL)
GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, lambda *_: (loop.quit(), GLib.SOURCE_REMOVE)[1])
loop.run()
