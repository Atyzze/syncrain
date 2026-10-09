"""`syncrain --diagnose`: can syncrain draw on this machine, and if not, why not.

Everything the wallpaper needs, checked the way the wallpaper uses it, without showing a window:
the session, the libraries, the graphics card from sysfs, the OpenGL context GTK hands out (the
same kind a wallpaper window gets: it shares with the display's own), the shaders compiled on
it, and one frame drawn offscreen and looked at. The verdict comes first; send the whole output
when something does not work.
"""
from __future__ import annotations

import glob
import os
import platform
import sys
import time

from . import build

VENDORS = {"0x10de": "NVIDIA", "0x1002": "AMD", "0x8086": "Intel", "0x1af4": "virtio", "0x15ad": "VMware",
           "0x1234": "QEMU"}


def graphics_cards() -> list[str]:
    """Every DRM card: vendor, PCI id, kernel driver, and whether firmware used it to boot."""
    cards = []
    for dev in sorted(glob.glob("/sys/class/drm/card[0-9]*/device")):
        card = dev.split("/")[-2]
        if "-" in card:          # connectors (card0-DP-1) share the device
            continue

        def read(name, dev=dev):
            try:
                with open(os.path.join(dev, name), encoding="ascii") as fh:
                    return fh.read().strip()
            except OSError:
                return ""
        vendor, device = read("vendor"), read("device")
        driver = os.path.basename(os.path.realpath(os.path.join(dev, "driver"))) if os.path.exists(
            os.path.join(dev, "driver")) else "no driver"
        boot = " (boot display)" if read("boot_vga") == "1" else ""
        cards.append(f"{card}: {VENDORS.get(vendor, vendor or 'unknown')} {device}, driver {driver}{boot}")
    try:
        with open("/proc/driver/nvidia/version", encoding="ascii") as fh:
            cards.append("NVIDIA kernel module: " + fh.readline().strip())
    except OSError:
        pass
    return cards or ["no DRM devices visible"]


def session_lines() -> list[str]:
    keys = ("XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP", "WAYLAND_DISPLAY", "DISPLAY", "GDK_BACKEND",
            "GDK_DEBUG", "GDK_DISABLE", "GSK_RENDERER", "LIBGL_ALWAYS_SOFTWARE", "__GLX_VENDOR_LIBRARY_NAME",
            "__EGL_VENDOR_LIBRARY_FILENAMES", "SYNCRAIN_WALLPAPER", "__NV_DISABLE_EXPLICIT_SYNC", "__GL_YIELD")
    lines = [f"{k}={os.environ[k]}" for k in keys if os.environ.get(k)]
    preload = os.environ.get("LD_PRELOAD", "")
    lines.append("gtk4-layer-shell preloaded: " + ("yes" if "gtk4-layer-shell" in preload else "no"))
    return lines


def library_lines(Gtk) -> tuple[list[str], bool | None]:
    """The versions that matter, and whether the compositor offers a wallpaper layer (None: not asked)."""
    import gi
    import PIL
    lines = [f"Python {platform.python_version()}, PyGObject {gi.__version__}, Pillow {PIL.__version__}",
             f"GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}"]
    layer = None
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell as LayerShell
        layer = bool(LayerShell.is_supported())
        lines.append("gtk4-layer-shell {}.{}.{}, wallpaper layer offered by the compositor: {}".format(
            LayerShell.get_major_version(), LayerShell.get_minor_version(), LayerShell.get_micro_version(),
            "yes" if layer else "no"))
    except (ValueError, ImportError):
        lines.append("gtk4-layer-shell: not installed")
    return lines, layer


def draw_one_frame(args, use_es, gl):
    """Compile everything and draw the theme offscreen at a fixed moment; return (mean, lit share)."""
    from .renderer import Renderer
    w, h = 640, 360
    r = Renderer(theme=args.theme, channel=args.channel, logo=args.logo,
                 rainbow=args.rainbow, spin=args.spin, drift=args.drift)
    r.init(use_es)
    fbo, tex = gl.gen_framebuffer(), gl.gen_texture()
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, w, h, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
    gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, tex, 0)
    status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
    if status != gl.GL_FRAMEBUFFER_COMPLETE:
        raise RuntimeError(f"offscreen target incomplete (status {int(status):#x})")
    started = time.monotonic()
    r.render(1791331200.0, fbo, 0, 0, w, h)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
    data = gl.read_pixels(0, 0, w, h)
    elapsed = time.monotonic() - started
    lum = [data[i] + data[i + 1] + data[i + 2] for i in range(0, len(data), 4)]
    mean = sum(lum) / (3 * len(lum))
    lit = sum(1 for v in lum if v > 3 * 60) / len(lum)
    return mean, lit, elapsed


def window_renderer(Gtk) -> str:
    """Which renderer GTK gives a window here: realise one without showing it, ask, destroy it."""
    from .app import renderer_name
    win = Gtk.Window()
    try:
        win.realize()
        return renderer_name(win)
    except Exception as e:  # noqa: BLE001 - informational only
        return f"unknown ({e})"
    finally:
        win.destroy()


def screen_lines(display) -> list[str]:
    """Every screen GTK sees: its connector, size, scale and refresh rate (what the frame timing uses)."""
    monitors = display.get_monitors()
    lines = []
    for i in range(monitors.get_n_items()):
        m = monitors.get_item(i)
        g = m.get_geometry()
        rate = f"{m.get_refresh_rate() / 1000:.2f} Hz" if m.get_refresh_rate() else "refresh rate unknown"
        scale = m.get_scale() if hasattr(m, "get_scale") else m.get_scale_factor()
        lines.append(f"{m.get_connector() or f'screen {i}'}: {g.width}x{g.height} at {g.x},{g.y}, "
                     f"scale {scale:g}, {rate}")
    return lines or ["no screens"]


