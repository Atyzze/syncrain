"""The web page in Chromium (software WebGL2): the same stream as the app, and a page that fits.

Needs node with Playwright and its Chromium (`docs/agent/ENVIRONMENT.md`). The page and the app
are separate implementations of the host side (JavaScript and Python) over the same shaders, so
the frame they draw at one moment is the test that they agree.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

from syncrain import build
from tests.conftest import need
from tests.support import MOMENT, mean_abs_diff


@pytest.fixture(scope="module")
def page(root):
    node = shutil.which("node")
    need(node is not None, "no node for the browser lane")
    env = dict(os.environ)
    if "NODE_PATH" not in env and shutil.which("npm"):
        env["NODE_PATH"] = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    probe = subprocess.run([node, "-e", "require('playwright')"], env=env, capture_output=True, text=True)
    need(probe.returncode == 0, "Playwright is not installed for node (npm i -g playwright)")

    def run(*args):
        done = subprocess.run([node, str(root / "tests/browser/page.js"), *map(str, args)], env=env,
                              capture_output=True, text=True, timeout=300)
        assert done.returncode == 0, done.stderr[-2000:]
        result = json.loads(done.stdout.strip().splitlines()[-1])
        assert not result.pop("errors"), "the page logged errors"
        return result
    return run


#: Every picture option, as the page's URL says it and as the command line does.
LOOK = {"speed": "0.5", "density": "1.7", "glow": "0.3", "bloom": "0.5", "bg-gain": "0.6", "snow": "off",
        "hieroglyphs": "0.6"}


@pytest.mark.parametrize("look", [{}, LOOK], ids=["defaults", "every-option"])
def test_the_page_and_the_app_draw_the_same_frame(page, app, tmp_path, look):
    web, native = tmp_path / "web.png", tmp_path / "native.png"
    page("shot", web, 1280, 720, f"t={MOMENT}&hud=0" + "".join(f"&{k}={v}" for k, v in look.items()))
    options = [x for k, v in look.items() for x in ("--" + k, v)]
    done = app(["--window", "--size", "1280x720", "--time", str(MOMENT), "--screenshot", str(native), *options])
    assert done.returncode == 0, done.stderr
    assert mean_abs_diff(web, native) < 1.0


def test_a_narrow_wallpaper_page_draws_what_a_narrow_desktop_does(page, app, tmp_path):
    """Under 768 px a cell stops shrinking at 12 px on both, so both show the middle of the stream."""
    web, native = tmp_path / "web.png", tmp_path / "native.png"
    page("shot", web, 640, 360, f"t={MOMENT}&hud=0")
    done = app(["--window", "--size", "640x360", "--time", str(MOMENT), "--screenshot", str(native)])
    assert done.returncode == 0, done.stderr
    assert mean_abs_diff(web, native) < 1.0


def test_screens_of_one_shape_share_one_stream(page):
    small = page("state", 1280, 720, f"t={MOMENT}&hud=0")
    large = page("state", 1920, 1080, f"t={MOMENT}&hud=0")
    assert small == large


def test_another_channel_is_another_stream(page):
    public = page("state", 1280, 720, f"t={MOMENT}&hud=0&channel=public")
    friends = page("state", 1280, 720, f"t={MOMENT}&hud=0&channel=friends")
    assert public["rows"] == friends["rows"] and public["hash"] != friends["hash"]


def test_the_page_says_which_build_and_stream_it_is(page):
    said = page("identity")
    assert said == {"build": build.BUILD_NUMBER, "stream": build.stream_id(),
                    "ident": f"Build {build.BUILD_NUMBER} · stream {build.stream_id()}"}


def test_the_controls_fit_a_desk_and_a_phone(page):
    for size, seen in page("controls").items():
        assert seen == {"overflow": False, "shown": True}, size


def test_the_page_turns_the_logo_as_the_desktop_does(page):
    """Cycles per hour for every period from 0.5 s to 2 h in halves: a half is rounded to the even
    neighbour in both, so a logo never turns once more an hour on one of them."""
    from syncrain.engine import cycles_per_hour
    assert page("cph")["cph"] == [cycles_per_hour((i + 1) / 2) for i in range(14400)]


def test_a_theme_that_is_no_theme_gives_the_default_one(page):
    """Names every object has (constructor, toString) are not themes; the page draws NixOS snow."""
    nixos = page("state", 1280, 720, f"t={MOMENT}&hud=0&theme=nixos")
    for name in ("constructor", "toString", "__proto__"):
        assert page("state", 1280, 720, f"t={MOMENT}&hud=0&theme={name}") == nixos, name


#: A settings file with every setting moved, and symbol sets of the shipped glyphs only (others are
#: drawn by each side's own fonts, which are not the same pixels).
SETTINGS = {
    "contract": "syncrain-config-1", "theme": "matrix", "channel": "friends", "rainbow": "all", "logo": "colours",
    "spin": 60, "drift": 0.05, "speed": 1.3, "density": 1.2, "glow": 0.7, "bloom": 1.4, "bg_gain": 0.8,
    "snow": False, "hieroglyphs": 0.3, "fps": 30, "pause_under": "never",
    "glyphs": {"balance": "glyphs", "sets": [
        {"name": "katakana", "chars": "アイウエオカキクケコ", "weight": 2, "mirror": True},
        {"name": "greek", "chars": "ΓΔΘΛΞΠΣΦΨΩ", "share": 0.2},
        {"name": "digits", "chars": "0123456789 ", "weight": 1},
        {"name": "hieroglyphs", "chars": "\U00013000\U00013001\U0001302D\U00013050", "weight": 1},
        {"name": "cyrillic", "chars": "АБВГД", "weight": 0}]},
}


def test_a_settings_file_draws_the_same_frame_on_the_page_and_the_desktop(page, app, tmp_path):
    """What the settings panel shows is what the desktop draws from the file it saves."""
    settings, web, native = tmp_path / "config.json", tmp_path / "web.png", tmp_path / "native.png"
    settings.write_text(json.dumps(SETTINGS, ensure_ascii=False), encoding="utf-8")
    said = page("configshot", web, 1280, 720, f"t={MOMENT}&hud=0", settings)
    assert said["loaded"] == ""
    done = app(["--window", "--size", "1280x720", "--time", str(MOMENT), "--screenshot", str(native),
                "--config", str(settings)])
    assert done.returncode == 0, done.stderr
    assert mean_abs_diff(web, native) < 1.0


def test_what_the_settings_panel_saves_the_desktop_takes(page, tmp_path):
    """Used as a person would at a desk and on a phone: the panel fits, and the file it saves
    holds what was chosen and is one the desktop reads."""
    from syncrain.app import parse_args
    for size, seen in page("studio").items():
        saved = seen.pop("saved")
        assert seen == {"overflow": False, "shown": True, "inside": True, "apart": True, "filename": "config.json",
                        "symbols": {"slots": seen["symbols"]["slots"], "drawn": [], "missing": [], "error": ""}}, size
        path = tmp_path / f"{size}.json"
        path.write_text(saved, encoding="utf-8")
        args = parse_args(["--config", str(path)])
        assert (args.theme, args.channel, args.speed) == ("matrix", "friends", 1.5), size
        assert [s["name"] for s in args.glyphs["sets"]] == ["katakana", "digits", "symbols", "hieroglyphs", "greek"]


def test_symbols_the_shipped_atlas_does_not_have_are_drawn_by_the_browser(page, tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"contract": "syncrain-config-1", "glyphs": {"sets": [
        {"name": "stars", "chars": "★☆♥"}, {"name": "mirrored", "chars": "AB", "mirror": True},
        {"name": "digits", "chars": "0123"}]}}, ensure_ascii=False), encoding="utf-8")
    said = page("symbols", path)
    assert said["loaded"] == "" and said["symbols"]["error"] == ""
    assert sorted(said["symbols"]["drawn"] + said["symbols"]["missing"]) == sorted("★☆♥AB")


@pytest.mark.parametrize("wrong, says", [
    ({"speed": "fast"}, "speed is a number"),
    ({"density": -1}, "density is 0 or more"),
    ({"theme": "nope"}, "theme is"),
    ({"colour": "red"}, "no setting"),
    ({"glyphs": {"sets": [{"name": "a", "chars": "ab", "share": 0.7}, {"name": "b", "chars": "cd", "share": 0.6}]}},
     "the shares add up to more than 1"),
    ({"glyphs": {"sets": [{"name": "a", "chars": " \x1c "}]}}, 'a needs "chars"'),
])
def test_the_page_refuses_what_the_desktop_refuses(page, tmp_path, wrong, says):
    from syncrain.app import parse_args
    path = tmp_path / "config.json"
    path.write_text(json.dumps(dict({"contract": "syncrain-config-1"}, **wrong)), encoding="utf-8")
    assert says in page("symbols", path)["loaded"]
    with pytest.raises(SystemExit) as stopped:
        parse_args(["--config", str(path)])
    assert stopped.value.code == 2


def test_a_settings_file_with_only_sets_leaves_nothing_of_the_last_one(page, tmp_path):
    """The desktop reads a missing setting as the default, so the page does too; a symbols file
    (with or without its contract) changes the sets only."""
    first, sets, symbols = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "glyphs.json"
    first.write_text(json.dumps({"contract": "syncrain-config-1", "speed": 2, "theme": "matrix"}))
    sets.write_text(json.dumps({"contract": "syncrain-config-1", "glyphs": {"sets": [{"name": "d", "chars": "0123"}]}}))
    symbols.write_text(json.dumps({"sets": [{"name": "e", "chars": "4567"}]}))
    said = page("symbols", first, sets)
    assert said["loaded"] == "" and (said["exported"]["speed"], said["exported"]["theme"]) == (1, "nixos")
    said = page("symbols", first, symbols)
    assert said["loaded"] == "" and said["exported"]["speed"] == 2
    assert [s["name"] for s in said["exported"]["glyphs"]["sets"]] == ["e"]
