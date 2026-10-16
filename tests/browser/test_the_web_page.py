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


def test_a_screen_whose_quarter_is_no_whole_number_draws_as_the_desktop_does(page, app, tmp_path):
    """1050 rows: a quarter is 262.5, which Python rounds to 262 and Math.round to 263; the blur
    passes then had other sizes on the page than on the desktop."""
    web, native = tmp_path / "web.png", tmp_path / "native.png"
    page("shot", web, 1680, 1050, f"t={MOMENT}&hud=0&bloom=0.25")
    done = app(["--window", "--size", "1680x1050", "--time", str(MOMENT), "--screenshot", str(native), "--bloom", "0.25"])
    assert done.returncode == 0, done.stderr
    assert mean_abs_diff(web, native) < 1.0


def test_a_moment_between_milliseconds_is_drawn_as_its_millisecond(page):
    """A video at 30 fps has frames between milliseconds; the desktop draws each at the millisecond it
    falls in (engine.split_time), and the page did not: one in six frames had other heads."""
    t0 = int(MOMENT) * 1000
    frames = [t0 + k * 1000 / 30 for k in range(90)]
    drawn = page("states", 640, 360, json.dumps(frames))["hashes"]
    floored = page("states", 640, 360, json.dumps([t0 + (k * 1000) // 30 for k in range(90)]))["hashes"]
    assert drawn == floored
    assert len(set(floored)) > 30, "the rain moves from frame to frame"


def test_saved_settings_load_back_as_they_were(page, tmp_path):
    """What the settings panel saves, loaded again: the same file, word for word."""
    seen = page("studio")
    for name in ("desk", "phone"):
        saved = tmp_path / f"{name}.json"
        saved.write_text(seen[name]["saved"], encoding="utf-8")
        again = page("symbols", saved)
        assert again["loaded"] == "", again["loaded"]
        assert json.loads(again["exported"] if isinstance(again["exported"], str) else json.dumps(again["exported"])) \
            == json.loads(seen[name]["saved"]), name


def test_a_wallpaper_page_at_a_low_scale_draws_the_same_grid(page):
    """scale= in the address, as --scale: fewer pixels, the same rows (the desktop's engine.geometry)."""
    from syncrain import engine
    cols = engine.load_meta()["cols"]
    one = page("state", 800, 450, f"t={MOMENT}&hud=0&scale=1")
    low = page("state", 800, 450, f"t={MOMENT}&hud=0&scale=0.3")
    assert (one["cols"], low["cols"]) == (cols, cols)
    assert low["rows"] == engine.geometry(240, 135, cols, 0.3)["rows"] == one["rows"]


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
    "snow": False, "hieroglyphs": 0.3, "fps": 30, "pause_under": "never", "words": ["WAKE UP NEO", "AI"],
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


def test_one_flavour_and_no_cycle_draws_as_the_desktop_does(page, app, tmp_path):
    """Over the syncrain preset (64 flavours in a wave, turning every 440 s), flavours 1 and cycle 0
    are a picture of their own: the page draws it as the desktop does with the same two options.
    (Over nixos, whose own values they are, the two pages could not differ.)"""
    one, native, preset = tmp_path / "one.png", tmp_path / "native.png", tmp_path / "preset.png"
    # the bloom at 0.25, as the frames above are compared (EVEN_BLOOM: the preset's gain multiplies
    # the last bit the two rasterizers round apart)
    page("shot", one, 640, 360, f"t={MOMENT}&hud=0&preset=syncrain&flavours=1&cycle=0&bloom=0.25")
    done = app(["--window", "--size", "640x360", "--time", str(MOMENT), "--screenshot", str(native),
                "--config", "none", "--preset", "syncrain", "--flavours", "1", "--cycle", "0", "--bloom", "0.25"])
    assert done.returncode == 0, done.stderr
    assert mean_abs_diff(one, native) < 1.0
    page("shot", preset, 640, 360, f"t={MOMENT}&hud=0&preset=syncrain&bloom=0.25")
    assert mean_abs_diff(one, preset) > 1.0, "one flavour is another picture than 64"


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


def _rgb(css: str) -> tuple[float, ...]:
    return tuple(float(v) / 255 for v in css[css.index("(") + 1:css.index(")")].split(",")[:3])


def _luminance(css: str) -> float:
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in _rgb(css)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def test_every_list_opens_readable(page):
    """An open list's options were light text on the browser's white (the operator's screenshot of
    build 28): each option, chosen or not, is now its text on the page's own colours, readable (a
    contrast of 4.5, the WCAG's for ordinary text)."""
    lists = page("dropdowns")["lists"]
    assert len(lists) >= 4 and all(lst["options"] for lst in lists)
    for lst in lists:
        for o in lst["options"]:
            if o["disabled"]:
                continue
            fg, bg = _luminance(o["color"]), _luminance(o["background"])
            contrast = (max(fg, bg) + 0.05) / (min(fg, bg) + 0.05)
            assert contrast >= 4.5, (lst["id"], o)
            if not o["chosen"]:
                assert bg < 0.05, (lst["id"], o)          # the page's dark sheet, not the browser's white


def test_the_page_makes_a_video_the_desktop_would(page, app, tmp_path, root):
    """The Video section's WebM, decoded: its frames are the moments the app draws, and a looping
    video's first frame is the moment just after its last, so a player repeating it shows no seam."""
    ffmpeg = shutil.which("ffmpeg")
    need(ffmpeg is not None, "no ffmpeg to decode the page's video")
    t0, seconds, fps, w, h = int(MOMENT), 3, 10, 640, 360
    webm = tmp_path / "page.webm"
    page("video", webm, w, h, seconds, fps, 1, t0)
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_entries",
                            "stream=codec_name,width,height,nb_read_frames", "-of", "csv=p=0", str(webm)],
                           capture_output=True, text=True)
    codec, *rest = probe.stdout.strip().split(",")
    assert codec in ("vp9", "vp8") and [int(v) for v in rest] == [w, h, seconds * fps], probe.stdout
    for k, moment in ((0, t0 + seconds), (25, t0 + 25 / fps)):     # the fade is 2 s: frame 0 is all end
        frame, native = tmp_path / f"frame{k}.png", tmp_path / f"native{k}.png"
        subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(webm), "-vf", f"select=eq(n\\,{k})", "-vsync", "0",
                        "-frames:v", "1", str(frame)], check=True)
        done = app(["--window", "--size", f"{w}x{h}", "--time", repr(moment), "--screenshot", str(native)])
        assert done.returncode == 0, done.stderr
        later = tmp_path / f"later{k}.png"                  # a tenth of a second on: not this frame
        done = app(["--window", "--size", f"{w}x{h}", "--time", repr(moment + 0.1), "--screenshot", str(later)])
        assert done.returncode == 0, done.stderr
        here = mean_abs_diff(frame, native)
        assert here < 6.0 and here < mean_abs_diff(frame, later) / 2, k   # a lossy video of a busy picture


