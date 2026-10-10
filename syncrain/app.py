"""syncrain native wallpaper: GTK4 + OpenGL (or OpenGL ES, whichever GTK hands out).

Wayland: one layer-shell surface per monitor (via gtk4-layer-shell); works on Hyprland, Sway,
         niri, river, Wayfire, labwc, COSMIC and KDE Plasma.
X11:     one desktop-type window covering the whole screen, one viewport per monitor.
--window opens an ordinary window instead (previews, or desktops without layer-shell such as GNOME).
"""
import argparse
import ctypes
import gc
import os
import signal
import sys
import time

from . import build, hidden, native

#: The exit status when no OpenGL context can be had. The autostart services list it under
#: RestartPreventExitStatus, so a machine without working OpenGL is not covered by an endless
#: restart loop of blank wallpapers; sysexits.h calls it EX_UNAVAILABLE.
EXIT_NO_GL = 69

#: The oldest contexts the shaders compile on: GLSL 3.30 core, or GLSL ES 3.00 (what WebGL2 runs).
MIN_GL = {False: (3, 3), True: (3, 0)}


class _ShowBuild(argparse.Action):
    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        print(build.describe())
        parser.exit()


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="syncrain", description="Never-repeating, clock-synchronised code rain wallpaper.")
    ap.add_argument("--theme", default="nixos", help="nixos (default) or matrix")
    ap.add_argument("--channel", default="public",
                    help="stream name; everyone on the same channel with a synced clock sees the same frame")
    ap.add_argument("--fps", type=float, default=30.0,
                    help="frame rate cap (default 30); frames land on whole refreshes of the screen")
    ap.add_argument("--pause-under", choices=hidden.POLICIES, default="maximized",
                    help="on KDE Plasma, stop drawing a screen while a maximized or full-screen window covers "
                         "it (maximized, the default), only while a full-screen one does (fullscreen), or never")
    ap.add_argument("--pacing", choices=("refresh", "timer"), default="refresh",
                    help=argparse.SUPPRESS)        # timer: build 4's frame timing, for the power sweep's comparison
    ap.add_argument("--host", choices=native.HOSTS, default="auto",
                    help="what draws the wallpaper on Wayland: auto (the native program when it is built, "
                         "else Python and GTK), native (the native program only) or gtk (Python and GTK, as on "
                         "X11 and in a window)")
    ap.add_argument("--logo", choices=("white", "colours", "none"), help="NixOS logo variant (theme default otherwise)")
    ap.add_argument("--background", metavar="IMAGE", help="use an image as the background instead of the theme gradient")
    ap.add_argument("--mask", metavar="IMAGE", help="greyscale mask (same framing as --background): white = keep bright, no rain")
    ap.add_argument("--bg-gamma", type=float, help="darkening curve for --background (default 2.0; 1 = unchanged)")
    ap.add_argument("--bg-gain", type=float,
                    help="background brightness: the gradient's (default 1; lower is darker) or --background's "
                         "(default 0.42; 1 = unchanged)")
    ap.add_argument("--rainbow", choices=("logo", "all", "off"),
                    help="colour cycling: logo (default), all (the rain too) or off")
    ap.add_argument("--spin", type=float, metavar="SECONDS", help="seconds per logo revolution (default 180, 0 = still)")
    ap.add_argument("--drift", type=float, metavar="FRACTION",
                    help="slow orbit of the logo / pan of the image, in screen heights (default 0.03, 0 = fixed)")
    ap.add_argument("--speed", type=float, metavar="F",
                    help="how fast the symbols fall, times the theme's (default 1; 0.25 to 4)")
    ap.add_argument("--density", type=float, metavar="F",
                    help="how often a column starts a new stream, times the theme's (default 1; 0 to 2.3)")
    ap.add_argument("--glow", type=float, metavar="F",
                    help="the glow around the centre and the logo, times the theme's (default 1; 0 = none)")
    ap.add_argument("--bloom", type=float, metavar="F",
                    help="the glow around the falling symbols, times the theme's (default 1; 0 = none)")
    ap.add_argument("--snow", choices=("on", "off"), help="the falling snowflakes (default on, where the theme has them)")
    ap.add_argument("--hieroglyphs", type=float, metavar="SHARE",
                    help="share of the changing symbols that are Egyptian hieroglyphs (default 0.15; 0 = none, 1 = only)")
    ap.add_argument("--scale", type=float, default=1.0, help="render resolution scale, e.g. 0.75 on weak GPUs")
    ap.add_argument("--layer", choices=("background", "bottom"),
                    help="Wayland layer (default: bottom on KDE Plasma, whose own desktop sits on the background layer)")
    ap.add_argument("--window", action="store_true", help="ordinary window instead of a wallpaper")
    ap.add_argument("--offset", type=float, default=0.0, help="add this many seconds to the clock")
    ap.add_argument("--time", type=float, help="freeze the clock at this UNIX time (screenshots, tests)")
    ap.add_argument("--screenshot", metavar="PNG", help="render one frame, save it, exit")
    ap.add_argument("--record", metavar="DIR", help="render a clip as numbered PNGs into DIR (from --time or now), exit")
    ap.add_argument("--record-seconds", type=float, default=8.0)
    ap.add_argument("--record-fps", type=float, default=30.0)
    ap.add_argument("--size", help="window size for --window / --record (default 1280x720), or the size "
                                   "--benchmark draws at (default: the first screen), e.g. 1920x1080")
    ap.add_argument("--list-themes", action="store_true")
    ap.add_argument("--benchmark", action="store_true",
                    help="time each pass on this machine's graphics card, print the table, exit")
    ap.add_argument("--power-sweep", action="store_true",
                    help="measure the graphics card's power with syncrain at several settings (a few minutes), "
                         "print the table and save it; every screen goes black in its last two phases")
    ap.add_argument("--sweep-seconds", type=int, default=25, help="seconds per --power-sweep phase (default 25)")
    ap.add_argument("--diagnose", action="store_true",
                    help="check whether syncrain can draw on this machine, print what it found, exit")
    ap.add_argument("--build", action=_ShowBuild, help="print the build number and the stream fingerprint, exit")
    ap.add_argument("--version", action=_ShowBuild, help=argparse.SUPPRESS)   # the reflex spelling; says the build
    return ap.parse_args(argv)


