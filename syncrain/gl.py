"""The OpenGL calls syncrain makes, straight to the driver, through the pointers GTK itself uses.

GTK reaches OpenGL through libepoxy, which picks each function for the context that is current:
OpenGL or OpenGL ES, through EGL or GLX, on any distribution (Nix included, where the libraries are
not on a search path). libepoxy keeps one pointer per function, `epoxy_glUseProgram` and so on;
calling those pointers through ctypes is one C call per OpenGL call. The wrapper library this
replaces (PyOpenGL) imported a module per OpenGL version and extension, a hundred thousand Python
objects, and numpy when it was installed, for the forty calls a frame makes.

Every function here must be called with a context current (a GLArea's render or realize handler,
or a context made current by hand); libepoxy resolves a function the first time it is called, for
that context. Only functions that exist in both OpenGL 3.3 and OpenGL ES 3.0 are called in the
wallpaper; `glGetQueryObjectui64v` (desktop OpenGL) is called by the benchmark on desktop OpenGL
only.

SYNCRAIN_GL_DEBUG=1 checks glGetError after every call and raises GLError naming the call.
"""
from __future__ import annotations

import ctypes
import os

# The enums syncrain uses (khronos.org/registry/OpenGL/api/GL/glcorearb.h).
GL_NO_ERROR = 0
GL_TRIANGLES = 0x0004
GL_COLOR_BUFFER_BIT = 0x00004000
GL_BLEND = 0x0BE2
GL_DEPTH_TEST = 0x0B71
GL_SCISSOR_TEST = 0x0C11
GL_UNPACK_ALIGNMENT = 0x0CF5
GL_PACK_ALIGNMENT = 0x0D05
GL_TEXTURE_2D = 0x0DE1
GL_UNSIGNED_BYTE = 0x1401
GL_RGBA = 0x1908
GL_VENDOR = 0x1F00
GL_RENDERER = 0x1F01
GL_VERSION = 0x1F02
GL_NEAREST = 0x2600
GL_LINEAR = 0x2601
GL_LINEAR_MIPMAP_LINEAR = 0x2703
GL_TEXTURE_MAG_FILTER = 0x2800
GL_TEXTURE_MIN_FILTER = 0x2801
GL_TEXTURE_WRAP_S = 0x2802
GL_TEXTURE_WRAP_T = 0x2803
GL_CLAMP_TO_EDGE = 0x812F
GL_RGBA8 = 0x8058
GL_TEXTURE0 = 0x84C0
GL_QUERY_RESULT = 0x8866
GL_TIME_ELAPSED = 0x88BF
GL_FRAGMENT_SHADER = 0x8B30
GL_VERTEX_SHADER = 0x8B31
GL_COMPILE_STATUS = 0x8B81
GL_LINK_STATUS = 0x8B82
GL_INFO_LOG_LENGTH = 0x8B84
GL_SHADING_LANGUAGE_VERSION = 0x8B8C
GL_FRAMEBUFFER_BINDING = 0x8CA6
GL_READ_FRAMEBUFFER = 0x8CA8
GL_DRAW_FRAMEBUFFER = 0x8CA9
GL_FRAMEBUFFER_COMPLETE = 0x8CD5
GL_COLOR_ATTACHMENT0 = 0x8CE0
GL_FRAMEBUFFER = 0x8D40

_u, _i, _f, _sz, _p = ctypes.c_uint, ctypes.c_int, ctypes.c_float, ctypes.c_int, ctypes.c_void_p
_uint_p = ctypes.POINTER(ctypes.c_uint)
_int_p = ctypes.POINTER(ctypes.c_int)

