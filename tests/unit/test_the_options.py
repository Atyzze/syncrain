"""Options are checked as they are read: a number that is not one, or out of what the option can
use, and a picture that is not there, end at once with argparse's status 2, which no service
restarts on, instead of a black screen or a crash at every start."""
from __future__ import annotations

import pytest

from syncrain.app import NO_RESTART, parse_args


@pytest.mark.parametrize("argv", [["--spin", "nan"], ["--speed", "inf"], ["--speed", "0"], ["--fps", "-1"],
                                  ["--hieroglyphs", "1.5"], ["--scale", "0"], ["--density", "-0.1"],
                                  ["--record-fps", "0"], ["--background", "/nonexistent/picture.png"],
                                  ["--mask", "/nonexistent/mask.png"], ["--glow", "lots"],
                                  ["--theme", "constructor"]])
def test_an_option_it_cannot_use_ends_with_status_2(argv, capsys):
    with pytest.raises(SystemExit) as stop:
        parse_args(argv)
    assert stop.value.code == 2 and 2 in NO_RESTART
    assert argv[0] in capsys.readouterr().err


def test_what_it_can_use_goes_through(tmp_path):
    picture = tmp_path / "p.png"
    picture.write_bytes(b"x")
    args = parse_args(["--spin", "0", "--speed", "0.25", "--hieroglyphs", "1", "--density", "0", "--drift", "-0.02",
                       "--background", str(picture), "--time", "1791331207.5"])
    assert (args.spin, args.speed, args.hieroglyphs, args.background) == (0.0, 0.25, 1.0, str(picture))


@pytest.mark.parametrize("given, channel", [(" friends ", "friends"), ("", "public"), ("  ", "public"),
                                            ("\ufefffriends\u3000", "friends"), ("\x1cfriends", "\x1cfriends"),
                                            ("it's 100% $HOME", "it's 100% $HOME")])
def test_the_channel_is_named_as_the_page_names_it(given, channel):
    assert parse_args(["--channel", given]).channel == channel


# ---- the settings file the web page exports (--config, ~/.config/syncrain/config.json)

def settings(tmp_path, **values):
    import json
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"contract": "syncrain-config-1", **values}), encoding="utf-8")
    return str(path)


def test_a_settings_file_gives_the_options_and_the_command_line_goes_over_it(tmp_path):
    path = settings(tmp_path, theme="matrix", spin=90, snow=False, speed=1.5, bg_gain=0.6, hieroglyphs=None,
                    pause_under="fullscreen", glyphs={"sets": [{"name": "d", "chars": "0123456789"}]})
    args = parse_args(["--config", path])
    assert (args.theme, args.spin, args.snow, args.speed, args.bg_gain, args.hieroglyphs, args.pause_under) == \
        ("matrix", 90.0, "off", 1.5, 0.6, None, "fullscreen")
    assert args.glyphs["sets"][0]["chars"] == "0123456789" and args.config_file == path
    over = parse_args(["--config", path, "--speed", "2", "--glyphs", "theme"])
    assert (over.speed, over.glyphs, over.theme) == (2.0, "theme", "matrix")


def test_the_settings_file_is_read_from_its_place_unless_told_none(tmp_path, monkeypatch):
    (tmp_path / "syncrain").mkdir()
    (tmp_path / "syncrain/config.json").write_text('{"contract": "syncrain-config-1", "theme": "matrix"}')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert parse_args([]).theme == "matrix"
    assert parse_args(["--config", "none"]).theme == "syncrain"


@pytest.mark.parametrize("values, says", [({"spin": "fast"}, "--spin"), ({"colour": "red"}, "no setting 'colour'"),
                                          ({"glyphs": {"sets": []}}, "needs a list"), ({"speed": [1]}, "list"),
                                          ({"theme": "nope"}, "no preset 'nope'")])
def test_a_settings_file_it_cannot_use_ends_with_status_2_and_says_where(tmp_path, capsys, values, says):
    path = settings(tmp_path, **values)
    with pytest.raises(SystemExit) as stop:
        parse_args(["--config", path])
    err = capsys.readouterr().err
    assert stop.value.code == 2 and says in err and path in err


def test_a_file_that_is_not_one_of_syncrain_s_says_so(tmp_path, capsys):
    (tmp_path / "x.json").write_text('{"theme": "matrix"}')
    with pytest.raises(SystemExit):
        parse_args(["--config", str(tmp_path / "x.json")])
    assert "not a syncrain settings file" in capsys.readouterr().err


def test_the_login_screen_s_rain_reads_the_operator_s_settings_file(tmp_path, monkeypatch):
    from syncrain import greeter
    monkeypatch.setattr(greeter, "LIB", tmp_path)
    assert greeter.rain_command({"rain": ["--fps", "20"]})[3:5] == ["--config", "none"]
    (tmp_path / "config.json").write_text("{}")
    assert greeter.rain_command({"rain": ["--fps", "20"]})[3:7] == ["--config", str(tmp_path / "config.json"),
                                                                    "--fps", "20"]
    sets = '{"contract": "syncrain-config-1", "glyphs": {"sets": [{"name": "d", "chars": "01"}]}}'
    (tmp_path / "config.json").write_text(sets)
    rain = greeter.rain_command({"rain": ["--glyphs", "/usr/local/lib/syncrain/glyphs.json", "--fps", "20"]})
    assert rain[5:] == ["--fps", "20", "--pause-under", "never"], "the settings file's sets go over a symbols file"


