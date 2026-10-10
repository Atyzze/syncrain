"""`syncrain --benchmark`: what each pass costs this machine's graphics card, per frame.

Draws the stream offscreen at the first screen's size (or --size) for a few seconds, times every
pass with GPU timer queries where the context has them (desktop OpenGL always does, so the
benchmark asks GTK for desktop OpenGL first), else by waiting for each pass, and prints the table.
It answers "where does a frame's work go" on the card itself; `syncrain --power-sweep` answers
"what does that cost in watts".
"""
from __future__ import annotations

import ctypes
import os
import time

from . import build

FRAMES, WARMUP = 120, 10


class QueryTimer:
    """GL_TIME_ELAPSED queries around each pass, read after the frame."""

    method = "GPU timer queries"

    def __init__(self, gl, names):
        self.gl, self.names = gl, names
        self.ids = dict(zip(names, gl.gen_queries(len(names))))
        self.total = {n: 0.0 for n in names}
        self._result = ctypes.c_uint64(0)

    def begin(self, name):
        self.gl.glBeginQuery(self.gl.GL_TIME_ELAPSED, self.ids[name])

    def end(self, name):
        self.gl.glEndQuery(self.gl.GL_TIME_ELAPSED)

    def collect(self):
        for n, qid in self.ids.items():
            self.gl.glGetQueryObjectui64v(qid, self.gl.GL_QUERY_RESULT, ctypes.byref(self._result))
            self.total[n] += self._result.value / 1e6


class FinishTimer:
    """Wall time around each pass with glFinish on both sides (a little slower than the truth)."""

    method = "glFinish around each pass (this context has no timer queries)"

    def __init__(self, gl, names):
        self.gl, self.names = gl, names
        self.total = {n: 0.0 for n in names}
        self._t = 0.0

    def begin(self, name):
        self.gl.glFinish()
        self._t = time.perf_counter()

    def end(self, name):
        self.gl.glFinish()
        self.total[name] += (time.perf_counter() - self._t) * 1000.0

    def collect(self):
        pass


def screen_size(Gdk, display) -> tuple[int, int]:
    monitors = display.get_monitors()
    if monitors.get_n_items():
        mon = monitors.get_item(0)
        g, s = mon.get_geometry(), mon.get_scale_factor()
        return g.width * s, g.height * s
    return 1920, 1080


def run_benchmark(args) -> int:
    debug = os.environ.get("GDK_DEBUG", "")
    os.environ["GDK_DEBUG"] = ",".join(x for x in (debug, "gl-prefer-gl") if x)
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, Gtk
    Gtk.init()
    display = Gdk.Display.get_default()
    if display is None:
        print("syncrain: no display (run it inside your desktop session)")
        return 1
    from . import gl
    from .app import EXIT_NO_GL, describe_context, gl_context_problem
    from .renderer import from_args

    try:
        ctx = display.create_gl_context()
        ctx.realize()
    except Exception as e:  # noqa: BLE001 - GLib.Error carries the reason
        print(f"syncrain: no OpenGL context: {getattr(e, 'message', e)}")
        return EXIT_NO_GL
    ctx.make_current()
    use_es, problem = gl_context_problem(ctx, Gdk)
    if problem:
        print(f"syncrain: {problem}")
        return EXIT_NO_GL
    w, h = (int(v) for v in args.size.lower().split("x")) if args.size else screen_size(Gdk, display)
    r = from_args(args)
    r.init(use_es)
    fbo, tex = gl.gen_framebuffer(), gl.gen_texture()
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, w, h, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
    gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, tex, 0)
    moment = time.time() if args.time is None else args.time
    for i in range(WARMUP):
        r.render(moment + i / 30, fbo, 0, 0, w, h)
    gl.glFinish()
    timer = FinishTimer(gl, r.PASSES) if use_es else QueryTimer(gl, r.PASSES)
    r.timer = timer
    host = 0.0
    frames = FRAMES
    for i in range(frames):
        t0 = time.thread_time()
        r.render(moment + (WARMUP + i) / 30, fbo, 0, 0, w, h)
        host += time.thread_time() - t0
        timer.collect()
    r.timer = None
    gl.glFinish()
    print(f"{build.describe()} --benchmark")
    print(f"{describe_context(ctx, Gdk)}, {w}x{h}, {frames} frames, timed by {timer.method}")
    print(f"{'pass':12s} {'ms per frame':>12s}")
    total = 0.0
    for name in r.PASSES:
        ms = timer.total[name] / frames
        total += ms
        print(f"{name:12s} {ms:12.3f}")
    fps = args.fps or 30.0
    print(f"{'all passes':12s} {total:12.3f}   the card is busy {min(100.0, total * fps / 10):.1f}% of the time at "
          f"{fps:g} fps on one screen of this size")
    print(f"{'host CPU':12s} {host / frames * 1000:12.3f}   Python and the driver issuing a frame (one CPU thread)")
    return 0
