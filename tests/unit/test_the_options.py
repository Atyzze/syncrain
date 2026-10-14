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
    assert parse_args(["--config", "none"]).theme == "nixos"


@pytest.mark.parametrize("values, says", [({"spin": "fast"}, "--spin"), ({"colour": "red"}, "no setting 'colour'"),
                                          ({"glyphs": {"sets": []}}, "needs a list"), ({"speed": [1]}, "list"),
                                          ({"theme": "nope"}, "no theme 'nope'")])
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