#: name: (result type, argument types). OpenGL's own names and C types (GLenum, GLuint and
#: GLbitfield are unsigned int, GLint and GLsizei int, GLfloat float).
SIGNATURES = {
    "glActiveTexture": (None, (_u,)),
    "glAttachShader": (None, (_u, _u)),
    "glBeginQuery": (None, (_u, _u)),
    "glBindFramebuffer": (None, (_u, _u)),
    "glBindTexture": (None, (_u, _u)),
    "glBindVertexArray": (None, (_u,)),
    "glBlitFramebuffer": (None, (_i, _i, _i, _i, _i, _i, _i, _i, _u, _u)),
    "glCheckFramebufferStatus": (_u, (_u,)),
    "glCompileShader": (None, (_u,)),
    "glCreateProgram": (_u, ()),
    "glCreateShader": (_u, (_u,)),
    "glDeleteFramebuffers": (None, (_sz, _uint_p)),
    "glDeleteProgram": (None, (_u,)),
    "glDeleteShader": (None, (_u,)),
    "glDeleteTextures": (None, (_sz, _uint_p)),
    "glDeleteVertexArrays": (None, (_sz, _uint_p)),
    "glDetachShader": (None, (_u, _u)),
    "glDisable": (None, (_u,)),
    "glDrawArrays": (None, (_u, _i, _sz)),
    "glEndQuery": (None, (_u,)),
    "glFinish": (None, ()),
    "glFramebufferTexture2D": (None, (_u, _u, _u, _u, _i)),
    "glGenFramebuffers": (None, (_sz, _uint_p)),
    "glGenQueries": (None, (_sz, _uint_p)),
    "glGenTextures": (None, (_sz, _uint_p)),
    "glGenVertexArrays": (None, (_sz, _uint_p)),
    "glGenerateMipmap": (None, (_u,)),
    "glGetError": (_u, ()),
    "glGetIntegerv": (None, (_u, _int_p)),
    "glGetProgramInfoLog": (None, (_u, _sz, _int_p, ctypes.c_char_p)),
    "glGetProgramiv": (None, (_u, _u, _int_p)),
    "glGetQueryObjectui64v": (None, (_u, _u, ctypes.POINTER(ctypes.c_uint64))),
    "glGetShaderInfoLog": (None, (_u, _sz, _int_p, ctypes.c_char_p)),
    "glGetShaderiv": (None, (_u, _u, _int_p)),
    "glGetString": (ctypes.c_char_p, (_u,)),
    "glGetUniformLocation": (_i, (_u, ctypes.c_char_p)),
    "glIsProgram": (ctypes.c_ubyte, (_u,)),
    "glIsTexture": (ctypes.c_ubyte, (_u,)),
    "glLinkProgram": (None, (_u,)),
    "glPixelStorei": (None, (_u, _i)),
    "glReadPixels": (None, (_i, _i, _sz, _sz, _u, _u, _p)),
    "glShaderSource": (None, (_u, _sz, ctypes.POINTER(ctypes.c_char_p), _int_p)),
    "glTexImage2D": (None, (_u, _i, _i, _sz, _sz, _i, _u, _u, _p)),
    "glTexParameteri": (None, (_u, _u, _i)),
    "glUniform1f": (None, (_i, _f)),
    "glUniform1i": (None, (_i, _i)),
    "glUniform1ui": (None, (_i, _u)),
    "glUniform2f": (None, (_i, _f, _f)),
    "glUniform3f": (None, (_i, _f, _f, _f)),
    "glUniform4f": (None, (_i, _f, _f, _f, _f)),
    "glUniform4fv": (None, (_i, _sz, ctypes.POINTER(_f))),
    "glUseProgram": (None, (_u,)),
    "glViewport": (None, (_i, _i, _sz, _sz)),
}

DEBUG = bool(os.environ.get("SYNCRAIN_GL_DEBUG"))


class GLError(RuntimeError):
    """An OpenGL call left an error behind (only checked with SYNCRAIN_GL_DEBUG=1)."""


_epoxy = None


def _library():
    """libepoxy, which GTK 4 links: already loaded in this process, whatever path it came from."""
    global _epoxy
    if _epoxy is None:
        _epoxy = ctypes.CDLL("libepoxy.so.0")
    return _epoxy