def test_the_desktop_makes_the_video_the_page_does(page, app, tmp_path):
    """syncrain --video and the page's Video section: the same frames, through different encoders."""
    ffmpeg = shutil.which("ffmpeg")
    need(ffmpeg is not None, "no ffmpeg for syncrain --video")
    t0, seconds, fps, w, h = int(MOMENT), 3, 10, 640, 360
    webm, mkv = tmp_path / "page.webm", tmp_path / "app.mkv"
    page("video", webm, w, h, seconds, fps, 1, t0)
    _the_seek_head_finds(webm.read_bytes())
    done = app(["--time", str(t0), "--video", str(mkv), "--seconds", str(seconds), "--video-fps", str(fps),
                "--size", f"{w}x{h}"], timeout=300)
    assert done.returncode == 0, done.stderr
    for k in (0, 10, 25):                             # in the fade, at its middle, after it
        a, b = tmp_path / f"page{k}.png", tmp_path / f"app{k}.png"
        for src, dst in ((webm, a), (mkv, b)):
            subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(src), "-vf", f"select=eq(n\\,{k})", "-vsync", "0",
                            "-frames:v", "1", str(dst)], check=True)
        assert mean_abs_diff(a, b) < 7.0, k            # two lossy encoders


def _ebml(data, at):
    """An element at `at`: its id (with its length marker), its body's start and its body's length."""
    def vint(i, keep):
        first = data[i]
        n = 8 - first.bit_length() + 1
        v = first if keep else first & ((1 << (8 - n)) - 1)
        for b in data[i + 1:i + n]:
            v = v * 256 + b
        return v, i + n
    ident, i = vint(at, True)
    size, i = vint(i, False)
    return ident, i, size


def _the_seek_head_finds(data):
    """The page's WebM starts its segment with a SeekHead, and each place in it holds what it names."""
    _, body, size = _ebml(data, 0)
    segment, seg_body, _ = _ebml(data, body + size)
    assert segment == 0x18538067
    head, at, size = _ebml(data, seg_body)
    assert head == 0x114D9B74, hex(head)
    found, end = {}, at + size
    while at < end:
        _, seek_body, seek_size = _ebml(data, at)
        fields, i = {}, seek_body
        while i < seek_body + seek_size:
            ident, b, n = _ebml(data, i)
            fields[ident] = data[b:b + n]
            i = b + n
        found[int.from_bytes(fields[0x53AB], "big")] = int.from_bytes(fields[0x53AC], "big")
        at = seek_body + seek_size
    assert sorted(found) == sorted([0x1549A966, 0x1654AE6B, 0x1C53BB6B])
    for ident, place in found.items():
        assert _ebml(data, seg_body + place)[0] == ident, hex(ident)


