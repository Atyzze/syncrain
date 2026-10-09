"""What syncrain keeps on the graphics card, and for how long (syncrain/renderer.py, syncrain/gl.py).

The programs and the textures every frame reads are made once per process and used by every screen's
context, since GTK makes every context of a display share objects; each screen's own targets are
deleted when its area goes. Build 7 made all of it again for every screen and never deleted any of
it: textures belong to the whole share group, so they outlived the screen, and every monitor change
(a screen unplugged, or a DisplayPort screen waking from sleep) left another set behind.
"""
from __future__ import annotations

import json
import subprocess
import sys

from tests.conftest import app_env
from tests.support import MOMENT

PROBE = """
import json, sys
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk
Gtk.init()
display = Gdk.Display.get_default()
from syncrain import gl
from syncrain.app import gl_context_problem
from syncrain.renderer import Renderer

W, H = 320, 180

def context():
    ctx = display.create_gl_context()
    ctx.realize()
    ctx.make_current()
    return ctx

def target():
    fbo, tex = gl.gen_framebuffer(), gl.gen_texture()
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, W, H, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
    gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, tex, 0)
    return fbo

def frame(renderer, fbo):
    renderer.render(float(sys.argv[1]), fbo, 0, 0, W, H)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
    return gl.read_pixels(0, 0, W, H)

first = context()
use_es, _ = gl_context_problem(first, Gdk)
a = Renderer(); a.init(use_es)
picture_a = frame(a, target())
second = context()
b = Renderer(); b.init(use_es)
picture_b = frame(b, target())
own = list(b.targets[(W, H)].tex.values())
out = {"shared": a.shared is b.shared, "same": picture_a == picture_b,
       "lit": sum(picture_a[0::4]) > 0, "own_before": all(gl.glIsTexture(t) for t in own)}
b.release()
out["own_after"] = any(gl.glIsTexture(t) for t in own)
out["vao"] = b.vao
first.make_current()
out["shared_alive"] = bool(gl.glIsProgram(a.shared.prog["composite"].id)) and bool(gl.glIsTexture(a.shared.tex["atlas"]))
print(json.dumps(out))
"""

BAD_CALL = """
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk
Gtk.init()
ctx = Gdk.Display.get_default().create_gl_context()
ctx.realize()
ctx.make_current()
from syncrain import gl
try:
    gl.glBindTexture(0x1234, 0)
except gl.GLError as e:
    print("raised:", e)
else:
    print("nothing raised")
"""


def probe(x_display, root, script, *args, **env):
    return subprocess.run([sys.executable, "-c", script, *args], cwd=root, env=app_env(x_display, **env),
                          capture_output=True, text=True, timeout=120)


def test_a_second_screen_uses_the_first_one_s_programs_and_textures(x_display, root):
    done = probe(x_display, root, PROBE, str(MOMENT))
    assert done.returncode == 0, done.stdout + done.stderr
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out["shared"], "the second context made its own programs and textures"
    assert out["lit"] and out["same"], "the second context drew a different frame from the same objects"
    assert out["own_before"]


def test_a_screen_that_goes_takes_its_own_objects_and_leaves_the_shared_ones(x_display, root):
    done = probe(x_display, root, PROBE, str(MOMENT))
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert not out["own_after"], "the screen's targets outlived it"
    assert out["vao"] == 0
    assert out["shared_alive"], "releasing one screen took what the others draw with"


def test_with_error_checking_on_a_frame_makes_no_opengl_error(app, tmp_path):
    shot = tmp_path / "frame.png"
    done = app(["--window", "--size", "640x360", "--time", str(MOMENT), "--screenshot", str(shot)],
               SYNCRAIN_GL_DEBUG="1")
    assert done.returncode == 0 and shot.exists(), done.stdout + done.stderr
    assert "GLError" not in done.stderr, done.stderr


def test_error_checking_names_the_call_that_failed(x_display, root):
    done = probe(x_display, root, BAD_CALL, SYNCRAIN_GL_DEBUG="1")
    assert "raised: glBindTexture" in done.stdout and "0x0500" in done.stdout, done.stdout + done.stderr
