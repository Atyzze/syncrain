"""OpenGL renderer for the GTK host: the same six passes as the web runner (`syncrain/gl.py` calls).

Expects a current GL 3.3 core (or GLES 3.0) context, e.g. inside a Gtk.GLArea "render" handler.

Every pixel is computed on the GPU, by the shaders, which the driver compiles to the card's own
code; this file only issues the passes. A program keeps its uniforms, so what never changes (the
theme, the channel, the textures' units) is set once in `init`, and a frame sets only the clock and
what depends on the viewport: about forty calls into OpenGL, each one C call through ctypes, with
every value that depends only on the viewport's size worked out once per size (`geometry`).

What never changes is made once per process, not once per screen: the programs and the textures
read by every frame (`Shared`). GTK creates every context of a display to share objects with the
display's own (GTK 4.14 and later, which syncrain needs), so a second screen, or a screen that comes
back after the monitors changed, uses the first one's programs and textures. They live as long as
the display; what is made per screen (the frame's intermediate textures, their framebuffers, the
vertex array) is deleted with `Renderer.release` when the screen's area goes.

The native wallpaper (`syncrain/native/`) draws the same frames from the same sources: its scene
(`syncrain/native.py`) is made from `shader_bodies`, `texture_sources` and `static_uniforms` below,
and its per-size and per-frame arithmetic is a port of `geometry` and `Renderer.render`, compared
value for value by tests/native/.
"""
import os
from types import SimpleNamespace

from . import engine, gl
from .gl import (GL_BLEND, GL_CLAMP_TO_EDGE, GL_COLOR_ATTACHMENT0, GL_DEPTH_TEST, GL_FRAGMENT_SHADER,
                 GL_FRAMEBUFFER, GL_LINEAR, GL_LINEAR_MIPMAP_LINEAR, GL_NEAREST, GL_RGBA, GL_RGBA8,
                 GL_SCISSOR_TEST, GL_TEXTURE0, GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER,
                 GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_TRIANGLES, GL_UNPACK_ALIGNMENT, GL_UNSIGNED_BYTE,
                 GL_VERTEX_SHADER, GL_COMPILE_STATUS, GL_LINK_STATUS)

UNIT = dict(state=0, field=1, atlas=2, lut=3, words=4, bloom=5, logo=6, bg=7, mask=8, src=9)
PROGRAMS = ("state", "field", "glyphs", "blur", "composite")
#: The textures every frame binds, in the order it binds them.
STATIC_TEXTURES = ("atlas", "lut", "words", "logo", "bg", "mask")

HEADER_ES = "#version 300 es\nprecision highp float;\nprecision highp int;\nprecision highp sampler2D;\n"
HEADER_GL = "#version 330 core\n"


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def shader_bodies(data_dir=engine.DATA_DIR) -> dict:
    """Each program's source with its includes in place, without the version header (which depends on
    the API the context has): "vert" and one per name in PROGRAMS."""
    sh = os.path.join(data_dir, "shaders")
    src = {n: _read(os.path.join(sh, f)) for n, f in dict(
        common="common.glsl", rain="rain.glsl", vert="fullscreen.vert", state="state.frag", field="field.frag",
        glyphs="glyphs.frag", blur="blur.frag", composite="composite.frag").items()}

    def assemble(name):
        lines = []
        for line in src[name].splitlines():
            s = line.strip()
            lines.append(src[s[len("//#include "):].strip()] if s.startswith("//#include ") else line)
        return "\n".join(lines) + "\n"

    return {n: assemble(n) for n in ("vert", *PROGRAMS)}