def _preload_layer_shell():
    """gtk4-layer-shell has to be loaded before libwayland-client. Nix wrappers set LD_PRELOAD;
    elsewhere, re-exec once with it set."""
    if not os.environ.get("WAYLAND_DISPLAY") or os.environ.get("SYNCRAIN_REEXEC"):
        return
    if "gtk4-layer-shell" in os.environ.get("LD_PRELOAD", ""):
        return
    import ctypes.util                         # only here: it brings subprocess with it
    lib = ctypes.util.find_library("gtk4-layer-shell")
    if not lib:
        return
    os.environ["LD_PRELOAD"] = (lib + " " + os.environ.get("LD_PRELOAD", "")).strip()
    os.environ["SYNCRAIN_REEXEC"] = "1"
    os.execv(sys.executable, [sys.executable, "-m", "syncrain"] + sys.argv[1:])


def _x11_desktop_hints(xid):
    """Mark an X11 window as the desktop: below everything, on all workspaces, not in taskbars."""
    try:
        x11 = ctypes.CDLL("libX11.so.6")
    except OSError:
        return
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XInternAtom.restype = ctypes.c_ulong
    x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x11.XChangeProperty.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
    x11.XMoveWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int]
    x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    dpy = x11.XOpenDisplay(None)
    if not dpy:
        return
    atom = lambda n: x11.XInternAtom(dpy, n.encode(), 0)  # noqa: E731

    def set_atoms(prop, names):
        arr = (ctypes.c_ulong * len(names))(*[atom(n) for n in names])
        x11.XChangeProperty(dpy, xid, atom(prop), 4, 32, 0, ctypes.cast(arr, ctypes.c_void_p), len(names))

    set_atoms("_NET_WM_WINDOW_TYPE", ["_NET_WM_WINDOW_TYPE_DESKTOP"])
    set_atoms("_NET_WM_STATE", ["_NET_WM_STATE_BELOW", "_NET_WM_STATE_STICKY",
                                "_NET_WM_STATE_SKIP_TASKBAR", "_NET_WM_STATE_SKIP_PAGER"])
    x11.XMoveWindow(dpy, xid, 0, 0)
    x11.XSync(dpy, 0)
    x11.XCloseDisplay(dpy)


def gl_context_problem(ctx, Gdk):
    """Why a realized GTK GL context cannot run the shaders, or None when it can.

    Which API a context gets is GTK's choice, not ours: it creates every context to share with
    the display's own, and since GTK 4.14 that one is OpenGL ES unless GDK_DEBUG=gl-prefer-gl.
    So a GLArea must not ask for a version only one of the two APIs has (desktop GL 3.3 asked
    of OpenGL ES is 3.3 > 3.2 and nothing is tried); it takes what GTK offers and checks it here.
    """
    es = ctx.get_api() == Gdk.GLAPI.GLES if hasattr(ctx, "get_api") else bool(ctx.get_use_es())
    have = tuple(ctx.get_version())
    need = MIN_GL[es]
    if have < need:
        api = "OpenGL ES" if es else "OpenGL"
        return es, f"{api} {have[0]}.{have[1]} is too old; syncrain needs {api} {need[0]}.{need[1]}"
    return es, None


