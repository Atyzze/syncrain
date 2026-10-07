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
