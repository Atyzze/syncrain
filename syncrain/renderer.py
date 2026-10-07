"""OpenGL renderer for the native app: the same six passes as the web runner, using PyOpenGL.

Expects a current GL 3.3 core (or GLES 3.0) context, e.g. inside a Gtk.GLArea "render" handler.

Every pixel is computed on the GPU, by the shaders, which the driver compiles to the card's own
code; this file only issues the passes. A program keeps its uniforms, so what never changes (the
theme, the channel, the textures' units) is set once in `init`, and a frame sets only the clock and
what depends on the viewport: about forty calls into OpenGL instead of about a hundred and ten.
"""
import ctypes
import os

import OpenGL

OpenGL.ERROR_CHECKING = bool(os.environ.get("SYNCRAIN_GL_DEBUG"))
from OpenGL import GL  # noqa: E402
from PIL import Image  # noqa: E402

from . import engine  # noqa: E402

UNIT = dict(state=0, field=1, atlas=2, lut=3, words=4, bloom=5, logo=6, bg=7, mask=8, src=9)
PROGRAMS = ("state", "field", "glyphs", "blur", "composite")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class Program:
    def __init__(self, vert_src, frag_src, name):
        self.id = GL.glCreateProgram()
        for kind, src in ((GL.GL_VERTEX_SHADER, vert_src), (GL.GL_FRAGMENT_SHADER, frag_src)):
            sh = GL.glCreateShader(kind)
            GL.glShaderSource(sh, src)
            GL.glCompileShader(sh)
            if not GL.glGetShaderiv(sh, GL.GL_COMPILE_STATUS):
                raise RuntimeError(f"{name}: {GL.glGetShaderInfoLog(sh).decode(errors='replace')}")
            GL.glAttachShader(self.id, sh)
        GL.glLinkProgram(self.id)
        if not GL.glGetProgramiv(self.id, GL.GL_LINK_STATUS):
            raise RuntimeError(f"{name}: {GL.glGetProgramInfoLog(self.id).decode(errors='replace')}")
        self._loc = {}

    def loc(self, name):
        if name not in self._loc:
            self._loc[name] = GL.glGetUniformLocation(self.id, name)
        return self._loc[name]

    def i(self, name, v): GL.glUniform1i(self.loc(name), int(v))
    def ui(self, name, v): GL.glUniform1ui(self.loc(name), int(v) & 0xFFFFFFFF)
    def f(self, name, v): GL.glUniform1f(self.loc(name), float(v))
    def f2(self, name, a, b): GL.glUniform2f(self.loc(name), float(a), float(b))
    def f3(self, name, v): GL.glUniform3f(self.loc(name), *[float(x) for x in v])
    def f4(self, name, v): GL.glUniform4f(self.loc(name), *[float(x) for x in v])
    def f4v(self, name, flat): GL.glUniform4fv(self.loc(name), len(flat) // 4, (ctypes.c_float * len(flat))(*flat))


def _tex(w, h, data, linear=False, mip=False):
    t = GL.glGenTextures(1)
    GL.glBindTexture(GL.GL_TEXTURE_2D, t)
    GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
    GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, w, h, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, data)
    if mip:
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
    mn = GL.GL_LINEAR_MIPMAP_LINEAR if mip else (GL.GL_LINEAR if linear else GL.GL_NEAREST)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, mn)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR if (linear or mip) else GL.GL_NEAREST)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
    return t


def _image_tex(path_or_img, max_side=4096):
    im = path_or_img if isinstance(path_or_img, Image.Image) else Image.open(path_or_img)
    im = im.convert("RGBA")
    if max(im.size) > max_side:
        k = max_side / max(im.size)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    return _tex(im.width, im.height, im.tobytes(), mip=True), im.size


