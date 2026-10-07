"""A black window over every screen, for the power sweep's "covered" phases and the KWin lane.

`python -m syncrain.cover` puts a full-screen window on every screen; with `--maximized`, a
maximized one instead, the way an application usually covers the desktop. xdg-shell lets a client
choose a screen only for full screen, so each window goes full screen on its screen first and is
then maximized where it is. It stays until it is sent SIGTERM or SIGINT.
"""
import signal
import sys


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    maximized = "--maximized" in argv
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, GLib, Gtk

    Gtk.init()
    display = Gdk.Display.get_default()
    if display is None:
        print("syncrain cover: no display", file=sys.stderr)
        return 1
    css = Gtk.CssProvider()
    rule = "window.cover { background-color: #000000; }"
    if hasattr(css, "load_from_string"):
        css.load_from_string(rule)
    else:
        css.load_from_data(rule.encode())
    add_provider = getattr(Gtk, "style_context_add_provider_for_display", None) \
        or Gtk.StyleContext.add_provider_for_display
    add_provider(display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    loop = GLib.MainLoop()
    windows = []
    monitors = display.get_monitors()
    for i in range(monitors.get_n_items()):
        win = Gtk.Window(title="syncrain cover")
        win.add_css_class("cover")
        win.set_decorated(False)
        win.set_default_size(640, 360)
        win.fullscreen_on_monitor(monitors.get_item(i))
        win.present()
        windows.append(win)
    how = "maximized" if maximized else "full-screen"

    def covered():
        if maximized:
            for win in windows:
                win.unfullscreen()
                win.maximize()
        print(f"syncrain cover: {len(windows)} screen{'s' if len(windows) != 1 else ''} covered ({how})", flush=True)
        return GLib.SOURCE_REMOVE

    GLib.timeout_add(800 if maximized else 1, covered)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    for sig in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_HIGH, sig, lambda *_: (loop.quit(), GLib.SOURCE_REMOVE)[1])
    loop.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
