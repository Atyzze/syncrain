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


@pytest.mark.parametrize("period, per_hour", [(180, 20), (90, 40), (600, 6), (10, 360), (7, 360), (1e-320, 360),
                                              (10_000, 1)])
def test_every_periodic_motion_runs_whole_cycles_per_hour(period, per_hour):
    """So the motion has no seam where the hour counter restarts; none is shorter than 10 s."""
    assert engine.cycles_per_hour(period) == per_hour


@pytest.mark.parametrize("period", [0, -5, None])
def test_a_period_of_zero_or_less_switches_the_motion_off(period):
    assert engine.cycles_per_hour(period) == 0.0


def test_the_rainbow_modes_are_the_colour_cycles_they_were():
    meta = engine.load_meta()
    off, logo, everything = (engine.motion(engine.compose(meta, "nixos", rainbow=m)) for m in ("off", "logo", "all"))
    assert off["uLogoHueCph"] == 0 and off["uRainHueCph"] == 0
    assert logo["uLogoHueCph"] > 0 and logo["uRainHueCph"] == 0
    assert everything["uLogoHueCph"] > 0 and everything["uRainHueCph"] == engine.cycles_per_hour(600)
    assert off["uSpinCph"] > 0, "the logo keeps turning with the colours off"
    still = engine.motion(engine.compose(meta, "nixos"), spin=0, drift=0)
    assert still["uSpinCph"] == 0 and still["uDrift"] == 0
    assert engine.motion(engine.compose(meta, "nixos", rainbow="all", cycle=0))["uRainHueCph"] == 0, "the new option wins"


def test_a_preset_with_the_settings_over_it():
    meta = engine.load_meta()
    th = engine.compose(meta, "matrix", rain_colors=["#000000", "#ff0000", [0.5, 0.25, 1], "#ffffff"],
                        glow_color="#102030", background_colors=["#010203", "#040506", "#070809"], vignette=0.1,
                        logo_size=0.2, logo_cycle=0, cycle=30, flavours=8, flavour_layout="wave", words=["HI"])
    assert th["colors"]["mid"] == [1.0, 0.0, 0.0] and th["colors"]["pale"] == [0.5, 0.25, 1.0]
    assert th["colors"]["glow"] == [round(16 / 255, 4), round(32 / 255, 4), round(48 / 255, 4)]
    assert th["background"]["vignette"] == 0.1 and th["logo"]["size"] == 0.2 and th["wordText"] == ["HI"]
    assert (th["rain"]["cycle"], th["rain"]["flavours"], th["rain"]["flavourLayout"]) == (30, 8, "wave")
    assert meta["themes"]["matrix"]["colors"]["mid"] == [0.12, 1.0, 0.36], "the preset itself stays"
    nixos = meta["themes"]["nixos"]["colors"]
    assert engine.compose(meta, "nixos", rain_colors=["#132a52", "#3d6ed2", "#8cc0ee", "#eef7ff"])["colors"] == nixos, \
        "the preset's own colours, as the page writes them, are the preset's to the last digit"
    for wrong in ("#12345", "blue", [1, 2, 3], [0.1, 0.2]):
        with pytest.raises(ValueError):
            engine.colour(wrong)


def test_the_themes_file_is_read_by_its_contract(tmp_path):
    meta = engine.load_meta()
    assert set(meta["themes"]) == {"syncrain", "nixos", "matrix"} and engine.default_preset(meta) == "syncrain"
    meta["contract"] = "syncrain-themes-1"
    (tmp_path / "themes.json").write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(RuntimeError, match="syncrain-themes-3"):
        engine.load_meta(str(tmp_path))


def test_the_picture_options_are_multiples_of_the_theme_s_own_values():
    theme = engine.load_meta()["themes"]["nixos"]
    assert engine.look(theme) == {"speed": 1.0, "density": 1.0, "glow": 1.0, "bloom": 1.0, "hieroglyphs": None,
                                  "snow": True}
    assert engine.look(theme, speed=9, density=-1, glow=0, bloom=3, hieroglyphs=2, snow="off") == {
        "speed": 4.0, "density": 0.0, "glow": 0.0, "bloom": 2.0, "hieroglyphs": 1.0, "snow": False}


def test_a_preset_says_where_its_sliders_start():
    """An option not given is the preset's "look" (1 where it says nothing); one given replaces it."""
    theme = engine.load_meta()["themes"]["syncrain"]
    assert theme["look"] == {"speed": 1.0, "density": 1.15, "glow": 1.0, "bloom": 1.0, "bg_gain": 0.6}
    assert engine.look(theme) == {"speed": 1.0, "density": 1.15, "glow": 1.0, "bloom": 1.0, "hieroglyphs": None,
                                  "snow": True}
    assert engine.look(theme, density=1.0, glow=2.0)["density"] == 1.0
    assert engine.look(theme, density=1.0, glow=2.0)["glow"] == 2.0


def uniforms(**look):
    from syncrain.renderer import Renderer, static_uniforms
    return {(p, n): v for p, n, _, v in static_uniforms(Renderer(theme="nixos", glyphs="theme", **look))}


def test_the_defaults_draw_the_theme_as_it_was():
    """Every option at its default sets the uniforms build 11 set."""
    theme = engine.load_meta()["themes"]["nixos"]
    u = uniforms()
    assert u[("state", "uDensity")] == (theme["rain"]["density"],) and u[("state", "uSpeed")] == (1.0,)
    assert u[("composite", "uBloomK")] == (theme["rain"]["bloom"],)
    assert u[("composite", "uLogoGlowK")] == (theme["logo"]["glowStrength"],)
    assert u[("composite", "uCentreGlow")] == (1.0,) and u[("composite", "uBgGain")] == (1.0,)
    assert u[("composite", "uSnowN")] == (len(theme["snow"]),)


def test_each_option_reaches_its_uniform():
    theme = engine.load_meta()["themes"]["nixos"]
    u = uniforms(speed=0.5, density=2.0, glow=0.0, bloom=0.5, bg_gain=0.4, snow="off")
    assert u[("state", "uSpeed")] == (0.5,)
    assert u[("state", "uDensity")] == (theme["rain"]["density"] * 2.0,)
    assert u[("composite", "uCentreGlow")] == (0.0,) and u[("composite", "uLogoGlowK")] == (0.0,)
    assert u[("composite", "uBloomK")] == (theme["rain"]["bloom"] * 0.5,)
    assert u[("composite", "uBgGain")] == (0.4,) and u[("composite", "uSnowN")] == (0,)
