"""Options are checked as they are read: a number that is not one, or out of what the option can
use, and a picture that is not there, end at once with argparse's status 2, which no service
restarts on, instead of a black screen or a crash at every start."""
from __future__ import annotations

import pytest

from syncrain.app import NO_RESTART, parse_args


@pytest.mark.parametrize("argv", [["--spin", "nan"], ["--speed", "inf"], ["--speed", "0"], ["--fps", "-1"],
                                  ["--hieroglyphs", "1.5"], ["--scale", "0"], ["--density", "-0.1"],
                                  ["--record-fps", "0"], ["--background", "/nonexistent/picture.png"],
                                  ["--mask", "/nonexistent/mask.png"], ["--glow", "lots"]])
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
