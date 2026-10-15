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
LOOK = {"speed": "0.5", "density": "1.7", "glow": "0.3", "bloom": "0.25", "bg-gain": "0.6", "snow": "off",
        "hieroglyphs": "0.6"}
#: The bloom is blurred in 8-bit textures, whose last bit Chromium's rasterizer and Mesa's round
#: differently, and the bloom's gain multiplies that: with it off the two are 0.03 apart, at the
#: syncrain preset's gain of 5 1.24, all of it spread evenly. So the frames are compared at a gain of
#: 1.25 (the option's 0.25, as matrix draws), and every other pass with the bloom off, to 0.15.
EVEN_BLOOM = {"bloom": "0.25"}


@pytest.mark.parametrize("look", [EVEN_BLOOM, LOOK], ids=["defaults", "every-option"])
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
    page("shot", web, 640, 360, f"t={MOMENT}&hud=0&bloom={EVEN_BLOOM['bloom']}")
    done = app(["--window", "--size", "640x360", "--time", str(MOMENT), "--screenshot", str(native),
                "--bloom", EVEN_BLOOM["bloom"]])
    assert done.returncode == 0, done.stderr
    assert mean_abs_diff(web, native) < 1.0


@pytest.mark.parametrize("look", [{}, LOOK, dict(LOOK, preset="nixos")],
                         ids=["defaults", "every-option", "every-option-nixos"])
def test_with_the_bloom_off_the_page_and_the_app_agree_closely(page, app, tmp_path, look):
    """Every pass but the bloom: the preset's colours, wave, logo and background as they are; under
    nixos, whose background and logo glow the syncrain preset lacks, the glow and bg-gain too."""
    look = dict(look, bloom="0")
    web, native = tmp_path / "web.png", tmp_path / "native.png"
    page("shot", web, 1280, 720, f"t={MOMENT}&hud=0" + "".join(f"&{k}={v}" for k, v in look.items()))
    options = [x for k, v in look.items() for x in ("--" + k, v)]
    done = app(["--window", "--size", "1280x720", "--time", str(MOMENT), "--screenshot", str(native), *options])
    assert done.returncode == 0, done.stderr
    assert mean_abs_diff(web, native) < 0.15


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
    """Names every object has (constructor, toString) are not presets; the page draws the default one."""
    default = page("state", 1280, 720, f"t={MOMENT}&hud=0&preset=syncrain")
    for name in ("constructor", "toString", "__proto__"):
        assert page("state", 1280, 720, f"t={MOMENT}&hud=0&theme={name}") == default, name