def test_what_the_page_saves_reads_even_when_it_starts_with_a_dash(tmp_path):
    """A channel the page takes as it is, and a negative number Python writes with an exponent."""
    args = parse_args(["--config", settings(tmp_path, channel="-x", drift=-0.00005, spin=-1e20)])
    assert (args.channel, args.drift, args.spin) == ("-x", -0.00005, -1e20)


def test_a_huge_number_is_said_not_thrown(tmp_path, capsys):
    path = tmp_path / "config.json"
    path.write_text('{"contract": "syncrain-config-1", "speed": 1' + "0" * 400 + "}")
    with pytest.raises(SystemExit) as stop:
        parse_args(["--config", str(path)])
    assert stop.value.code == 2 and "too large" in capsys.readouterr().err


def test_a_broken_settings_file_stops_neither_build_nor_help_and_diagnose_says_it(tmp_path, monkeypatch, capsys):
    (tmp_path / "syncrain").mkdir()
    (tmp_path / "syncrain/config.json").write_text('{"contract": "syncrain-config-1", "speeed": 2}')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(SystemExit) as stop:
        parse_args(["--build"])
    assert stop.value.code == 0
    assert parse_args(["--diagnose"]).config_file is None
    assert "is not used" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        parse_args([])


def test_a_shortened_option_is_no_option(capsys):
    with pytest.raises(SystemExit) as stop:
        parse_args(["--conf", "x.json"])
    assert stop.value.code == 2


def test_check_config_refuses_sets_the_wallpaper_would_not_draw(tmp_path, capsys):
    from syncrain.app import main
    many = "".join(chr(0x4E00 + i) for i in range(700))
    assert main(["--config", settings(tmp_path, glyphs={"sets": [{"name": "kanji", "chars": many}]}),
                 "--check-config"]) == 2
    assert "at most 640" in capsys.readouterr().err


def test_the_look_s_options_and_their_settings(tmp_path):
    from syncrain import engine
    from syncrain.renderer import from_args
    args = parse_args(["--config", "none", "--preset", "matrix", "--rain-colors", "#000000,#ff0000,0.5/0.25/1,#ffffff",
                       "--glow-color", "#102030", "--flavours", "3.0", "--flavour-layout", "wave", "--cycle", "45",
                       "--words", "HI,THERE", "--logo-size", "0.3", "--logo-cycle", "0", "--vignette", "0.2"])
    assert (args.theme, args.flavours, args.flavour_layout, args.cycle, args.words) == ("matrix", 3, "wave", 45.0,
                                                                                         ["HI", "THERE"])
    th = from_args(args, glyphs="theme").th
    assert th["colors"]["mid"] == [1.0, 0.0, 0.0] and th["colors"]["pale"] == [0.5, 0.25, 1.0]
    assert (th["rain"]["flavours"], th["logo"]["hueCycle"], th["wordText"]) == (3, 0.0, ["HI", "THERE"])
    assert engine.motion(th)["uRainHueCph"] == 80
    path = settings(tmp_path, preset="matrix", rain_colors=["#000000", "#ff0000", [0.5, 0.25, 1], "#ffffff"],
                    glow_color=[0.1, 0.2, 0.3], background_colors=["#010203", "#040506", "#070809"], flavours=3,
                    words=[], snow=None)
    from_file = parse_args(["--config", path])
    assert from_file.rain_colors == args.rain_colors and from_file.glow_color == [0.1, 0.2, 0.3]
    assert from_file.words == [] and from_file.flavours == 3 and from_file.snow is None


@pytest.mark.parametrize("argv", [["--rain-colors", "#000000,#ffffff"], ["--rain-colors", "red,green,blue,white"],
                                  ["--glow-color", "1/2/3"], ["--flavours", "65"], ["--flavours", "2.5"],
                                  ["--words", "TOO LONG A WORD"], ["--words", "A" * 17], ["--logo", "/no/such.png"],
                                  ["--logo-size", "1"], ["--vignette", "2"], ["--flavour-layout", "spiral"]])
def test_a_look_it_cannot_draw_ends_with_status_2(argv, capsys):
    with pytest.raises(SystemExit) as stop:
        parse_args(["--config", "none", *argv])
    assert stop.value.code == 2 and argv[0] in capsys.readouterr().err