def describe_context(ctx, Gdk):
    from . import gl
    es = ctx.get_api() == Gdk.GLAPI.GLES if hasattr(ctx, "get_api") else bool(ctx.get_use_es())
    major, minor = ctx.get_version()
    try:
        renderer = gl.get_string(gl.GL_RENDERER) or "unknown renderer"
    except Exception:  # noqa: BLE001 - informational only
        renderer = "unknown renderer"
    return f"{'OpenGL ES' if es else 'OpenGL'} {major}.{minor} on {renderer}"


def use_gl_renderer():
    """Have GTK put our OpenGL picture on screen with its own OpenGL renderer, unless told otherwise.

    On Wayland, GTK 4.16 and later draw windows with Vulkan where they can, and then hand a GLArea's
    OpenGL texture to Vulkan every frame: without the GL driver's dmabuf export, by copying it through
    the processor, a full screen per frame per screen. Its OpenGL renderer uses the texture where it
    is. (GTK 4.14 spells its newer OpenGL renderer "ngl"; "gl" there is the older one, which also
    uses the texture as it is.) A GSK_RENDERER set by the user wins; the power sweep compares both.

    With the OpenGL renderer, GTK's dmabuf support is turned off too (GDK_DISABLE=dmabuf, which
    GTK 4.16 and later read). From 4.16 a GLArea hands each frame over as a dmabuf where the driver
    can export one (NVIDIA's can, and Mesa's on real hardware), so that it could be given to the
    compositor directly; syncrain's frames never are, so every frame was exported, wrapped and
    imported back by the same renderer that could have drawn the texture itself, and the first one
    made GTK start a whole Vulkan renderer beside it (`gdk_vulkan_init_dmabuf`), kept for the life
    of the process. Without dmabufs the renderer draws the GLArea's texture as it is, as GTK 4.14
    does and as every machine without the export already did.
    """
    os.environ.setdefault("GSK_RENDERER", "gl")
    if os.environ["GSK_RENDERER"].strip().lower() in ("gl", "ngl", "opengl"):
        disabled = [f.strip() for f in os.environ.get("GDK_DISABLE", "").split(",") if f.strip()]
        if "dmabuf" not in disabled:
            os.environ["GDK_DISABLE"] = ",".join(disabled + ["dmabuf"])


def avoid_the_explicit_sync_leak():
    """NVIDIA's Wayland driver keeps a small allocation for every frame it presents while explicit
    sync is on: on the operator's desktop the wallpaper grew by about 0.9 MiB a minute (two screens
    at 30 fps), in either host, and only while it drew; on Mesa it stays flat. With explicit sync
    off the driver falls back to implicit sync, which does not leak; __GL_YIELD=USLEEP lets the
    driver sleep while it waits for a frame there, rather than spin. Both are NVIDIA's own
    variables, which other drivers ignore; a value the user set wins. Set before GTK starts and
    before the native wallpaper, which inherits them through execve."""
    os.environ.setdefault("__NV_DISABLE_EXPLICIT_SYNC", "1")
    os.environ.setdefault("__GL_YIELD", "USLEEP")


def _libc_function(name):
    """A glibc function by name, or None (another C library, or none of that name)."""
    try:
        return getattr(ctypes.CDLL(None), name)
    except (OSError, AttributeError):
        return None


#: How often freed memory goes back to the system while syncrain runs.
TRIM_SECONDS = 300


def settle_memory():
    """After startup (and after the screens changed): give back what starting left behind.

    Starting leaves garbage and freed memory inside the C heap: the decoded images uploaded to the
    card, the shader compiler's working space, the import machinery, the old screens' objects after
    a change. gc.collect frees what only cycles kept, and malloc_trim hands the free pages back to
    the system (glibc; elsewhere nothing happens). A frame makes no cycles, so after this the
    collector has nothing to do (none ran in 30 s of two screens at 30 fps).
    """
    gc.collect()
    trim = _libc_function("malloc_trim")
    if trim is not None:
        trim.argtypes = [ctypes.c_size_t]
        trim(0)


def resident_mib() -> float:
    """This process's resident memory (VmRSS), in MiB, or 0 where /proc does not say."""
    try:
        with open("/proc/self/status", encoding="ascii") as fh:
            return next(int(line.split()[1]) for line in fh if line.startswith("VmRSS:")) / 1024
    except (OSError, StopIteration, ValueError):
        return 0.0