#: A settings file with every setting moved, and symbol sets of the shipped glyphs only (others are
#: drawn by each side's own fonts, which are not the same pixels).
SETTINGS = {
    "contract": "syncrain-config-1", "theme": "matrix", "channel": "friends", "rainbow": "all", "logo": "nixos",
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
    ({"theme": "nope"}, "no preset"),
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
    assert said["loaded"] == "" and (said["exported"]["speed"], said["exported"]["preset"]) == (1, "syncrain")
    said = page("symbols", first, symbols)
    assert said["loaded"] == "" and said["exported"]["speed"] == 2
    assert [s["name"] for s in said["exported"]["glyphs"]["sets"]] == ["e"]


def a_logo_png(path):
    """A small picture with a see-through background, made into the logo texture as the page does."""
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (300, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((20, 20, 180, 180), fill=(230, 60, 40, 255))
    d.rectangle((150, 60, 280, 140), fill=(40, 120, 230, 255))
    im.save(path)
    return path


def test_the_new_look_settings_draw_the_same_frame_on_the_page_and_the_desktop(page, app, tmp_path):
    """Colours of one's own, seven flavours by the channel cycling every 45 s, another background,
    a picture as the logo (as the desktop gets it from the page: the texture itself), hidden words."""
    import base64
    from syncrain import logo
    from PIL import Image
    texture = tmp_path / "logo.png"
    logo.prepare(Image.open(a_logo_png(tmp_path / "picture.png"))).save(texture)
    settings = {"contract": "syncrain-config-1", "preset": "matrix", "channel": "flavours",
                "rain_colors": ["#202040", "#8040c0", [0.9, 0.7, 1.0], "#ffffff"], "glow_color": "#6030a0",
                "background_colors": ["#050008", "#0a0010", "#200838"], "vignette": 0.3, "cycle": 45, "flavours": 7,
                "flavour_layout": "random", "logo": "data:image/png;base64," + base64.b64encode(texture.read_bytes()).decode(),
                "logo_size": 0.3, "logo_cycle": 0, "logo_color": "#ffaa33", "snow": True, "words": ["HELLO", "SYNC"]}
    path, web, native = tmp_path / "config.json", tmp_path / "web.png", tmp_path / "native.png"
    for layout in ("random", "wave"):
        path.write_text(json.dumps(dict(settings, flavour_layout=layout)), encoding="utf-8")
        said = page("configshot", web, 1280, 720, f"t={MOMENT}&hud=0", path)
        assert said["loaded"] == "", said
        done = app(["--window", "--size", "1280x720", "--time", str(MOMENT), "--screenshot", str(native),
                    "--config", str(path)])
        assert done.returncode == 0, done.stderr
        assert mean_abs_diff(web, native) < 1.0, layout


def test_one_flavour_and_no_cycle_is_the_picture_as_it_was(page, tmp_path):
    """The default stays: flavours 1 draws what a page without flavours drew."""
    plain, one = tmp_path / "plain.png", tmp_path / "one.png"
    page("shot", plain, 640, 360, f"t={MOMENT}&hud=0&preset=nixos")
    page("shot", one, 640, 360, f"t={MOMENT}&hud=0&preset=nixos&flavours=1&cycle=0")
    assert mean_abs_diff(plain, one) == 0
    many = tmp_path / "many.png"
    page("shot", many, 640, 360, f"t={MOMENT}&hud=0&preset=nixos&flavours=12")
    assert mean_abs_diff(plain, many) > 1.0, "twelve flavours are another picture"


def test_a_picture_picked_as_the_logo_goes_into_the_settings_file(page, tmp_path):
    import base64
    import io
    from PIL import Image
    from syncrain.app import parse_args
    said = page("logo", a_logo_png(tmp_path / "picture.png"))["exported"]
    uri = said["logo"]
    assert uri.startswith("data:image/png;base64,") and said["logo_cycle"] == 0, "a picture keeps its colours"
    im = Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1])))
    assert im.size == (1024, 1024) and im.mode == "RGBA"
    box = im.getchannel("A").getbbox()
    middle = (1024 - round(1024 * 2 / 3)) // 2
    assert middle <= box[0] and box[2] <= 1024 - middle and box[2] - box[0] > 0.8 * round(1024 * 2 / 3), \
        "the picture fills the middle two thirds across"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(said), encoding="utf-8")
    assert parse_args(["--config", str(path)]).logo == uri


@pytest.mark.parametrize("given, then", [
    ({"theme": "matrix", "snow": True, "rainbow": "off"}, {"preset": "matrix", "snow": False, "logo_cycle": 0}),
    ({"theme": "matrix", "preset": None}, {"preset": "matrix"}),
    ({"preset": "nixos", "rainbow": "off", "logo_cycle": None}, {"logo_cycle": 0}),
    ({"logo_cycle": 30, "rainbow": "off"}, {"logo_cycle": 0}),
    ({"words": [" HI", "THERE "]}, {"words": ["HI", "THERE"]}),
], ids=["build-21-matrix", "a-null-is-no-value", "rainbow-off", "rainbow-where-it-stands", "words-as-the-desktop-reads"])
def test_the_page_reads_a_file_as_the_desktop_does(page, tmp_path, given, then):
    from syncrain import engine
    from syncrain.app import parse_args
    from syncrain.renderer import from_args
    path = tmp_path / "config.json"
    path.write_text(json.dumps(dict({"contract": "syncrain-config-1"}, **given)), encoding="utf-8")
    said = page("symbols", path)
    assert said["loaded"] == "" and {k: said["exported"][k] for k in then} == then
    r = from_args(parse_args(["--config", str(path)]), glyphs="theme")
    desktop = {"preset": r.theme_name, "snow": r.look["snow"], "logo_cycle": r.th["logo"]["hueCycle"],
               "words": r.th["wordText"]}
    assert {k: desktop[k] for k in then} == then