class Program:
    def __init__(self, vert_src, frag_src, name):
        self.id = gl.glCreateProgram()
        shaders = []
        for kind, src in ((GL_VERTEX_SHADER, vert_src), (GL_FRAGMENT_SHADER, frag_src)):
            sh = gl.glCreateShader(kind)
            gl.shader_source(sh, src)
            gl.glCompileShader(sh)
            if not gl.shader_iv(sh, GL_COMPILE_STATUS):
                raise RuntimeError(f"{name}: {gl.shader_info_log(sh)}")
            gl.glAttachShader(self.id, sh)
            shaders.append(sh)
        gl.glLinkProgram(self.id)
        if not gl.program_iv(self.id, GL_LINK_STATUS):
            raise RuntimeError(f"{name}: {gl.program_info_log(self.id)}")
        for sh in shaders:                     # the linked program keeps what it needs; the sources go
            gl.glDetachShader(self.id, sh)
            gl.glDeleteShader(sh)
        self._loc = {}

    def loc(self, name):
        if name not in self._loc:
            self._loc[name] = gl.glGetUniformLocation(self.id, name.encode())
        return self._loc[name]

    def i(self, name, v): gl.glUniform1i(self.loc(name), int(v))
    def ui(self, name, v): gl.glUniform1ui(self.loc(name), int(v) & 0xFFFFFFFF)
    def f(self, name, v): gl.glUniform1f(self.loc(name), float(v))
    def f2(self, name, a, b): gl.glUniform2f(self.loc(name), float(a), float(b))
    def f3(self, name, v): gl.glUniform3f(self.loc(name), *[float(x) for x in v])
    def f4(self, name, v): gl.glUniform4f(self.loc(name), *[float(x) for x in v])
    def f4v(self, name, flat): gl.uniform4fv(self.loc(name), flat)

    def set(self, name, kind, values):
        """One uniform as static_uniforms lists it."""
        if kind == "f4v":
            self.f4v(name, values)
        elif kind == "f2":
            self.f2(name, *values)
        elif kind in ("f3", "f4"):
            getattr(self, kind)(name, values)
        else:
            getattr(self, kind)(name, values[0])


def _tex(w, h, data, linear=False, mip=False):
    t = gl.gen_texture()
    gl.glBindTexture(GL_TEXTURE_2D, t)
    gl.glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
    gl.glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    if mip:
        gl.glGenerateMipmap(GL_TEXTURE_2D)
    mn = GL_LINEAR_MIPMAP_LINEAR if mip else (GL_LINEAR if linear else GL_NEAREST)
    gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, mn)
    gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR if (linear or mip) else GL_NEAREST)
    gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    return t


#: How a texture is filtered: renderer._tex's (linear, mip) by name.
FILTERS = {"nearest": (False, False), "linear": (True, False), "mip": (False, True)}


def rgba_pil(path_or_img, max_side=4096):
    """(width, height, RGBA bytes) of an image, as Pillow converts it, no side above max_side."""
    from PIL import Image
    im = path_or_img if isinstance(path_or_img, Image.Image) else Image.open(path_or_img)
    im = im.convert("RGBA")
    if max(im.size) > max_side:
        k = max_side / max(im.size)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    size = im.size
    data = im.tobytes()
    del im                                     # the decoded image goes before the upload's copy is made
    return size[0], size[1], data


def _straight_rgba(path, max_side):
    """(width, height, bytes) of an image file that GTK's own loader reads as 8-bit RGBA with straight
    alpha, else None. For the bundled glyph atlas and logos that is exactly what Pillow's
    convert("RGBA") gives, byte for byte (checked on GTK 4.14 and 4.22), and the GTK host has GTK's
    loader in memory already, so it does not need Pillow's few mebibytes for them."""
    try:
        import gi
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk
        tex = Gdk.Texture.new_from_filename(path)
        w, h = tex.get_width(), tex.get_height()
        if int(tex.get_format()) != int(Gdk.MemoryFormat.R8G8B8A8) or max(w, h) > max_side:
            return None
        down = Gdk.TextureDownloader.new(tex)
        down.set_format(Gdk.MemoryFormat.R8G8B8A8)
        if hasattr(down, "set_color_state") and hasattr(tex, "get_color_state"):
            down.set_color_state(tex.get_color_state())      # the file's own colours: no conversion
        data, stride = down.download_bytes()
        del tex, down
        raw = data.get_data()
        del data
        if stride != w * 4:
            raw = b"".join(raw[y * stride:y * stride + w * 4] for y in range(h))
        return w, h, raw
    except Exception:  # noqa: BLE001 - any failure here is Pillow's to handle
        return None


def rgba_bundled_with_gtk(path, max_side=4096):
    """rgba_pil for the bundled images, through GTK's loader when it reads them as they are."""
    return _straight_rgba(os.fspath(path), max_side) or rgba_pil(path, max_side)