def renderer_name(widget) -> str:
    """The short name of the renderer GTK draws this widget's window with."""
    native = widget.get_native()
    renderer = native.get_renderer() if native is not None else None
    if renderer is None:
        return "unknown"
    name = type(renderer).__name__.removeprefix("Gsk")      # PyGObject names it GLRenderer, C GskGLRenderer
    return {"GLRenderer": "gl", "NglRenderer": "ngl", "VulkanRenderer": "vulkan",
            "CairoRenderer": "cairo"}.get(name, name)


def debug_fps_interval() -> float:
    """SYNCRAIN_DEBUG_FPS: report the frame rate every N seconds (any non-number: every 5)."""
    value = os.environ.get("SYNCRAIN_DEBUG_FPS", "")
    if not value:
        return 0.0
    try:
        return max(0.5, float(value))
    except ValueError:
        return 5.0


DEBUG_FPS = debug_fps_interval()


def install_quit_signals(GLib, quit_callback):
    """Ctrl+C, `systemctl --user stop` and a closed terminal all end the main loop cleanly.

    PyGObject installs a SIGINT fallback that raises KeyboardInterrupt after the loop ends (the
    traceback build 2 printed on Ctrl+C) unless Python's default handler has already been
    replaced, so it is replaced first and GLib owns the signals from then on.
    """
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    def on_signal(*_):
        quit_callback()
        return GLib.SOURCE_REMOVE

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        GLib.unix_signal_add(GLib.PRIORITY_HIGH, sig, on_signal)


