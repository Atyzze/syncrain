"""What syncrain sets in its own environment before GTK and the graphics driver start (syncrain/app.py).

GSK_RENDERER=gl keeps GTK from handing every frame to Vulkan; with it, GDK_DISABLE=dmabuf keeps GTK
4.16 and later from exporting every frame as a dmabuf and importing it back, and from starting a
Vulkan renderer for that. __NV_DISABLE_EXPLICIT_SYNC=1 keeps NVIDIA's Wayland driver from losing
memory on every frame it presents, and __GL_YIELD=USLEEP lets its wait for a frame sleep. GDK reads
GDK_DISABLE once, when GTK initialises, which PyGObject does on `from gi.repository import Gtk`, so
all of it has to be in place before anything imports gi; the native wallpaper inherits it.
"""
from __future__ import annotations

import os
import sys
import types

import pytest

from syncrain import app

NAMES = ("GSK_RENDERER", "GDK_DISABLE", "__NV_DISABLE_EXPLICIT_SYNC", "__GL_YIELD")


@pytest.fixture
def clean(monkeypatch):
    """None of them set, and afterwards exactly what was there before (the app sets them itself,
    so the tests set them with os.environ too and this puts all of it back)."""
    before = {n: os.environ.get(n) for n in NAMES}
    for name in NAMES:
        os.environ.pop(name, None)
    yield monkeypatch
    for name, value in before.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def test_gtk_draws_with_opengl_and_keeps_frames_as_textures(clean):
    app.use_gl_renderer()
    assert os.environ["GSK_RENDERER"] == "gl"
    assert os.environ["GDK_DISABLE"] == "dmabuf"


def test_features_the_user_disabled_stay_disabled_and_nothing_is_added_twice(clean):
    os.environ["GDK_DISABLE"] = "gl-api,vulkan"
    app.use_gl_renderer()
    app.use_gl_renderer()
    assert os.environ["GDK_DISABLE"].split(",") == ["gl-api", "vulkan", "dmabuf"]


def test_a_renderer_the_user_chose_is_kept_and_vulkan_keeps_its_dmabufs(clean):
    """GTK's Vulkan renderer takes a GLArea's frames by dmabuf; without one, through the processor."""
    os.environ["GSK_RENDERER"] = "vulkan"
    app.use_gl_renderer()
    assert os.environ["GSK_RENDERER"] == "vulkan"
    assert "GDK_DISABLE" not in os.environ


def test_nvidia_presents_without_explicit_sync_and_waits_asleep(clean):
    app.avoid_the_explicit_sync_leak()
    assert os.environ["__NV_DISABLE_EXPLICIT_SYNC"] == "1"
    assert os.environ["__GL_YIELD"] == "USLEEP"


def test_values_the_user_set_win(clean):
    os.environ["__NV_DISABLE_EXPLICIT_SYNC"] = "0"
    os.environ["__GL_YIELD"] = "NOTHING"
    app.avoid_the_explicit_sync_leak()
    assert os.environ["__NV_DISABLE_EXPLICIT_SYNC"] == "0"
    assert os.environ["__GL_YIELD"] == "NOTHING"


def test_the_native_wallpaper_inherits_them(clean):
    """The launcher replaces itself with the native program, passing it this environment."""
    from syncrain import native
    app.avoid_the_explicit_sync_leak()
    env = native.environment()
    assert env["__NV_DISABLE_EXPLICIT_SYNC"] == "1" and env["__GL_YIELD"] == "USLEEP"


class GiImported(Exception):
    """Raised by the stand-in gi module at the moment syncrain first imports it."""


def test_everything_is_set_before_gtk_is_imported(clean):
    """main() must set the environment before the first `import gi`: a stand-in gi records the
    environment at that moment and stops the app there."""
    seen = {}

    def require_version(*_):
        seen.update({n: os.environ.get(n) for n in NAMES})
        raise GiImported

    fake = types.ModuleType("gi")
    fake.require_version = require_version
    clean.setitem(sys.modules, "gi", fake)
    clean.setattr(app, "_preload_layer_shell", lambda: None)
    with pytest.raises(GiImported):
        app.main(["--window"])
    assert seen == {"GSK_RENDERER": "gl", "GDK_DISABLE": "dmabuf", "__NV_DISABLE_EXPLICIT_SYNC": "1",
                    "__GL_YIELD": "USLEEP"}