def texture_sources(r, bundled=rgba_pil):
    """Every texture a frame reads: ({name: (width, height, filter, bytes)}, bg_size, mask_bbox).
    `bundled` decodes the images that come with syncrain; an image the user names (--background,
    --mask) always goes through Pillow."""
    out = {}
    w, h, data = bundled(os.path.join(r.data_dir, "atlas.png"))
    out["atlas"] = (w, h, "mip", data)
    out["lut"] = (256, 1, "nearest", engine.lut_bytes(r.th))
    wb, n_words = engine.words_bytes(r.th)
    out["words"] = (16, n_words, "nearest", wb)
    if r.logo_choice != "none":
        w, h, data = bundled(os.path.join(r.data_dir, f"logo-{r.logo_choice}.png"))
        out["logo"] = (w, h, "mip", data)
    else:
        out["logo"] = (1, 1, "linear", bytes(4))
    bg_size = None
    if r.background:
        w, h, data = rgba_pil(r.background)
        out["bg"], bg_size = (w, h, "mip", data), (w, h)
    else:
        out["bg"] = (1, 1, "linear", bytes([0, 0, 0, 255]))
    mask_bbox = None
    if r.mask:
        from PIL import Image
        mimg = Image.open(r.mask).convert("L")
        bbox = mimg.point(lambda v: 255 if v > 127 else 0).getbbox()
        if bbox:
            mask_bbox = (bbox[0] / mimg.width, bbox[1] / mimg.height, bbox[2] / mimg.width, bbox[3] / mimg.height)
        w, h, data = rgba_pil(mimg.convert("RGBA"))
        out["mask"] = (w, h, "mip", data)
    else:
        out["mask"] = (1, 1, "linear", bytes(4))
    return out, bg_size, mask_bbox


def static_uniforms(r):
    """Everything a frame does not change: [(program, name, kind, values)], kinds as Program.set takes
    them. The GTK host sets these once; the native wallpaper gets them in its scene."""
    th, rain, c, bg = r.th, r.th["rain"], r.th["colors"], r.th["background"]
    out = []

    def put(program, name, kind, *values):
        out.append((program, name, kind, values))

    put("state", "uSeed", "ui", r.seed)
    put("state", "uLUT", "i", UNIT["lut"]); put("state", "uWords", "i", UNIT["words"])
    put("state", "uNumWords", "i", len(th["words"]))
    put("state", "uDensity", "f", rain["density"]); put("state", "uWordRate", "f", rain["wordRate"])
    put("state", "uGlintRate", "f", rain["glintRate"])
    put("state", "uContrast", "i", rain["contrast"])

    put("field", "uState", "i", UNIT["state"])

    for name in ("glyphs", "composite"):
        put(name, "uSeed", "ui", r.seed)
        put(name, "uState", "i", UNIT["state"]); put(name, "uAtlas", "i", UNIT["atlas"])
        for uniform, key in (("cDeep", "deep"), ("cMid", "mid"), ("cPale", "pale"), ("cHead", "head")):
            put(name, uniform, "f3", *c[key])
        put(name, "uContrast", "i", rain["contrast"])

    put("blur", "uSrc", "i", UNIT["src"])

    for name, key in (("uField", "field"), ("uBloom", "bloom"), ("uLogo", "logo"), ("uBg", "bg"), ("uMask", "mask")):
        put("composite", name, "i", UNIT[key])
    put("composite", "uBgMode", "i", 1 if r.background else 0)
    put("composite", "bgTop", "f3", *bg["top"]); put("composite", "bgBot", "f3", *bg["bottom"])
    put("composite", "bgCenter", "f3", *bg["center"]); put("composite", "bgVignette", "f", bg["vignette"])
    put("composite", "uBgGamma", "f", r.bg_gamma); put("composite", "uBgGain", "f", r.bg_gain)
    put("composite", "uHasLogo", "i", 1 if (r.logo_choice != "none" and not r.background) else 0)
    put("composite", "uHasMask", "i", 1 if r.mask else 0)
    put("composite", "cGlow", "f3", *c["glow"]); put("composite", "cLogoGlow", "f3", *th["logo"]["glow"])
    put("composite", "uBloomK", "f", rain["bloom"]); put("composite", "uVeil", "f", rain["veil"])
    put("composite", "uLogoSize", "f", th["logo"]["size"]); put("composite", "uLogoGlowK", "f", th["logo"]["glowStrength"])
    for k, v in r.motion.items():
        put("composite", k, "f", v)
    snow = th["snow"][:4]
    pad = [None] * (4 - len(snow))
    put("composite", "uSnowN", "i", len(snow))
    put("composite", "uSnowA", "f4v", *sum(([s["cell"], s["speed"], s["density"], s["bright"]] if s else [0] * 4
                                             for s in snow + pad), []))
    put("composite", "uSnowB", "f4v", *sum(([s["rmin"], s["rmax"], s["sway"], s["star"]] if s else [0] * 4
                                             for s in snow + pad), []))
    put("composite", "uSnowC", "f4v", *sum(([*s["color"], s["front"]] if s else [0] * 4 for s in snow + pad), []))
    return out


