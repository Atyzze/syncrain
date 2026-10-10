"""What the host hands the shaders: the channel seed, the split clock, the periodic motion.

Every machine on a channel must compute these identically (the web runner does the same in
JavaScript; the browser lane checks the two agree on a whole frame), so they are pinned to
known answers here rather than to whatever the code happens to return today.
"""
from __future__ import annotations

import json

import pytest

from syncrain import engine


def test_a_channel_name_is_its_32_bit_fnv1a_hash():
    assert engine.channel_seed("") == 0x811C9DC5            # the FNV offset basis
    assert engine.channel_seed("a") == 0xE40C292C           # published FNV-1a test vectors
    assert engine.channel_seed("foobar") == 0xBF9CF968


def test_a_channel_name_is_hashed_as_utf8():
    by_hand = 0x811C9DC5
    for byte in "ä".encode("utf-8"):
        by_hand = ((by_hand ^ byte) * 0x01000193) & 0xFFFFFFFF
    assert engine.channel_seed("ä") == by_hand


def test_time_is_whole_seconds_since_2024_and_a_millisecond_fraction():
    epoch0 = engine.load_meta()["epoch0"]
    assert epoch0 == 1704067200                            # 2024-01-01T00:00:00Z
    assert engine.split_time(epoch0 + 1.25, epoch0) == (1, 0.25)
    sec, frac = engine.split_time(4102444800.123, epoch0)  # 2100: still a millisecond grid
    assert sec == 4102444800 - epoch0 and frac == pytest.approx(0.123, abs=1e-9)


def test_the_seconds_wrap_as_an_unsigned_32_bit_counter():
    epoch0 = engine.load_meta()["epoch0"]
    assert engine.split_time(epoch0 - 1, epoch0)[0] == 0xFFFFFFFF


@pytest.mark.parametrize("period, per_hour", [(180, 20), (90, 40), (600, 6), (7, 514), (10_000, 1)])
def test_every_periodic_motion_runs_whole_cycles_per_hour(period, per_hour):
    """So the motion has no seam where the hour counter restarts."""
    assert engine.cycles_per_hour(period) == per_hour


@pytest.mark.parametrize("period", [0, -5, None])
def test_a_period_of_zero_or_less_switches_the_motion_off(period):
    assert engine.cycles_per_hour(period) == 0.0


def test_the_rainbow_modes():
    theme = engine.load_meta()["themes"]["nixos"]
    off, logo, everything = (engine.motion(theme, rainbow=m) for m in ("off", "logo", "all"))
    assert off["uLogoHueCph"] == 0 and off["uRainHueCph"] == 0
    assert logo["uLogoHueCph"] > 0 and logo["uRainHueCph"] == 0
    assert everything["uLogoHueCph"] > 0 and everything["uRainHueCph"] > 0
    assert off["uSpinCph"] > 0, "the logo keeps turning with the colours off"
    still = engine.motion(theme, spin=0, drift=0)
    assert still["uSpinCph"] == 0 and still["uDrift"] == 0


def test_the_themes_file_is_read_by_its_contract(tmp_path):
    meta = engine.load_meta()
    assert set(meta["themes"]) == {"nixos", "matrix"}
    meta["contract"] = "syncrain-themes-0"
    (tmp_path / "themes.json").write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(RuntimeError, match="syncrain-themes-1"):
        engine.load_meta(str(tmp_path))


def test_the_lookup_tables_have_the_shapes_the_shaders_read():
    theme = engine.load_meta()["themes"]["matrix"]
    assert len(engine.lut_bytes(theme)) == 256 * 4
    data, rows = engine.words_bytes(theme)
    assert rows == len(theme["words"]) and len(data) == 16 * rows * 4


def test_the_picture_options_are_multiples_of_the_theme_s_own_values():
    theme = engine.load_meta()["themes"]["nixos"]
    assert engine.look(theme) == {"speed": 1.0, "density": 1.0, "glow": 1.0, "bloom": 1.0, "hieroglyphs": 0.15,
                                  "snow": True}
    assert engine.look(theme, speed=9, density=-1, glow=0, bloom=3, hieroglyphs=2, snow="off") == {
        "speed": 4.0, "density": 0.0, "glow": 0.0, "bloom": 2.0, "hieroglyphs": 1.0, "snow": False}


def uniforms(**look):
    from syncrain.renderer import Renderer, static_uniforms
    return {(p, n): v for p, n, _, v in static_uniforms(Renderer(theme="nixos", **look))}


def test_the_defaults_draw_the_theme_as_it_was():
    """Every option at its default sets the uniforms build 11 set (and the hieroglyphs a share)."""
    theme = engine.load_meta()["themes"]["nixos"]
    u = uniforms()
    assert u[("state", "uDensity")] == (theme["rain"]["density"],) and u[("state", "uSpeed")] == (1.0,)
    assert u[("composite", "uBloomK")] == (theme["rain"]["bloom"],)
    assert u[("composite", "uLogoGlowK")] == (theme["logo"]["glowStrength"],)
    assert u[("composite", "uCentreGlow")] == (1.0,) and u[("composite", "uBgGain")] == (1.0,)
    assert u[("composite", "uSnowN")] == (len(theme["snow"]),)
    assert u[("state", "uHiero")] == (0.15,)


def test_each_option_reaches_its_uniform():
    theme = engine.load_meta()["themes"]["nixos"]
    u = uniforms(speed=0.5, density=2.0, glow=0.0, bloom=0.5, bg_gain=0.4, snow="off", hieroglyphs=1.0)
    assert u[("state", "uSpeed")] == (0.5,)
    assert u[("state", "uDensity")] == (theme["rain"]["density"] * 2.0,)
    assert u[("composite", "uCentreGlow")] == (0.0,) and u[("composite", "uLogoGlowK")] == (0.0,)
    assert u[("composite", "uBloomK")] == (theme["rain"]["bloom"] * 0.5,)
    assert u[("composite", "uBgGain")] == (0.4,) and u[("composite", "uSnowN")] == (0,)
    assert u[("state", "uHiero")] == (1.0,)


def test_the_hieroglyphs_follow_every_older_glyph_in_the_atlas():
    """They were added after the others, so no older glyph moved; the shader draws them from there."""
    meta = engine.load_meta()
    first, count = meta["atlas"]["hieroglyphs"]
    assert first == 125 and count >= 64 and first + count == meta["atlas"]["glyphs"] <= 256
    assert all(0x13000 <= ord(g) <= 0x1342F for g in meta["glyphs"][first:first + count])
    u = uniforms()
    assert u[("state", "uHieroFirst")] == (first,) and u[("state", "uHieroCount")] == (count,)