def main(argv=None):
    args = parse_args(argv)
    if args.list_themes:
        from .engine import load_meta
        for name, th in load_meta()["themes"].items():
            print(f"{name:10s} {th['label']}")
        return 0
    # Before GTK is imported: PyGObject initialises GTK on import, and GDK reads GDK_DISABLE then.
    use_gl_renderer()
    avoid_the_explicit_sync_leak()
    if args.host != "gtk" and not (args.power_sweep or args.benchmark or args.diagnose):
        if native.applies(args):
            path = native.binary()
            if path:
                why = native.run(args, sys.argv[1:] if argv is None else argv, path)   # returns only on failure
                print(f"syncrain: {why}; the GTK host draws instead", file=sys.stderr, flush=True)
            elif args.host == "native":
                print("syncrain: the native wallpaper is not built here (install.sh builds it; "
                      "`syncrain --diagnose` says what it needs)", file=sys.stderr)
                return 1
        elif args.host == "native":
            print("syncrain: the native wallpaper draws only the wallpaper on a Wayland session, paced by the "
                  "refresh; use --host gtk for X11, --window, --screenshot, --record and --pacing timer",
                  file=sys.stderr)
            return 1
    _preload_layer_shell()
    if args.power_sweep:
        from .power import run_sweep
        return run_sweep(args)
    if args.benchmark:
        from .bench import run_benchmark
        return run_benchmark(args)
    if args.diagnose:
        from .diagnose import run
        return run(args)

    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, GLib, Gtk

    Gtk.init()
    display = Gdk.Display.get_default()
    if display is None:
        print("syncrain: no display (run it inside your desktop session)", file=sys.stderr)
        return 1
    backend = type(display).__name__          # GdkWaylandDisplay / GdkX11Display
    from . import gl
    from .renderer import from_args as renderer_from_args

    LayerShell = None
    if "Wayland" in backend and not (args.window or args.record):
        try:
            gi.require_version("Gtk4LayerShell", "1.0")
            from gi.repository import Gtk4LayerShell as LayerShell
            if not LayerShell.is_supported():
                LayerShell = None
        except (ValueError, ImportError):
            LayerShell = None
        if LayerShell is None:
            print("syncrain: this Wayland compositor has no wlr-layer-shell support (GNOME?). "
                  "Use --window, or the web version in web/index.html.", file=sys.stderr)
            return 2

    # Until the first frame, and if OpenGL never comes, a window shows its theme background:
    # black, not the light grey a GTK window is by default.
    css = Gtk.CssProvider()
    rule = "window.syncrain { background-color: #000000; }"
    if hasattr(css, "load_from_string"):
        css.load_from_string(rule)
    else:
        css.load_from_data(rule.encode())
    add_provider = getattr(Gtk, "style_context_add_provider_for_display", None) \
        or Gtk.StyleContext.add_provider_for_display
    add_provider(display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    from .pacing import Pacer, spacing, steady

    class RainArea(Gtk.GLArea):
        def __init__(self, rects=None, screens=()):
            super().__init__()
            self.rects = rects                 # callable(width, height) -> [(x, y, w, h)] device px, or None
            self.screens = tuple(screens)      # connector names of the screens it shows (none: a window)
            self.renderer = None
            self.pacer = Pacer(args.fps)
            self.hidden = False                # every screen it shows is covered: nothing is drawn
            self._due = None                   # the GLib source that asks for the next frame
            self._drawn_for = 0                # the monotonic moment the frame being drawn is drawn for
            self.frames = 0                    # frames drawn since it was realized
            self._drawn = []                   # (GTK frame counter, target, drawn for) until GTK knows when shown
            self._shown = []                   # SYNCRAIN_DEBUG_FPS: (when shown, refresh interval, drawn for)
            # No set_required_version: see gl_context_problem. GTK's own minimums are GL 3.3 core
            # and GLES 3.0, exactly what the shaders need.
            self.set_has_depth_buffer(False)
            self.set_has_stencil_buffer(False)
            self.set_auto_render(False)
            self.connect("realize", self._realize)
            self.connect("unrealize", self._unrealize)
            self.connect("resize", self._resize)
            self.connect("render", self._render)
            self._off = {}                     # (w, h) -> (framebuffer, texture) for --scale
            self.fb = None

        def _resize(self, _area, w, h):            # framebuffer size in device pixels
            self.fb = (int(w), int(h))

        def _realize(self, _area):
            self.make_current()
            if self.get_error() is not None:
                app.fail(f"OpenGL is not available: {self.get_error().message}")
                return
            ctx = self.get_context()
            use_es, problem = gl_context_problem(ctx, Gdk)
            if problem:
                app.fail(problem)
                return
            try:
                r = renderer_from_args(args)
                r.init(use_es)
            except RuntimeError as e:          # a shader this driver will not compile
                app.fail(f"the shaders did not compile here: {e}")
                return
            self.renderer = r
            app.started(describe_context(ctx, Gdk) + f", GTK renderer {renderer_name(self)}")

        def _unrealize(self, _area):
            """The area is going (the screens changed, or the app stops): delete what was made for
            its context. Textures belong to every context GTK shares objects between, so they would
            outlive this one; the programs and textures every screen reads stay for the next one."""
            if self.renderer is None and not self._off:
                return
            self.make_current()
            # make_current does not say when it fails, and framebuffers and vertex arrays are each
            # context's own: delete only with this area's context current, never in GTK's.
            ctx = self.get_context()
            if self.get_error() is None and ctx is not None and Gdk.GLContext.get_current() == ctx:
                if self.renderer is not None:
                    self.renderer.release()
                gl.delete_framebuffers([fbo for fbo, _tex in self._off.values()])
                gl.delete_textures([tex for _fbo, tex in self._off.values()])
            self._off = {}
            self.renderer = None

        def _offscreen(self, w, h):                # one reduced-size target per viewport size (--scale)
            if (w, h) not in self._off:
                fbo, tex = gl.gen_framebuffer(), gl.gen_texture()
                gl.glBindTexture(gl.GL_TEXTURE_2D, tex)
                gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, w, h, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
                gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, tex, 0)
                self._off[(w, h)] = (fbo, tex)
            return self._off[(w, h)][0]

        def _moment(self):
            """The stream time this frame is drawn for: the refresh it will be shown on, when known."""
            now = GLib.get_monotonic_time()
            self._drawn_for = self.pacer.target if self.pacer.target is not None else now
            if args.time is not None:
                return args.time
            return time.time() + args.offset + (self._drawn_for - now) / 1e6

        def _schedule(self):
            """Ask for the next frame at the time the pacer gives (syncrain/pacing.py)."""
            if self._due is not None:
                GLib.source_remove(self._due)
                self._due = None
            if self.hidden or args.pacing == "timer":     # timer: App.tick asks, as in build 4
                return
            now = GLib.get_monotonic_time()
            refresh = vblank = 0
            clock = self.get_frame_clock()
            if clock is not None:
                refresh, vblank = clock.get_refresh_info(now)
            delay, _target = self.pacer.plan(now, refresh, vblank)
            self._due = GLib.timeout_add(max(1, int(delay // 1000)), self._on_due, priority=GLib.PRIORITY_HIGH)

        def _on_due(self):
            self._due = None
            if not self.hidden:
                self.queue_render()
            return GLib.SOURCE_REMOVE

        def set_hidden(self, value):
            """Covered: stop asking for frames. Shown again: draw at once, then on the cadence."""
            if value == self.hidden:
                return
            self.hidden = value
            if DEBUG_FPS:
                what = "covered, drawing stops" if value else "shown again, drawing resumes"
                print(f"syncrain: {', '.join(self.screens)} {what}", flush=True)
            if value:
                if self._due is not None:
                    GLib.source_remove(self._due)
                    self._due = None
            else:
                self.pacer.restart()
                self._frames, self._since = 0, time.monotonic()    # the next report counts from now
                self._drawn, self._shown = [], []
                self.queue_render()

        def retire(self):
            """The monitors changed and this area is being replaced: ask for no more frames."""
            self.hidden = True
            if self._due is not None:
                GLib.source_remove(self._due)
                self._due = None

        def _note_presented(self):
            """When GTK learns when a drawn frame was shown, tell the pacer whether it made its refresh
            (`Pacer.shown`), and keep it for the SYNCRAIN_DEBUG_FPS report. GTK holds 16 frames' timings."""
            clock = self.get_frame_clock()
            if clock is None:
                return
            waiting = []
            for counter, target, drawn_for in self._drawn:
                timings = clock.get_timings(counter)
                if timings is None:
                    continue
                if not timings.get_complete():
                    waiting.append((counter, target, drawn_for))
                    continue
                shown, refresh = timings.get_presentation_time(), timings.get_refresh_interval()
                if shown > 0:
                    if target is not None:
                        self.pacer.shown(target, shown, refresh)
                    if DEBUG_FPS:
                        self._shown.append((shown, refresh, drawn_for))
            self._drawn = waiting + [(clock.get_frame_counter(), self.pacer.target, self._drawn_for)]

        def _timing(self):
            """', spacing 2 refreshes 100%, steady 100%, lead 14.3 ms': of the frames shown since the last
            report, how many came the expected number of refreshes after the one before, how many were
            shown the usual delay after the moment they were drawn for (syncrain/pacing.py, steady), and
            how long before its refresh a frame is now asked for."""
            shown, self._shown = self._shown, self._shown[-1:]
            refresh = shown[-1][1] if shown else 0
            steps = spacing([p for p, _, _ in shown], refresh)
            if len(steps) < 2 or refresh <= 0:
                return ""
            n = self.pacer.step(refresh)
            even = 100.0 * sum(1 for s in steps if s == n) / len(steps)
            calm = 100.0 * steady([p - drawn_for for p, _, drawn_for in shown[1:]])
            return (f", spacing {n} refresh{'es' if n != 1 else ''} {even:.0f}%, steady {calm:.0f}%, "
                    f"lead {self.pacer.lead(refresh) / 1000:.1f} ms")

        def _render(self, _area, _ctx):
            if self.renderer is None:
                return False
            try:
                return self._draw()
            finally:
                # The next frame is asked for whatever happened to this one (a frame that raised
                # is reported by PyGObject and the wallpaper goes on), except after --screenshot
                # and --record, which end the app.
                if self.renderer is not None:
                    self._schedule()

        def _draw(self):
            if self.fb:                              # GLArea does not reset the viewport between frames
                W, H = self.fb
            else:
                s = self.get_scale_factor()
                W, H = self.get_width() * s, self.get_height() * s
            if W <= 0 or H <= 0:
                return False
            out = gl.get_integer(gl.GL_FRAMEBUFFER_BINDING)
            t = self._moment()
            for (x, y, w, h) in (self.rects(W, H) if self.rects else [(0, 0, W, H)]):
                if args.scale < 0.999:
                    sw, sh = max(64, round(w * args.scale)), max(36, round(h * args.scale))
                    off = self._offscreen(sw, sh)
                    self.renderer.render(t, off, 0, 0, sw, sh)
                    gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, off)
                    gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, out)
                    gl.glBlitFramebuffer(0, 0, sw, sh, x, y, x + w, y + h, gl.GL_COLOR_BUFFER_BIT, gl.GL_LINEAR)
                    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, out)
                else:
                    self.renderer.render(t, out, x, y, w, h)
            self._note_presented()
            self.frames += 1
            if self.frames == 1:
                app.settle_soon()
            if DEBUG_FPS:
                now = time.monotonic()
                self._frames = getattr(self, "_frames", 0) + 1
                if now - getattr(self, "_since", now) >= DEBUG_FPS:
                    print(f"syncrain: {self._frames / (now - self._since):.1f} fps at {W}x{H} "
                          f"(area {app.areas.index(self) if self in app.areas else 0}){self._timing()}",
                          flush=True)
                    self._frames, self._since = 0, now
                elif not hasattr(self, "_since"):
                    self._since = now
            if args.screenshot:
                self._save(out, W, H, args.screenshot)
                print(f"syncrain: saved {args.screenshot} ({W}x{H})", flush=True)
                self.renderer = None                 # one frame only
                GLib.idle_add(app.quit, priority=GLib.PRIORITY_HIGH)
            elif args.record:
                os.makedirs(args.record, exist_ok=True)
                n = max(1, round(args.record_seconds * args.record_fps))
                t0 = args.time if args.time is not None else time.time() + args.offset
                for i in range(n):
                    self.renderer.render(t0 + i / args.record_fps, out, 0, 0, W, H)
                    self._save(out, W, H, os.path.join(args.record, f"frame_{i:05d}.png"))
                print(f"syncrain: recorded {n} frames ({W}x{H}) into {args.record}", flush=True)
                self.renderer = None
                GLib.idle_add(app.quit, priority=GLib.PRIORITY_HIGH)
            return True

        @staticmethod
        def _save(fbo, W, H, path):
            from PIL import Image
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
            data = gl.read_pixels(0, 0, W, H)
            Image.frombytes("RGBA", (W, H), data).transpose(Image.FLIP_TOP_BOTTOM).convert("RGB").save(path)

    layer_name = args.layer or ("bottom" if "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "") else "background")

    class App(Gtk.Application):
        def __init__(self):
            super().__init__(application_id=None)
            self.windows, self.areas = [], []
            self.exit_code = 0
            self.announced = False
            self.screens = 0
            self.watch = None
            self.watch_said = False
            self._settle = None                # the GLib source that will settle memory, while it waits
            self.settled = False               # memory settled since the screens were last built

        def do_activate(self):
            self.hold()
            self.build()
            display.get_monitors().connect("items-changed", lambda *_: GLib.idle_add(self.rebuild))
            if args.pacing == "timer":
                GLib.timeout_add(max(1, int(round(1000.0 / max(1.0, args.fps)))), self.tick)
            self.start_watch()

        def tick(self):
            """--pacing timer: build 4's frame timing, a frame asked of every screen every 1/fps seconds."""
            for a in self.areas:
                if not a.hidden:
                    a.queue_render()
            return GLib.SOURCE_CONTINUE

        def start_watch(self):
            """On KDE Plasma, ask KWin which screens a window covers (syncrain/hidden.py)."""
            if args.pause_under == "never" or LayerShell is None or self.screens == 0:
                return
            watch = hidden.Watch(self.update_hidden, maximized=args.pause_under == "maximized")
            why = watch.start()
            if why is None:
                self.watch = watch
                GLib.timeout_add(1500, self._watch_check, False)
            elif "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "") or "not on the session bus" not in why:
                print(f"syncrain: {why}; drawing goes on under covering windows", flush=True)

        def _watch_check(self, retried):
            """No answer 1.5 s after the script was run: ask KWin to start it once more (hidden.Watch.retry);
            still none 1.5 s later: give up and draw as before."""
            if self.watch is None or self.watch.answered:
                return GLib.SOURCE_REMOVE
            if not retried:
                self.watch.retry()
                GLib.timeout_add(1500, self._watch_check, True)
                return GLib.SOURCE_REMOVE
            print("syncrain: KWin loaded the script but it reported nothing (KWin 5?); "
                  "drawing goes on under covering windows", flush=True)
            self.watch.stop()
            self.watch = None
            self.update_hidden()
            return GLib.SOURCE_REMOVE

        def update_hidden(self):
            if self.watch is not None and self.watch.answered and not self.watch_said:
                self.watch_said = True
                which = "maximized and full-screen" if args.pause_under == "maximized" else "full-screen"
                print(f"syncrain: drawing pauses on a screen under {which} windows (KWin)", flush=True)
            for a in self.areas:
                a.set_hidden(self.watch.hidden(a.screens) if self.watch is not None else False)

        def stop_watch(self):
            if self.watch is not None:
                self.watch.stop()
                self.watch = None

        def settle_soon(self):
            """Once every screen has drawn its first frame, startup is over: settle_memory, once."""
            if self._settle is None and not self.settled and self.areas and all(a.frames for a in self.areas):
                self._settle = GLib.timeout_add(500, self._settle_now)

        def _settle_now(self):
            self._settle = None
            self.settled = True
            settle_memory()
            if DEBUG_FPS:
                print(f"syncrain: memory handed back after the first frames ({resident_mib():.0f} MiB resident)",
                      flush=True)
            if not getattr(self, "_trimming", None):     # and again every five minutes, as the native one does
                self._trimming = GLib.timeout_add_seconds(TRIM_SECONDS, self._trim)
            return GLib.SOURCE_REMOVE

        @staticmethod
        def _trim():
            settle_memory()
            return GLib.SOURCE_CONTINUE

        def started(self, context):
            """One line when the first viewport is up: what draws, where (it lands in the journal)."""
            if not self.announced:
                self.announced = True
                n = self.screens
                where = "a window" if n == 0 else f"{n} screen{'s' if n != 1 else ''}"
                print(f"{build.describe()}: {context}, {where}", flush=True)

        def fail(self, reason):
            """Give the desktop back at once and exit with EXIT_NO_GL; said once, not once per screen."""
            if self.exit_code == 0:
                self.exit_code = EXIT_NO_GL
                print(f"syncrain: {reason}\n"
                      "syncrain: nothing can be drawn, so the wallpaper is closed again. "
                      "`syncrain --diagnose` shows what this machine offers.", file=sys.stderr, flush=True)
            for w in self.windows:
                w.set_visible(False)
            GLib.idle_add(self.quit, priority=GLib.PRIORITY_HIGH)

        def rebuild(self):
            for a in self.areas:
                a.retire()
            for w in self.windows:
                w.destroy()
            self.windows, self.areas = [], []
            if self._settle is not None:
                GLib.source_remove(self._settle)
                self._settle = None
            self.settled = False                       # settle again once the new screens have drawn
            self.build()
            self.update_hidden()
            return False

        def build(self):
            monitors = [display.get_monitors().get_item(i) for i in range(display.get_monitors().get_n_items())]
            windowed = args.window or args.record or (args.screenshot and not monitors)
            self.screens = 0 if windowed else len(monitors)
            if windowed:
                w, h = (int(v) for v in (args.size or "1280x720").lower().split("x"))
                self.add_window(Gtk.Window(application=self), RainArea(), size=(w, h))
            elif LayerShell is not None:
                layer = LayerShell.Layer.BOTTOM if layer_name == "bottom" else LayerShell.Layer.BACKGROUND
                for mon in monitors:
                    win = Gtk.Window(application=self)
                    LayerShell.init_for_window(win)
                    LayerShell.set_namespace(win, "syncrain")
                    LayerShell.set_layer(win, layer)
                    LayerShell.set_monitor(win, mon)
                    for edge in (LayerShell.Edge.LEFT, LayerShell.Edge.RIGHT, LayerShell.Edge.TOP, LayerShell.Edge.BOTTOM):
                        LayerShell.set_anchor(win, edge, True)
                    LayerShell.set_exclusive_zone(win, -1)
                    LayerShell.set_keyboard_mode(win, LayerShell.KeyboardMode.NONE)
                    connector = mon.get_connector()
                    self.add_window(win, RainArea(screens=(connector,) if connector else ()), click_through=True)
            else:                               # X11: one desktop window, one viewport per monitor
                geos = [m.get_geometry() for m in monitors] or [None]
                if geos[0] is None:
                    self.add_window(Gtk.Window(application=self), RainArea(), size=(1280, 720))
                    return
                x0 = min(g.x for g in geos); y0 = min(g.y for g in geos)
                bw = max(g.x + g.width for g in geos) - x0; bh = max(g.y + g.height for g in geos) - y0

                def rects(W, H, geos=geos, x0=x0, y0=y0, bw=bw, bh=bh):
                    sx, sy = W / bw, H / bh
                    return [(round((g.x - x0) * sx), round((bh - (g.y - y0) - g.height) * sy),
                             round(g.width * sx), round(g.height * sy)) for g in geos]
                win = Gtk.Window(application=self)
                self.add_window(win, RainArea(rects), size=(bw, bh), x11=True)

        def add_window(self, win, area, size=None, x11=False, click_through=False):
            win.add_css_class("syncrain")
            win.set_decorated(args.window)
            win.set_title("syncrain")
            if size:
                win.set_default_size(*size)
            win.set_child(area)
            if x11 and not args.window:
                win.realize()
                gi.require_version("GdkX11", "4.0")
                from gi.repository import GdkX11
                xid = GdkX11.X11Surface.get_xid(win.get_surface())
                _x11_desktop_hints(xid)
                win.connect("map", lambda *_: _x11_desktop_hints(xid))
            self.windows.append(win)
            self.areas.append(area)
            win.present()
            if click_through:                    # clicks pass through to whatever is underneath (Plasma's desktop)
                try:
                    import cairo
                    win.get_surface().set_input_region(cairo.Region())
                except Exception as e:  # noqa: BLE001 - cosmetic, never fatal
                    print(f"syncrain: could not make the wallpaper click-through: {e}", file=sys.stderr)

    app = App()
    install_quit_signals(GLib, app.quit)
    try:
        rc = app.run([])
    finally:
        app.stop_watch()                         # the script leaves KWin with us
    return app.exit_code or rc