class Targets:
    """Offscreen textures for one viewport size."""

    def __init__(self, w, h, cols):
        self.w, self.h, self.cols = w, h, cols
        self.cell = max(w / cols, 12.0)          # narrow viewports show the middle of the stream
        self.col0 = (cols - w / self.cell) / 2
        self.rows = int(-(-h // self.cell))
        self.qw, self.qh = max(16, round(w / 4)), max(9, round(h / 4))
        self.tex, self.fbo = {}, {}
        for name, (tw, th, lin) in dict(state=(cols, self.rows, False), field=(cols, self.rows, True),
                                        glyphs=(self.qw, self.qh, True), blurA=(self.qw, self.qh, True),
                                        blurB=(self.qw, self.qh, True)).items():
            t = _tex(tw, th, None, linear=lin)
            f = GL.glGenFramebuffers(1)
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, f)
            GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, t, 0)
            self.tex[name], self.fbo[name] = t, f

    def delete(self):
        GL.glDeleteFramebuffers(len(self.fbo), list(self.fbo.values()))
        GL.glDeleteTextures(list(self.tex.values()))


class Renderer:
    def __init__(self, theme="nixos", channel="public", logo=None, background=None, mask=None,
                 bg_gamma=None, bg_gain=None, rainbow=None, spin=None, drift=None, data_dir=engine.DATA_DIR):
        self.meta = engine.load_meta(data_dir)
        if theme not in self.meta["themes"]:
            raise SystemExit(f"unknown theme {theme!r}; available: {', '.join(self.meta['themes'])}")
        self.theme_name, self.th = theme, self.meta["themes"][theme]
        self.seed = engine.channel_seed(channel)
        self.logo_choice = logo or self.th["logo"]["default"]
        self.background, self.mask = background, mask
        dark = background is not None
        self.bg_gamma = bg_gamma if bg_gamma is not None else (2.0 if dark else 1.0)
        self.bg_gain = bg_gain if bg_gain is not None else (0.42 if dark else 1.0)
        self.motion = engine.motion(self.th, rainbow=rainbow, spin=spin, drift=drift)
        self.data_dir = data_dir
        self.targets = {}
        self.ready = False

    # ------------------------------------------------------------------ setup
    def init(self, use_es: bool):
        sh = os.path.join(self.data_dir, "shaders")
        src = {n: _read(os.path.join(sh, f)) for n, f in dict(
            common="common.glsl", rain="rain.glsl", vert="fullscreen.vert", state="state.frag", field="field.frag",
            glyphs="glyphs.frag", blur="blur.frag", composite="composite.frag").items()}
        header = ("#version 300 es\nprecision highp float;\nprecision highp int;\nprecision highp sampler2D;\n"
                  if use_es else "#version 330 core\n")

        def assemble(name):
            lines = []
            for line in src[name].splitlines():
                s = line.strip()
                lines.append(src[s[len("//#include "):].strip()] if s.startswith("//#include ") else line)
            return header + "\n".join(lines) + "\n"

        vert = assemble("vert")
        self.prog = {n: Program(vert, assemble(n), n) for n in PROGRAMS}
        self.vao = GL.glGenVertexArrays(1)
        self.tex = {}
        self.tex["atlas"], _ = _image_tex(os.path.join(self.data_dir, "atlas.png"))
        self.tex["lut"] = _tex(256, 1, engine.lut_bytes(self.th))
        wb, self.n_words = engine.words_bytes(self.th)
        self.tex["words"] = _tex(16, self.n_words, wb)
        if self.logo_choice != "none":
            self.tex["logo"], _ = _image_tex(os.path.join(self.data_dir, f"logo-{self.logo_choice}.png"))
        else:
            self.tex["logo"] = _tex(1, 1, bytes(4), linear=True)
        self.bg_size = None
        if self.background:
            self.tex["bg"], self.bg_size = _image_tex(self.background)
        else:
            self.tex["bg"] = _tex(1, 1, bytes([0, 0, 0, 255]), linear=True)
        self.mask_bbox = None
        if self.mask:
            mimg = Image.open(self.mask).convert("L")
            bbox = mimg.point(lambda v: 255 if v > 127 else 0).getbbox()
            if bbox:
                self.mask_bbox = (bbox[0] / mimg.width, bbox[1] / mimg.height, bbox[2] / mimg.width, bbox[3] / mimg.height)
            self.tex["mask"], _ = _image_tex(mimg.convert("RGBA"))
        else:
            self.tex["mask"] = _tex(1, 1, bytes(4), linear=True)
        self._set_static_uniforms()
        self.ready = True

    def _set_static_uniforms(self):
        """Everything a frame does not change, once: the theme, the channel, the texture units."""
        th, rain, c, bg = self.th, self.th["rain"], self.th["colors"], self.th["background"]

        p = self.prog["state"]; GL.glUseProgram(p.id)
        p.ui("uSeed", self.seed)
        p.i("uLUT", UNIT["lut"]); p.i("uWords", UNIT["words"]); p.i("uNumWords", len(th["words"]))
        p.f("uDensity", rain["density"]); p.f("uWordRate", rain["wordRate"]); p.f("uGlintRate", rain["glintRate"])
        p.i("uContrast", rain["contrast"])

        p = self.prog["field"]; GL.glUseProgram(p.id)
        p.i("uState", UNIT["state"])

        for name in ("glyphs", "composite"):
            p = self.prog[name]; GL.glUseProgram(p.id)
            p.ui("uSeed", self.seed)
            p.i("uState", UNIT["state"]); p.i("uAtlas", UNIT["atlas"])
            p.f3("cDeep", c["deep"]); p.f3("cMid", c["mid"]); p.f3("cPale", c["pale"]); p.f3("cHead", c["head"])
            p.i("uContrast", rain["contrast"])

        p = self.prog["blur"]; GL.glUseProgram(p.id)
        p.i("uSrc", UNIT["src"])

        p = self.prog["composite"]; GL.glUseProgram(p.id)
        for name, key in (("uField", "field"), ("uBloom", "bloom"), ("uLogo", "logo"), ("uBg", "bg"), ("uMask", "mask")):
            p.i(name, UNIT[key])
        p.i("uBgMode", 1 if self.background else 0)
        p.f3("bgTop", bg["top"]); p.f3("bgBot", bg["bottom"]); p.f3("bgCenter", bg["center"]); p.f("bgVignette", bg["vignette"])
        p.f("uBgGamma", self.bg_gamma); p.f("uBgGain", self.bg_gain)
        p.i("uHasLogo", 1 if (self.logo_choice != "none" and not self.background) else 0)
        p.i("uHasMask", 1 if self.mask else 0)
        p.f3("cGlow", c["glow"]); p.f3("cLogoGlow", th["logo"]["glow"])
        p.f("uBloomK", rain["bloom"]); p.f("uVeil", rain["veil"])
        p.f("uLogoSize", th["logo"]["size"]); p.f("uLogoGlowK", th["logo"]["glowStrength"])
        for k, v in self.motion.items():
            p.f(k, v)
        snow = th["snow"][:4]
        pad = [None] * (4 - len(snow))
        p.i("uSnowN", len(snow))
        p.f4v("uSnowA", sum(([s["cell"], s["speed"], s["density"], s["bright"]] if s else [0] * 4 for s in snow + pad), []))
        p.f4v("uSnowB", sum(([s["rmin"], s["rmax"], s["sway"], s["star"]] if s else [0] * 4 for s in snow + pad), []))
        p.f4v("uSnowC", sum(([*s["color"], s["front"]] if s else [0] * 4 for s in snow + pad), []))

    def _targets(self, w, h):
        key = (w, h)
        if key not in self.targets:
            if len(self.targets) > 8:
                for t in self.targets.values():
                    t.delete()
                self.targets.clear()
            self.targets[key] = Targets(w, h, self.meta["cols"])
        return self.targets[key]

    def _keep_rect(self, w, h, cols, scale, offset, cell=None, col0=0.0):
        cell = cell or w / cols
        if self.logo_choice != "none" and not self.background:
            # the logo's square box contains it at any rotation; widen by the drift
            half = self.th["logo"]["size"] * h / 2 / cell + self.motion["uDrift"] * h / cell + 1
            rc = h / 2 / cell
            return (cols / 2 - half, rc - half, cols / 2 + half, rc + half)
        if self.mask_bbox:
            x0, y0, x1, y1 = self.mask_bbox      # image uv -> screen px -> cells
            sx0, sy0 = (x0 - offset[0]) / scale[0] * w, (y0 - offset[1]) / scale[1] * h
            sx1, sy1 = (x1 - offset[0]) / scale[0] * w, (y1 - offset[1]) / scale[1] * h
            m = 1 + self.motion["uDrift"] * h / cell * 2       # the image pans slowly
            return (col0 + sx0 / cell - m, sy0 / cell - m, col0 + sx1 / cell + m, sy1 / cell + m)
        return (-1, -1, -1, -1)

    # ------------------------------------------------------------------ frame
    def _bind(self, unit, tex):
        GL.glActiveTexture(GL.GL_TEXTURE0 + unit)
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)

    def _clock(self, p, sec, frac):
        p.ui("uSec", sec)
        p.f("uFrac", frac)

    def _grid(self, p, tg):
        p.i("uCols", tg.cols); p.i("uRows", tg.rows)
        p.f("uCell", tg.cell); p.f("uColOffset", tg.col0)

    def _pass(self, name, fbo, w, h, x=0, y=0):
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
        GL.glViewport(x, y, w, h)
        if self.timer:
            self.timer.begin(name)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        if self.timer:
            self.timer.end(name)

    #: The passes in the order a frame runs them (the benchmark reports them under these names).
    PASSES = ("state", "field", "glyphs", "blur-h", "blur-v", "composite")
    timer = None                      # set by the benchmark: begin(name) / end(name) around each pass

    def render(self, unix_time, out_fbo, x, y, w, h):
        """Draw one viewport (x, y, w, h in framebuffer pixels, GL origin bottom-left) into out_fbo."""
        sec, frac = engine.split_time(unix_time, self.meta["epoch0"])
        tg = self._targets(w, h)
        GL.glDisable(GL.GL_BLEND)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_SCISSOR_TEST)
        GL.glBindVertexArray(self.vao)
        for k in ("atlas", "lut", "words", "logo", "bg", "mask"):
            self._bind(UNIT[k], self.tex[k])
        if self.bg_size:
            scale, offset = engine.cover_fit(w, h, *self.bg_size)
        else:
            scale, offset = (1.0, 1.0), (0.0, 0.0)

        p = self.prog["state"]; GL.glUseProgram(p.id); self._clock(p, sec, frac)
        p.i("uCols", tg.cols); p.i("uRows", tg.rows)
        p.f4("uKeep", self._keep_rect(w, h, tg.cols, scale, offset, tg.cell, tg.col0))
        self._pass("state", tg.fbo["state"], tg.cols, tg.rows)

        self._bind(UNIT["state"], tg.tex["state"])
        p = self.prog["field"]; GL.glUseProgram(p.id)
        p.i("uCols", tg.cols); p.i("uRows", tg.rows)
        self._pass("field", tg.fbo["field"], tg.cols, tg.rows)

        p = self.prog["glyphs"]; GL.glUseProgram(p.id); self._clock(p, sec, frac); self._grid(p, tg)
        p.f2("uRes", w, h); p.f2("uTarget", tg.qw, tg.qh)
        self._pass("glyphs", tg.fbo["glyphs"], tg.qw, tg.qh)

        p = self.prog["blur"]; GL.glUseProgram(p.id)
        p.f("uSigma", 0.2 * tg.cell / 4)
        self._bind(UNIT["src"], tg.tex["glyphs"]); p.f2("uStep", 1.0 / tg.qw, 0.0)
        self._pass("blur-h", tg.fbo["blurA"], tg.qw, tg.qh)
        self._bind(UNIT["src"], tg.tex["blurA"]); p.f2("uStep", 0.0, 1.0 / tg.qh)
        self._pass("blur-v", tg.fbo["blurB"], tg.qw, tg.qh)

        self._bind(UNIT["field"], tg.tex["field"]); self._bind(UNIT["bloom"], tg.tex["blurB"])
        p = self.prog["composite"]; GL.glUseProgram(p.id); self._clock(p, sec, frac); self._grid(p, tg)
        p.f2("uRes", w, h); p.f2("uOrigin", x, y)
        p.f2("uBgScale", *scale); p.f2("uBgOffset", *offset)
        self._pass("composite", out_fbo, w, h, x, y)
