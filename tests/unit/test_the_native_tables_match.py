"""The native wallpaper's C keeps tables of its own that must say what Python says: which texture
unit each sampler reads (the samplers' uniforms come from Python's renderer.UNIT through the scene,
the binding from passes.c), and the order of the textures in the scene."""
from __future__ import annotations

import re

from syncrain import renderer
from tests.conftest import ROOT

NATIVE = ROOT / "syncrain" / "native"


def test_each_texture_unit_is_the_one_python_names():
    passes = (NATIVE / "passes.c").read_text(encoding="utf-8")
    units = {name.lower(): int(n) for name, n in re.findall(r"UNIT_([A-Z]+) = (\d+)", passes)}
    assert units == renderer.UNIT
    static = re.search(r"STATIC_UNIT\[TEXTURE_COUNT\] = \{([^}]*)\}", passes).group(1)
    assert [u.strip().removeprefix("UNIT_").lower() for u in static.split(",")] == list(renderer.STATIC_TEXTURES)


def test_the_scene_s_textures_are_in_python_s_order():
    scene = (NATIVE / "scene.c").read_text(encoding="utf-8")
    names = re.search(r"TEXTURES\[TEXTURE_COUNT\] = \{([^}]*)\}", scene).group(1)
    assert [n.strip().strip('"') for n in names.split(",")] == list(renderer.STATIC_TEXTURES)
    header = (NATIVE / "syncrain.h").read_text(encoding="utf-8")
    enum = re.search(r"enum texture \{([^}]*)\}", header).group(1)
    assert [e.strip().removeprefix("TEXTURE_").lower() for e in enum.split(",")][:-1] == list(renderer.STATIC_TEXTURES)