def _function(name):
    restype, argtypes = SIGNATURES[name]
    pointer = ctypes.c_void_p.in_dll(_library(), "epoxy_" + name).value
    fn = ctypes.CFUNCTYPE(restype, *argtypes)(pointer)
    if not DEBUG or name == "glGetError":
        return fn
    get_error = _function("glGetError")

    def checked(*args):
        result = fn(*args)
        error = get_error()
        if error != GL_NO_ERROR:
            raise GLError(f"{name}{args}: OpenGL error {error:#06x}")
        return result
    checked.__name__ = name
    return checked


def __getattr__(name):
    """The first use of `gl.glSomething` makes the ctypes function and keeps it in the module."""
    if name not in SIGNATURES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    fn = _function(name)
    globals()[name] = fn
    return fn


def _fn(name):
    return globals().get(name) or __getattr__(name)


# -- the few calls that hand back values, in the shapes the rest of syncrain uses ---------------

def _gen(fn, n=1):
    ids = (ctypes.c_uint * n)()
    fn(n, ids)
    return ids[0] if n == 1 else list(ids)


def gen_texture() -> int:
    return _gen(_fn("glGenTextures"))


def gen_framebuffer() -> int:
    return _gen(_fn("glGenFramebuffers"))


def gen_vertex_array() -> int:
    return _gen(_fn("glGenVertexArrays"))


def gen_queries(n: int) -> list[int]:
    ids = (ctypes.c_uint * n)()
    _fn("glGenQueries")(n, ids)
    return list(ids)


def _delete(fn, ids):
    ids = [int(i) for i in ids if i]
    if ids:
        fn(len(ids), (ctypes.c_uint * len(ids))(*ids))


def delete_textures(ids) -> None:
    _delete(_fn("glDeleteTextures"), ids)


def delete_framebuffers(ids) -> None:
    _delete(_fn("glDeleteFramebuffers"), ids)


def delete_vertex_arrays(ids) -> None:
    _delete(_fn("glDeleteVertexArrays"), ids)


_scratch = ctypes.c_int(0)


def get_integer(pname: int) -> int:
    """A single-valued glGetIntegerv."""
    _fn("glGetIntegerv")(pname, ctypes.byref(_scratch))
    return _scratch.value


def get_string(name: int) -> str | None:
    value = _fn("glGetString")(name)
    return None if value is None else value.decode(errors="replace")


def shader_source(shader: int, text: str) -> None:
    data = text.encode()
    strings = (ctypes.c_char_p * 1)(data)
    lengths = (ctypes.c_int * 1)(len(data))
    _fn("glShaderSource")(shader, 1, strings, lengths)


def _iv(fn, obj, pname):
    out = ctypes.c_int(0)
    fn(obj, pname, ctypes.byref(out))
    return out.value


def shader_iv(shader: int, pname: int) -> int:
    return _iv(_fn("glGetShaderiv"), shader, pname)


def program_iv(program: int, pname: int) -> int:
    return _iv(_fn("glGetProgramiv"), program, pname)


def _log(get_iv, get_log, obj):
    size = max(1, get_iv(obj, GL_INFO_LOG_LENGTH))
    buf = ctypes.create_string_buffer(size)
    get_log(obj, size, None, buf)
    return buf.value.decode(errors="replace")


def shader_info_log(shader: int) -> str:
    return _log(shader_iv, _fn("glGetShaderInfoLog"), shader)


def program_info_log(program: int) -> str:
    return _log(program_iv, _fn("glGetProgramInfoLog"), program)


def uniform4fv(location: int, values) -> None:
    flat = [float(v) for v in values]
    _fn("glUniform4fv")(location, len(flat) // 4, (ctypes.c_float * len(flat))(*flat))


def read_pixels(x: int, y: int, w: int, h: int) -> bytes:
    """RGBA bytes of a rectangle of the bound framebuffer, rows bottom to top (OpenGL's order)."""
    _fn("glPixelStorei")(GL_PACK_ALIGNMENT, 1)
    buf = ctypes.create_string_buffer(w * h * 4)
    _fn("glReadPixels")(x, y, w, h, GL_RGBA, GL_UNSIGNED_BYTE, buf)
    return buf.raw