def covering_lines(args) -> list[str]:
    """Whether KWin answers the script that pauses covered screens, and what it says right now."""
    from gi.repository import GLib
    from .hidden import Watch
    if args.pause_under == "never":
        return ["--pause-under never: KWin is not asked"]
    watch = Watch(lambda: None, maximized=args.pause_under == "maximized")
    why = watch.start()
    if why:
        return [f"not watched: {why}" + ("" if "not on the session bus" in why else "; drawing goes on under windows")]
    context = GLib.MainContext.default()

    def wait(seconds):
        deadline = time.monotonic() + seconds
        settle = None
        while time.monotonic() < deadline:             # the first answer, then a moment for every screen's
            context.iteration(False)
            if watch.answered and settle is None:
                settle = time.monotonic() + 0.3
            if settle is not None and time.monotonic() > settle:
                break
            time.sleep(0.01)
    wait(1.5)
    if not watch.answered:                             # see hidden.Watch.retry
        watch.retry()
        wait(1.5)
    watch.stop()
    if not watch.answered:
        return ["KWin ran the script but it reported nothing (KWin 5?); drawing goes on under windows"]
    which = "maximized and full-screen" if args.pause_under == "maximized" else "full-screen"
    lines = [f"KWin answers: drawing pauses on a screen under {which} windows"]
    lines += [f"{name}: {'covered right now' if covered else 'not covered'}"
              for name, covered in sorted(watch.covered.items())]
    if watch.showing_desktop:
        lines.append("KWin is showing the desktop (nothing counts as covered)")
    return lines


def native_lines(args) -> list[str]:
    """Whether the native wallpaper is built, and what it finds here (`syncrain-wallpaper --probe`)."""
    from . import native
    path = native.binary()
    if not path:
        return ["not built, so the GTK host draws the wallpaper (install.sh builds it with a C compiler, "
                "pkg-config, wayland-scanner and the libwayland and libdbus headers)"]
    lines = [f"program: {path}"]
    if not native.wayland_session():
        return lines + ["not used in this session: it draws the wallpaper on Wayland only"]
    _code, found = native.probe(args, path)
    return lines + found


def run(args) -> int:
    out: list[str] = []
    verdict = None
    code = 0

    def section(title, lines):
        out.append(f"{title}:")
        out.extend(f"  {line}" for line in lines)

    section("session", session_lines())
    section("graphics cards", graphics_cards())
    from .app import avoid_the_explicit_sync_leak, use_gl_renderer
    use_gl_renderer()                        # what the wallpaper itself does, so the answer is about it
    avoid_the_explicit_sync_leak()
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk, Gtk
    except (ImportError, ValueError) as e:
        verdict, code = f"GTK 4 is not usable from Python: {e}", 1
        Gtk = Gdk = None
    display = None
    if Gtk is not None:
        Gtk.init()
        display = Gdk.Display.get_default()
        if display is None:
            verdict, code = "no display: run this inside your desktop session, not over SSH or a TTY", 1
    if display is not None:
        backend = type(display).__name__.replace("Gdk", "").replace("Display", "") or "unknown"
        libs, layer = library_lines(Gtk)
        section("libraries", libs + [f"GDK backend: {backend}"])
        section("screens", screen_lines(display))
        from . import gl
        from .app import EXIT_NO_GL, gl_context_problem

        gl_lines = []
        ctx = None
        try:
            ctx = display.create_gl_context()
            ctx.realize()
        except Exception as e:  # noqa: BLE001 - GLib.Error carries the reason
            verdict, code = f"no OpenGL context: {getattr(e, 'message', e)}", EXIT_NO_GL
            ctx = None
        if ctx is not None:
            ctx.make_current()
            use_es, problem = gl_context_problem(ctx, Gdk)
            for name in ("GL_VENDOR", "GL_RENDERER", "GL_VERSION", "GL_SHADING_LANGUAGE_VERSION"):
                try:
                    gl_lines.append(f"{name}: {gl.get_string(getattr(gl, name))}")
                except Exception as e:  # noqa: BLE001
                    gl_lines.append(f"{name}: unreadable ({e})")
            major, minor = ctx.get_version()
            gl_lines.insert(0, f"GTK hands out: {'OpenGL ES' if use_es else 'OpenGL'} {major}.{minor}")
            if problem:
                verdict, code = problem, EXIT_NO_GL
            else:
                try:
                    mean, lit, elapsed = draw_one_frame(args, use_es, gl)
                    gl_lines.append(f"test frame: 640x360 in {elapsed * 1000:.0f} ms, mean brightness {mean:.1f}, "
                                    f"{lit * 100:.1f}% of pixels lit")
                    if mean < 1.0:
                        verdict, code = "the shaders compiled but the test frame came out black", 1
                except Exception as e:  # noqa: BLE001 - a compile log or a GL error, reported whole
                    verdict, code = f"drawing failed: {e}", 1
            gl_lines.append(f"GTK renderer for windows: {window_renderer(Gtk)} "
                            f"(GSK_RENDERER={os.environ.get('GSK_RENDERER', '')})")
            section("OpenGL", gl_lines)
        if backend == "Wayland" and layer:
            section("covering windows", covering_lines(args))
        section("native wallpaper", native_lines(args))
        if verdict is None:
            kind = "OpenGL ES" if use_es else "OpenGL"
            verdict = f"OK, syncrain can draw here ({kind} {major}.{minor})"
            if backend == "Wayland" and not layer:
                verdict += ", but only with --window: this compositor offers no wallpaper layer"
    print(f"{build.describe()} --diagnose")
    print(f"verdict: {verdict}")
    print("\n".join(out))
    sys.stdout.flush()
    return code