#: Settings files at the edges of the grammar: what one side takes, the other takes, and reads the same.
#: (Before, 18 of 41 such files were taken by one and refused by the other.)
EDGES = [
    {"speed": 1.5}, {"speed": "1.5"}, {"speed": " 1.5 "}, {"speed": "0x10"}, {"speed": "1_0"},
    {"speed": "\uff11"}, {"speed": "Infinity"}, {"speed": "nan"}, {"speed": ""}, {"speed": "1e0"},
    {"speed": ".5"}, {"speed": "1."}, {"speed": "+1"}, {"speed": "\ufeff1"}, {"speed": "1\u00a0"},
    {"speed": True}, {"speed": None}, {"speed": [1]}, {"speed": "0b1"},
    {"channel": "friends"}, {"channel": 5}, {"channel": "\ud800"}, {"channel": "-x"}, {"channel": True},
    {"snow": True}, {"snow": "on"}, {"snow": "yes"}, {"snow": 1},
    {"preset": "matrix"}, {"preset": "MATRIX"}, {"preset": " matrix"},
    {"spin": 5}, {"spin": "5"}, {"spin": 0}, {"spin": -15},
    {"flavours": 2}, {"flavours": 2.5}, {"flavours": "2"},
    {"fps": "60"}, {"fps": 0},
    {"words": ["A", "B"]}, {"words": ["A,B"]}, {"words": "A"},
    {"glow_color": "#ff0000"}, {"glow_color": [1, 0, 0]}, {"glow_color": [True, 0, 0]}, {"glow_color": "red"},
    {"logo": "nixos"}, {"logo": "NixOS"},
    {"scale": 0.75}, {"scale": "0.5"}, {"scale": 4}, {"scale": 5}, {"scale": 0}, {"scale": True},
    {"layer": "bottom"}, {"layer": "top"}, {"layer": 1},
    {"background": "wall.png"}, {"background": "pictures/wall.png"}, {"background": ""}, {"background": 5},
    {"mask": "mask.png"}, {"mask": "  "}, {"background": "\u001c"}, {"mask": "\u2003"},
    {"no_such": 1},
]
#: The settings compared where both take the file: what the desktop's options become, on the page.
SAME = {"speed": "speed", "channel": "channel", "spin": "spin", "flavours": "flavours", "fps": "fps",
        "scale": "scale", "layer": "layer"}
#: Pictures on the desktop's machine: the desktop reads them beside the settings file, the page
#: keeps them as written and writes them back so.
PICTURES = ("background", "mask")


def _texts():
    head = '{"contract": "syncrain-config-1", '
    texts = [head + json.dumps(e)[1:] for e in EDGES]
    texts.append("\ufeff" + head + '"speed": 1.25}')                     # a byte order mark first
    texts.append(head + '"speed": 1, "speed": 2}')                       # a key twice: the last
    texts.append(head + '"cycle": 1e400}')                               # past what a double holds
    texts.append(head + '"speed": "1.5", "channel": "\\ud83d\\ude00"}')  # a whole character, escaped
    return texts


def test_the_page_and_the_desktop_read_the_same_settings_files(page, tmp_path):
    from syncrain.app import parse_args
    texts = _texts()
    (tmp_path / "texts.json").write_text(json.dumps(texts), encoding="utf-8")
    on_page = page("reads", tmp_path / "texts.json")["reads"]
    for picture in ("wall.png", "pictures/wall.png", "mask.png"):    # on the desktop's machine, beside the file
        (tmp_path / picture).parent.mkdir(exist_ok=True)
        (tmp_path / picture).write_bytes(b"")
    differ = []
    for i, (text, web) in enumerate(zip(texts, on_page)):
        path = tmp_path / f"{i}.json"
        path.write_bytes(text.encode("utf-8", "surrogatepass"))
        try:
            import contextlib
            import io
            with contextlib.redirect_stderr(io.StringIO()):
                args = parse_args(["--config", str(path)])
        except SystemExit:
            args = None
        if (args is None) != bool(web["said"]):
            differ.append(f"{text!r}: desktop {'refuses' if args is None else 'takes'} it, page {web['said']!r}")
            continue
        if args is None:
            continue
        given = json.loads(text.lstrip("\ufeff"))
        for key, dest in SAME.items():
            if key in given and given[key] is not None:
                ours, theirs = getattr(args, dest), web["exported"][key]
                if (float(ours) if isinstance(theirs, (int, float)) else ours) != theirs:
                    differ.append(f"{text!r}: {key} is {ours!r} on the desktop, {theirs!r} on the page")
        for key in PICTURES:
            if key in given:
                ours, theirs = getattr(args, key), web["exported"].get(key)
                if theirs != given[key] or ours != str(path.parent / given[key]):
                    differ.append(f"{text!r}: {key} is {ours!r} on the desktop, {theirs!r} on the page")
    assert not differ, "\n".join(differ)