def geometry(w, h, cols, r):
    """Every value a frame sets that depends only on the viewport's size."""
    g = SimpleNamespace(w=w, h=h, cols=cols)
    g.cell = max(w / cols, 12.0)                 # narrow viewports show the middle of the stream
    g.col0 = (cols - w / g.cell) / 2
    g.rows = int(-(-h // g.cell))
    g.qw, g.qh = max(16, round(w / 4)), max(9, round(h / 4))
    if r.bg_size:
        g.scale, g.offset = engine.cover_fit(w, h, *r.bg_size)
    else:
        g.scale, g.offset = (1.0, 1.0), (0.0, 0.0)
    g.keep = tuple(float(v) for v in r._keep_rect(w, h, cols, g.scale, g.offset, g.cell, g.col0))
    g.sigma = 0.2 * g.cell / 4
    g.step_h, g.step_v = (1.0 / g.qw, 0.0), (0.0, 1.0 / g.qh)
    return g


class Targets:
    """Offscreen textures for one viewport size, and its geometry."""

    def __init__(self, w, h, cols, renderer):
        g = geometry(w, h, cols, renderer)
        self.__dict__.update(vars(g))
        self.tex, self.fbo = {}, {}
        for name, (tw, th, lin) in dict(state=(cols, self.rows, False), field=(cols, self.rows, True),
                                        glyphs=(self.qw, self.qh, True), blurA=(self.qw, self.qh, True),
                                        blurB=(self.qw, self.qh, True)).items():
            t = _tex(tw, th, None, linear=lin)
            f = gl.gen_framebuffer()
            gl.glBindFramebuffer(GL_FRAMEBUFFER, f)
            gl.glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, t, 0)
            self.tex[name], self.fbo[name] = t, f

    def delete(self):
        gl.delete_framebuffers(self.fbo.values())
        gl.delete_textures(self.tex.values())
        self.fbo, self.tex = {}, {}


class Shared:
    """What never changes, made once per process and used by every screen's context: the five
    programs, with their uniforms that never change already set, and the textures every frame reads.

    `Shared.get` hands out the one already made when the current context can use it (it shares
    objects with the context that made it, which GTK 4.14 and later always arrange), else makes one.
    """

    _made = {}

    @classmethod
    def get(cls, renderer, use_es):
        key = renderer.resource_key(use_es)
        shared = cls._made.get(key)
        if shared is None or not shared.usable_here():
            shared = cls(renderer, use_es)
            cls._made[key] = shared
        return shared

    @classmethod
    def forget(cls):
        """Drop every record (the objects stay with their contexts); for tests that tear contexts down."""
        cls._made.clear()

    def __init__(self, r, use_es):
        header = HEADER_ES if use_es else HEADER_GL
        bodies = shader_bodies(r.data_dir)
        vert = header + bodies["vert"]
        self.prog = {n: Program(vert, header + bodies[n], n) for n in PROGRAMS}
        sources, self.bg_size, self.mask_bbox = texture_sources(r, rgba_bundled_with_gtk)
        self.tex = {}
        for name in STATIC_TEXTURES:
            w, h, kind, data = sources.pop(name)
            linear, mip = FILTERS[kind]
            self.tex[name] = _tex(w, h, data, linear=linear, mip=mip)
            del data
        self.binds = tuple((GL_TEXTURE0 + UNIT[k], self.tex[k]) for k in STATIC_TEXTURES)
        r.bg_size, r.mask_bbox = self.bg_size, self.mask_bbox
        for program, name, kind, values in static_uniforms(r):
            p = self.prog[program]
            gl.glUseProgram(p.id)
            p.set(name, kind, values)
        # the locations a frame sets, looked up now: a frame makes no name lookups
        L = {n: self.prog[n].loc for n in PROGRAMS}
        self.loc = dict(
            state=tuple(L["state"](u) for u in ("uSec", "uFrac", "uCols", "uRows", "uKeep")),
            field=tuple(L["field"](u) for u in ("uCols", "uRows")),
            glyphs=tuple(L["glyphs"](u) for u in ("uSec", "uFrac", "uCols", "uRows", "uCell", "uColOffset",
                                                  "uRes", "uTarget")),
            blur=tuple(L["blur"](u) for u in ("uSigma", "uStep")),
            composite=tuple(L["composite"](u) for u in ("uSec", "uFrac", "uCols", "uRows", "uCell", "uColOffset",
                                                        "uRes", "uOrigin", "uBgScale", "uBgOffset")),
        )
        # Another context may use all this next: it is complete before anyone else sees it (the
        # rule for objects changed in one context and used in another, OpenGL 4.6 appendix D.3.1).
        gl.glFinish()

    def usable_here(self):
        """The current context shares objects with the one that made these."""
        return bool(gl.glIsProgram(self.prog["composite"].id)) and bool(gl.glIsTexture(self.tex["atlas"]))


class Renderer:
    def __init__(self, theme="nixos", channel="public", logo=None, background=None, mask=None,
                 bg_gamma=None, bg_gain=None, rainbow=None, spin=None, drift=None, data_dir=engine.DATA_DIR):
        self.meta = engine.load_meta(data_dir)
        if theme not in self.meta["themes"]:
            raise SystemExit(f"unknown theme {theme!r}; available: {', '.join(self.meta['themes'])}")
        self.theme_name, self.th = theme, self.meta["themes"][theme]
        self.channel = channel
        self.seed = engine.channel_seed(channel)
        self.logo_choice = logo or self.th["logo"]["default"]
        self.background, self.mask = background, mask
        dark = background is not None
        self.bg_gamma = bg_gamma if bg_gamma is not None else (2.0 if dark else 1.0)
        self.bg_gain = bg_gain if bg_gain is not None else (0.42 if dark else 1.0)
        self.motion = engine.motion(self.th, rainbow=rainbow, spin=spin, drift=drift)
        self.data_dir = data_dir
        self.epoch0, self.cols = self.meta["epoch0"], self.meta["cols"]
        self.targets = {}
        self.vao = 0
        self.shared = None
        self.bg_size = self.mask_bbox = None
        self.ready = False

    def resource_key(self, use_es):
        """Everything the shared programs and textures depend on: two renderers with the same key
        draw with the same objects."""
        return (use_es, self.data_dir, self.theme_name, self.seed, self.logo_choice, self.background, self.mask,
                self.bg_gamma, self.bg_gain, tuple(sorted(self.motion.items())))

    def keep_mode(self):
        """Which cells the hidden words keep clear of, as the native scene says it:
        ("logo", size, drift), ("mask", bbox, drift) or ("none",). Needs mask_bbox known."""
        if self.logo_choice != "none" and not self.background:
            return ("logo", self.th["logo"]["size"], self.motion["uDrift"])
        if self.mask_bbox:
            return ("mask", self.mask_bbox, self.motion["uDrift"])
        return ("none",)

    # ------------------------------------------------------------------ setup
    def init(self, use_es: bool):
        self.shared = Shared.get(self, use_es)
        self.bg_size, self.mask_bbox = self.shared.bg_size, self.shared.mask_bbox
        self.vao = gl.gen_vertex_array()        # a vertex array belongs to one context: one per renderer
        self.ready = True

    def release(self):
        """Delete what this renderer made for its own context (call with that context current). The
        shared programs and textures stay for the next screen."""
        for t in self.targets.values():
            t.delete()
        self.targets.clear()
        if self.vao:
            gl.delete_vertex_arrays([self.vao])
            self.vao = 0
        self.ready = False

    def _targets(self, w, h):
        key = (w, h)
        if key not in self.targets:
            if len(self.targets) > 8:
                for t in self.targets.values():
                    t.delete()
                self.targets.clear()
            self.targets[key] = Targets(w, h, self.cols, self)
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
    def _pass(self, name, fbo, w, h, x=0, y=0):
        gl.glBindFramebuffer(GL_FRAMEBUFFER, fbo)
        gl.glViewport(x, y, w, h)
        if self.timer:
            self.timer.begin(name)
        gl.glDrawArrays(GL_TRIANGLES, 0, 3)
        if self.timer:
            self.timer.end(name)

    #: The passes in the order a frame runs them (the benchmark reports them under these names).
    PASSES = ("state", "field", "glyphs", "blur-h", "blur-v", "composite")
    timer = None                      # set by the benchmark: begin(name) / end(name) around each pass

    def render(self, unix_time, out_fbo, x, y, w, h):
        """Draw one viewport (x, y, w, h in framebuffer pixels, GL origin bottom-left) into out_fbo."""
        sec, frac = engine.split_time(unix_time, self.epoch0)
        tg = self.targets.get((w, h)) or self._targets(w, h)
        s = self.shared
        prog, loc = s.prog, s.loc
        uniform1ui, uniform1f, uniform1i = gl.glUniform1ui, gl.glUniform1f, gl.glUniform1i
        uniform2f, use, active, bind = gl.glUniform2f, gl.glUseProgram, gl.glActiveTexture, gl.glBindTexture
        gl.glDisable(GL_BLEND)
        gl.glDisable(GL_DEPTH_TEST)
        gl.glDisable(GL_SCISSOR_TEST)
        gl.glBindVertexArray(self.vao)
        for unit, tex in s.binds:
            active(unit)
            bind(GL_TEXTURE_2D, tex)
        cols, rows = tg.cols, tg.rows

        u_sec, u_frac, u_cols, u_rows, u_keep = loc["state"]
        use(prog["state"].id); uniform1ui(u_sec, sec); uniform1f(u_frac, frac)
        uniform1i(u_cols, cols); uniform1i(u_rows, rows)
        gl.glUniform4f(u_keep, *tg.keep)
        self._pass("state", tg.fbo["state"], cols, rows)

        active(GL_TEXTURE0 + UNIT["state"]); bind(GL_TEXTURE_2D, tg.tex["state"])
        u_cols, u_rows = loc["field"]
        use(prog["field"].id)
        uniform1i(u_cols, cols); uniform1i(u_rows, rows)
        self._pass("field", tg.fbo["field"], cols, rows)

        u_sec, u_frac, u_cols, u_rows, u_cell, u_col0, u_res, u_target = loc["glyphs"]
        use(prog["glyphs"].id); uniform1ui(u_sec, sec); uniform1f(u_frac, frac)
        uniform1i(u_cols, cols); uniform1i(u_rows, rows); uniform1f(u_cell, tg.cell); uniform1f(u_col0, tg.col0)
        uniform2f(u_res, w, h); uniform2f(u_target, tg.qw, tg.qh)
        self._pass("glyphs", tg.fbo["glyphs"], tg.qw, tg.qh)

        u_sigma, u_step = loc["blur"]
        use(prog["blur"].id)
        uniform1f(u_sigma, tg.sigma)
        active(GL_TEXTURE0 + UNIT["src"]); bind(GL_TEXTURE_2D, tg.tex["glyphs"]); uniform2f(u_step, *tg.step_h)
        self._pass("blur-h", tg.fbo["blurA"], tg.qw, tg.qh)
        bind(GL_TEXTURE_2D, tg.tex["blurA"]); uniform2f(u_step, *tg.step_v)
        self._pass("blur-v", tg.fbo["blurB"], tg.qw, tg.qh)

        active(GL_TEXTURE0 + UNIT["field"]); bind(GL_TEXTURE_2D, tg.tex["field"])
        active(GL_TEXTURE0 + UNIT["bloom"]); bind(GL_TEXTURE_2D, tg.tex["blurB"])
        u_sec, u_frac, u_cols, u_rows, u_cell, u_col0, u_res, u_origin, u_bgscale, u_bgoffset = loc["composite"]
        use(prog["composite"].id); uniform1ui(u_sec, sec); uniform1f(u_frac, frac)
        uniform1i(u_cols, cols); uniform1i(u_rows, rows); uniform1f(u_cell, tg.cell); uniform1f(u_col0, tg.col0)
        uniform2f(u_res, w, h); uniform2f(u_origin, x, y)
        uniform2f(u_bgscale, *tg.scale); uniform2f(u_bgoffset, *tg.offset)
        self._pass("composite", out_fbo, w, h, x, y)