def test_a_logo_of_one_s_own_from_a_file_or_from_the_page(tmp_path):
    import base64
    from PIL import Image
    from syncrain import logo
    picture = tmp_path / "p.png"
    Image.new("RGBA", (40, 20), (200, 30, 30, 255)).save(picture)
    made = logo.prepare(Image.open(picture))
    assert made.size == (logo.SIDE, logo.SIDE)
    assert made.getchannel("A").getbbox() == (170, 341, 853, 683), "the middle two thirds across"
    assert made.getpixel((0, 0)) == (200, 30, 30, 0), "the picture's colour under its see-through pixels"
    made.save(tmp_path / "t.png")
    uri = "data:image/png;base64," + base64.b64encode((tmp_path / "t.png").read_bytes()).decode()
    w, h, data = logo.texture(uri, "", None)
    assert (w, h) == made.size and data == made.tobytes(), "the page's texture is used as it is"
    assert parse_args(["--config", "none", "--logo", str(picture)]).logo == str(picture)
    assert parse_args(["--config", "none", "--logo", "nixos"]).logo == "nixos"
    with pytest.raises(SystemExit):
        parse_args(["--config", "none", "--logo", "data:image/png;base64,bm90IGEgcG5n"])


def test_a_font_whose_file_name_is_not_utf8_is_still_a_font(tmp_path, monkeypatch):
    from syncrain import glyphs
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "fc-list").write_bytes(b"#!/bin/sh\nprintf '/fonts/caf\\351.ttf\\t0\\tCafe\\tBold\\t41-5a\\n'\n")
    (fake / "fc-list").chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake}:/usr/bin:/bin")
    fonts = glyphs.font_list()
    assert len(fonts) == 1 and fonts[0]["family"] == "Cafe" and fonts[0]["ranges"] == [(0x41, 0x5A)]


def test_the_words_hold_at_most_254_different_characters(capsys):
    many = ",".join("".join(chr(0x4E00 + w * 10 + i) for i in range(10)) for w in range(26))
    with pytest.raises(SystemExit):
        parse_args(["--config", "none", "--words", many])
    assert "254 different characters" in capsys.readouterr().err
    assert len(parse_args(["--config", "none", "--words", many[:274]]).words) == 25


def test_rainbow_goes_over_a_settings_file_as_any_option_does(tmp_path):
    from syncrain import engine
    from syncrain.renderer import from_args
    path = settings(tmp_path, preset="nixos", logo_cycle=90, cycle=0)
    def cycles(argv):
        motion = engine.motion(from_args(parse_args(argv), glyphs="theme").th)
        return motion["uLogoHueCph"], motion["uRainHueCph"]
    assert cycles(["--config", path, "--rainbow", "off"]) == (0, 0)
    assert cycles(["--config", path, "--rainbow", "all"]) == (40, 6)
    assert cycles(["--config", path, "--rainbow", "off", "--logo-cycle", "60"]) == (60, 0), "what comes after goes over"
    assert cycles(["--config", settings(tmp_path, theme="nixos", rainbow="all")]) == (40, 6), "build 21's files as they were"


def test_build_21_s_matrix_files_still_have_no_snow(tmp_path):
    from syncrain.renderer import from_args
    old = parse_args(["--config", settings(tmp_path, theme="matrix", snow=True, rainbow=None)])
    assert from_args(old, glyphs="theme").look["snow"] is False
    new = parse_args(["--config", settings(tmp_path, preset="matrix", snow=True)])
    assert from_args(new, glyphs="theme").look["snow"] is True


def test_a_logo_file_that_is_no_picture_is_refused_at_once(tmp_path, capsys):
    svg = tmp_path / "logo.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>')
    with pytest.raises(SystemExit) as stop:
        parse_args(["--config", "none", "--logo", str(svg)])
    assert stop.value.code == 2 and "not a picture syncrain reads" in capsys.readouterr().err


def test_one_colour_over_the_logo_and_its_own_again(tmp_path):
    from syncrain.renderer import from_args, static_uniforms
    def tint(argv):
        r = from_args(parse_args(["--config", "none", *argv]), glyphs="theme")
        return next(v for p, n, k, v in static_uniforms(r) if n == "uLogoTint")
    assert tint([]) == (0.0, 0.0, 0.0, 0.0), "the logo's own colours"
    assert tint(["--logo-color", "#ff0000"]) == (1.0, 0.0, 0.0, 1.0)
    path = settings(tmp_path, logo_color="#00ff00")
    r = from_args(parse_args(["--config", path]), glyphs="theme")
    assert r.th["logo"]["color"] == [0.0, 1.0, 0.0], "the settings file's colour"
    r = from_args(parse_args(["--config", path, "--logo-color", "own"]), glyphs="theme")
    assert "color" not in r.th["logo"], "own, on the command line, goes over the file's colour"


def test_the_default_is_the_operator_s_own_look():
    from syncrain import engine
    from syncrain.renderer import from_args
    r = from_args(parse_args(["--config", "none"]), glyphs="theme")
    assert (r.theme_name, r.logo_choice, r.th["rain"]["flavours"], r.th["rain"]["cycle"]) == ("syncrain", "syncrain", 64, 55)
    assert "sSs" in r.th["wordText"] and r.look["snow"] is False
    nixos = from_args(parse_args(["--config", "none", "--preset", "nixos"]), glyphs="theme")
    assert nixos.logo_choice == "white" and nixos.th["rain"]["flavours"] == 1, "nixos as it was"
    assert from_args(parse_args(["--config", "none", "--logo", "nixos"]), glyphs="theme").logo_choice == "white"
