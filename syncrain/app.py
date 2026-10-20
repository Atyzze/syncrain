"""syncrain's options, and its GTK host: GTK4 + OpenGL (or OpenGL ES, whichever GTK hands out).

On Wayland the native wallpaper (syncrain/native.py) draws instead where it is built.

Wayland: one layer-shell surface per monitor (via gtk4-layer-shell); works on Hyprland, Sway,
         niri, river, Wayfire, labwc, COSMIC and KDE Plasma.
X11:     one desktop-type window covering the whole screen, one viewport per monitor.
--window opens an ordinary window instead (previews, or desktops without layer-shell such as GNOME).
"""
import argparse
import ctypes
import gc
import math
import os
import re
import signal
import sys
import time

from . import build, hidden, native
from .logo import SHIPPED as SHIPPED_LOGOS

#: The exit status when no OpenGL context can be had. The autostart services list it under
#: RestartPreventExitStatus, so a machine without working OpenGL is not covered by an endless
#: restart loop of blank wallpapers; sysexits.h calls it EX_UNAVAILABLE.
EXIT_NO_GL = 69
#: The exit status when the compositor offers no wallpaper layer (GNOME); argparse's too, for an
#: unknown option.
EXIT_NO_LAYER = 2
#: What every autostart service lists under RestartPreventExitStatus: a restart cannot change these,
#: so it would only start the same failure again every few seconds, for good. 70 is the native
#: wallpaper's for a scene from another build (syncrain/native/wallpaper.c).
#: A setting it cannot use (a picture or symbols file it cannot read, a font): sysexits.h's EX_CONFIG.
EXIT_CONFIG = 78
NO_RESTART = (EXIT_NO_LAYER, EXIT_NO_GL, 70, EXIT_CONFIG)

#: The oldest contexts the shaders compile on: GLSL 3.30 core, or GLSL ES 3.00 (what WebGL2 runs).
MIN_GL = {False: (3, 3), True: (3, 0)}


class _ShowBuild(argparse.Action):
    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        print(build.describe())
        parser.exit()


#: What JavaScript's String.prototype.trim() removes: WhiteSpace and LineTerminator (ECMA-262).
JS_SPACE = ("\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009"
            "\u200a\u2028\u2029\u202f\u205f\u3000\ufeff")


#: A number as an option or the settings file gives it, the same grammar as the page's (index.html,
#: DECIMAL): decimal digits, a point, an exponent, spaces at the ends. Python's float also took
#: "1_0", "\uff11" and " \u2003 1", the page's Number "0x10" and "0b1": one side drew what the
#: other refused.
DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


def _decimal(text: str) -> float:
    """The number text says, or ValueError (inf and nan are no such text)."""
    word = text.strip(" \t\n\r") if isinstance(text, str) else ""
    if not DECIMAL.fullmatch(word):
        raise ValueError(text)
    return float(word)


def _number(low=None, high=None, above=None):
    """An option's number: finite (never nan or inf, which every frame would carry), and within
    what the option can use. A value outside ends with argparse's status 2, said at once."""
    def parse(text):
        try:
            value = _decimal(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
        if not math.isfinite(value):
            raise argparse.ArgumentTypeError(f"not a finite number: {text!r}")
        if above is not None and not value > above:
            raise argparse.ArgumentTypeError(f"{text} is not above {above:g}")
        if (low is not None and value < low) or (high is not None and value > high):
            if high is None:
                raise argparse.ArgumentTypeError(f"{text} is below {low:g}")
            if low is None:
                raise argparse.ArgumentTypeError(f"{text} is above {high:g}")
            raise argparse.ArgumentTypeError(f"{text} is outside {low:g} to {high:g}")
        return value
    return parse


def _period(low=None):
    """A period in seconds: off (0, or below for a spin) or at least engine.SHORTEST_PERIOD, so
    nothing flashes (a cycle of 0.07 s strobed; a spin of 1e-320 overflowed every frame)."""
    number = _number(low=low)

    def parse(text):
        value = number(text)
        if 0 < value < 10:
            raise argparse.ArgumentTypeError(f"{text} s is too short: 0 (off) or 10 s and more")
        return value
    return parse


def _channel(text):
    """A channel name the seed can be made of: text UTF-8 can carry (no lone surrogate)."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        raise argparse.ArgumentTypeError("the channel holds a character that is no character") from None
    return text


def _size(text):
    """WIDTHxHEIGHT, each 1 to 16384: checked here for every use (a window, --record, --benchmark),
    not first inside the window where a wrong one raised."""
    try:
        w, h = (int(v) for v in text.lower().split("x"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"a size is WIDTHxHEIGHT, e.g. 1920x1080: {text!r}") from None
    if not (1 <= w <= 16384 and 1 <= h <= 16384):
        raise argparse.ArgumentTypeError(f"a size is 1 to 16384 pixels each way: {text!r}")
    return f"{w}x{h}"


def _theme(text):
    """A theme there is: refused here (status 2, which the service does not restart on), not when
    the wallpaper starts (status 1, which it restarts on, for good)."""
    from .engine import load_meta
    themes = load_meta()["themes"]
    if text not in themes:
        raise argparse.ArgumentTypeError(f"no preset {text!r} (the presets: {', '.join(themes)})")
    return text


def _colours(count):
    """A list of colours, comma-separated: "#rrggbb" or three numbers 0 to 1 split by "/"."""
    def parse(text):
        from .engine import colour
        words = [w.strip() for w in text.split(",")]
        if len(words) != count:
            raise argparse.ArgumentTypeError(f"{count} colours, comma-separated, not {len(words)}")
        out = []
        for w in words:
            try:
                out.append(colour([_decimal(x) for x in w.split("/")] if "/" in w else w))
            except ValueError as e:
                raise argparse.ArgumentTypeError(str(e)) from None
        return out if count > 1 else out[0]
    return parse


def _logo_colour(text):
    """One colour over the logo, or "" for the logo's own ("own", or empty)."""
    if text.strip() in ("", "own", "none"):
        return ""
    return _colours(1)(text)


def _flavours(text):
    """How many colours at once, 1 to 64 (a whole number; 3.0 is 3)."""
    try:
        value = _decimal(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
    if not value.is_integer() or not 1 <= value <= 64:
        raise argparse.ArgumentTypeError(f"{text} is not a whole number 1 to 64")
    return int(value)


#: Hidden words and sentences: at most this many, each this long at most, and at most this many
#: different characters among them besides the space (a word's slot is a byte: 255 ends a word, 254
#: is a space's gap). A word falls only where a column has rows for it and three to spare at each end
#: (state.frag): a 16:9 screen has 36 rows, room for 30; a 21:9 one 27, room for 21. The words
#: texture (glyphs.WORD_CELLS) has room for more.
MAX_WORDS, MAX_WORD, MAX_WORD_CHARS = 32, 30, 254


def _words(text):
    """The hidden words and sentences, comma-separated; none for none. A space inside falls as a gap
    in the column (glyphs.GAP); other spacing (a tab, a line break) is no part of one."""
    words = [w.strip() for w in text.split(",")] if text.strip() else []
    for w in words:
        if not w or any(ch.isspace() and ch != " " for ch in w) or len(w) > MAX_WORD:
            raise argparse.ArgumentTypeError(f"a word or sentence is 1 to {MAX_WORD} characters, spaces between "
                                             f"words only: {w!r}")
    if len(words) > MAX_WORDS:
        raise argparse.ArgumentTypeError(f"at most {MAX_WORDS} words")
    if len(set("".join(words).replace(" ", ""))) > MAX_WORD_CHARS:
        raise argparse.ArgumentTypeError(f"at most {MAX_WORD_CHARS} different characters in all the words")
    return words


class _Rainbow(argparse.Action):
    """--rainbow is the colour cycles it stood for, set where it stands among the options, so what
    comes after it (a settings file's cycles come before the command line) goes over it."""

    def __call__(self, parser, namespace, value, option_string=None):
        from .engine import ALL_CYCLE
        namespace.rainbow = value
        if value == "off":
            namespace.logo_cycle = 0.0
        elif value == "all":
            namespace.cycle = float(ALL_CYCLE)


def _logo(text):
    from .logo import LogoError, check
    try:
        return check(text)
    except LogoError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def _image(text):
    """A picture file that is there to be read (the native wallpaper and the GTK host read it later)."""
    if not (os.path.isfile(text) and os.access(text, os.R_OK)):
        raise argparse.ArgumentTypeError(f"no picture file to read at {text}")
    return text


#: What a settings file is (the web page writes it): the options it may hold, as their command-line names.
CONFIG_CONTRACT = "syncrain-config-1"
CONFIG_KEYS = {"preset": "--preset", "theme": "--preset", "channel": "--channel", "rainbow": "--rainbow",
               "rain_colors": "--rain-colors", "glow_color": "--glow-color", "background_colors": "--background-colors",
               "vignette": "--vignette", "cycle": "--cycle", "flavours": "--flavours",
               "flavour_layout": "--flavour-layout", "logo": "--logo", "logo_color": "--logo-color", "logo_size": "--logo-size",
               "logo_cycle": "--logo-cycle", "spin": "--spin", "drift": "--drift", "speed": "--speed",
               "density": "--density", "glow": "--glow", "bloom": "--bloom", "bg_gain": "--bg-gain", "snow": "--snow",
               "hieroglyphs": "--hieroglyphs", "words": "--words", "fps": "--fps", "pause_under": "--pause-under", "lock_rest": "--lock-rest",
               # the desktop's own, kept in the file the page saves (it shows none of them): a picture
               # behind the rain, its mask, the drawing scale and the Wayland layer
               "background": "--background", "mask": "--mask", "scale": "--scale", "layer": "--layer"}
#: Settings that name a file: one given relative is the settings file's neighbour, wherever it is read.
PATH_KEYS = ("background", "mask")
#: A logo that names a picture file, as the page tells one from a logo's name (index.html, PICTURE_NAME).
PICTURE_ENDINGS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".ico", ".svg", ".svgz")
PICTURE_NAME = re.compile(r"(^|[/\\])[^/\\]+\.(png|jpe?g|webp|gif|bmp|tiff?|ico|svgz?)\Z", re.IGNORECASE | re.ASCII)
#: The settings whose values are colours: (how many, as a list).
COLOUR_KEYS = {"rain_colors": 4, "background_colors": 3, "glow_color": 1, "logo_color": 1}


#: The default settings file: config.json at the repository's top, copied in by tools/build_assets.py
#: (the default preset is made from it, so it and no settings file draw the same frame).
DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "config.json")


def write_default_config(path: str) -> int:
    """`syncrain --write-config PATH`: the default settings file, where there is none yet."""
    try:
        with open(DEFAULT_CONFIG, "rb") as fh:
            data = fh.read()
        with open(path, "xb") as out:          # never over a file someone made
            out.write(data)
    except OSError as e:
        print(f"syncrain: no settings file written to {path}: {e.strerror or e}", file=sys.stderr)
        return 1
    print(f"syncrain: the default settings written to {path}", flush=True)
    return 0


def default_config_path() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "syncrain", "config.json")


def _config_path(argv):
    """The settings file: --config's, else the default one when it is there; None for none."""
    named = None
    for i, a in enumerate(argv):
        if a == "--config" and i + 1 < len(argv):
            named = argv[i + 1]
        elif a.startswith("--config="):
            named = a.split("=", 1)[1]
    if named is not None:
        return None if named in ("", "none") else named
    path = default_config_path()
    return path if os.path.isfile(path) else None


def _colour_words(value, count, wrong, key):
    """A settings file's colours as the option takes them: "#rrggbb", or r/g/b exactly."""
    def word(c):
        if isinstance(c, str):
            return c
        if isinstance(c, list) and len(c) == 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                                                       for x in c):
            return "/".join(repr(float(x)) for x in c)
        wrong(f"{key}: {c!r} is no colour (\"#rrggbb\", or three numbers 0 to 1)")
    if count == 1:
        return word(value)
    if not isinstance(value, list) or len(value) != count:
        wrong(f"{key} is a list of {count} colours")
    return ",".join(word(c) for c in value)


def _read_settings(ap, path):
    """The settings file as options (checked as the command line's are) and its symbol sets."""
    import json

    def wrong(why):
        ap.error(f"{path}: {why}")
    try:
        # utf-8-sig: a byte order mark first (some editors write one) is no reason to refuse the
        # file, and the page, reading it as text, never saw one
        with open(path, encoding="utf-8-sig") as fh:
            cfg = json.load(fh)
    except OSError as e:
        wrong(e.strerror or str(e))
    except (ValueError, RecursionError) as e:    # RecursionError: nested past what Python reads
        wrong(f"not JSON ({type(e).__name__ if isinstance(e, RecursionError) else e})")
    if not isinstance(cfg, dict) or cfg.get("contract") != CONFIG_CONTRACT:
        wrong(f'not a syncrain settings file (it says "contract": "{CONFIG_CONTRACT}")')
    out = []
    # A file that names a "theme" was written by the page of build 21, which wrote "snow": true for
    # every theme, where matrix had none to show: there it means as the preset has it.
    legacy = "theme" in cfg and "preset" not in cfg
    for key, value in cfg.items():
        if key in ("contract", "about", "glyphs"):
            continue
        if legacy and key == "snow" and value in (True, "on"):
            continue
        if key not in CONFIG_KEYS:
            wrong(f"no setting {key!r} (the settings: {', '.join(CONFIG_KEYS)}, glyphs)")
        if value is None:                         # as the preset or the sets have it
            continue
        if key == "channel" and not isinstance(value, str):
            wrong("channel is a name in quotes")       # 5 was the channel "5.0" here, refused on the page
        if key in COLOUR_KEYS:
            value = _colour_words(value, COLOUR_KEYS[key], wrong, key)
        elif key in PATH_KEYS:
            if not isinstance(value, str) or not value.strip():
                wrong(f"{key} is a picture file's path in quotes")
            # beside the file itself: through a link (dotfiles), where the pictures are kept with it
            value = os.path.join(os.path.dirname(os.path.realpath(path)), os.path.expanduser(value))
            if not os.path.isfile(value):
                # a picture moved since: the wallpaper still starts, as without one (an option on
                # the command line is the operator's at that moment, and is refused instead)
                print(f"syncrain: {path}: no picture at {value}; the {key} is left out", file=sys.stderr)
                continue
        elif key == "logo" and isinstance(value, str) and not value.startswith("data:") \
                and value not in SHIPPED_LOGOS and value != "none":
            # a picture file by the name the page tells one by (it keeps such a logo, unseen), beside
            # the settings file as the background is
            if not PICTURE_NAME.search(value):
                wrong("logo is syncrain, nixos, none, a picture the page made, or a picture file's path "
                      f"(a name ending {', '.join(PICTURE_ENDINGS)})")
            value = os.path.join(os.path.dirname(os.path.realpath(path)), os.path.expanduser(value))
            if not os.path.isfile(value):
                # moved since, as a background can be: the preset's logo, said
                print(f"syncrain: {path}: no picture at {value}; the preset's logo instead", file=sys.stderr)
                continue
        elif key == "words":
            if not isinstance(value, list) or not all(isinstance(w, str) and "," not in w for w in value):
                wrong("words is a list of words in quotes, none with a comma")
            value = ",".join(value)
        elif isinstance(value, bool):
            value = "on" if value else "off"
        elif isinstance(value, (int, float)):
            if key in ("spin", "cycle", "logo_cycle") and 0 < value < 10:
                # pages before build 35 wrote 5 one click from 0: 10 s, the shortest, said once
                print(f"syncrain: {path}: {key} {value:g} s is 10 s (the shortest)", file=sys.stderr)
                value = 10
            try:
                value = repr(float(value))
            except OverflowError:
                wrong(f"{key} is a number too large")
        elif not isinstance(value, str):
            wrong(f"{key} is a {type(value).__name__}")
        # one word, --option=value: a value that starts with "-" (a channel, -5e-05) is then no option
        out.append(f"{CONFIG_KEYS[key]}={value}")
    sets = cfg.get("glyphs")
    if sets is not None:
        from . import glyphs
        try:
            sets = glyphs.check_config(sets, f"{path}'s glyphs")
        except glyphs.GlyphsError as e:
            ap.error(str(e))
    try:
        ap.parse_args(out)                        # said as from the file, not as from the command line
    except SystemExit:
        print(f"syncrain: that is in {path}", file=sys.stderr)
        raise
    return out, sets


#: Options that only say something and exit, whatever the settings file holds.
INFO_ONLY = {"--build", "--version", "-h", "--help", "--list-themes", "--write-config"}


def parse_args(argv=None):
    # no shortened options: --conf would be --config to argparse and not to _config_path
    ap = argparse.ArgumentParser(prog="syncrain", description="Never-repeating, clock-synchronised code rain wallpaper.",
                                 allow_abbrev=False)
    ap.add_argument("--preset", "--theme", dest="theme", type=_theme,
                    help="where the look starts: syncrain (the default), nixos or matrix; every option below "
                         "goes over it")
    ap.add_argument("--channel", default="public", type=_channel,
                    help="stream name; everyone on the same channel with a synced clock sees the same frame")
    ap.add_argument("--fps", type=_number(above=0, high=1000), default=30.0,
                    help="frame rate cap (default 30); frames land on whole refreshes of the screen")
    ap.add_argument("--pause-under", choices=hidden.POLICIES, default="never",
                    help="on KDE Plasma, stop drawing a screen while a maximized or full-screen window covers "
                         "it (maximized), only while a full-screen one does (fullscreen), or never (the default)")
    ap.add_argument("--lock-rest", type=_number(low=0, high=86400), default=0.0, metavar="SECONDS",
                    help="the lock screen draws 10 fps instead of 30 after this many seconds without a key or a "
                         "moved pointer, and 30 again at the next one; 0, the default: never")
    ap.add_argument("--pacing", choices=("refresh", "timer"), default="refresh",
                    help=argparse.SUPPRESS)        # timer: build 4's frame timing, for the power sweep's comparison
    ap.add_argument("--host", choices=native.HOSTS, default="auto",
                    help="what draws the wallpaper on Wayland: auto (the native program when it is built, "
                         "else Python and GTK), native (the native program only) or gtk (Python and GTK, as on "
                         "X11 and in a window)")
    ap.add_argument("--logo", type=_logo, metavar="LOGO",
                    help="syncrain, nixos, none, or a picture file (PNG, JPEG, WebP: what Pillow reads); the preset's otherwise")
    ap.add_argument("--logo-color", type=_logo_colour, metavar="C",
                    help="one colour over the logo, #rrggbb (the default: the logo's own; 'own' for its own again)")
    ap.add_argument("--logo-size", type=_number(low=0.05, high=0.9), metavar="F",
                    help="the logo's height, in screen heights (the preset's otherwise)")
    ap.add_argument("--logo-cycle", type=_period(low=0), metavar="SECONDS",
                    help="seconds a turn of the logo's rainbow (the preset's otherwise; 0 = the logo's own colours)")
    ap.add_argument("--rain-colors", type=_colours(4), metavar="C,C,C,C",
                    help="the rain's gradient, dark to bright, then the leading symbol: #rrggbb each")
    ap.add_argument("--glow-color", type=_colours(1), metavar="C", help="the glow round the rain: #rrggbb")
    ap.add_argument("--background-colors", type=_colours(3), metavar="C,C,C",
                    help="the background gradient: top, bottom, centre glow (#rrggbb each)")
    ap.add_argument("--vignette", type=_number(low=0, high=1), metavar="F",
                    help="how much darker the corners are, 0 to 1 (the preset's otherwise)")
    ap.add_argument("--flavours", type=_flavours, metavar="N",
                    help="colours at once, 1 to 64 (the preset's otherwise): each column of rain one of N hues round the wheel")
    ap.add_argument("--flavour-layout", choices=("random", "wave"),
                    help="random: the columns' hues by the channel; wave: in order across the screen (the preset's otherwise)")
    ap.add_argument("--cycle", type=_period(low=0), metavar="SECONDS",
                    help="seconds a turn of the rain's hue wheel, every flavour together (the preset's otherwise; "
                         "0 = the colours stay)")
    ap.add_argument("--words", type=_words, metavar="W,W,...",
                    help="the hidden words and sentences that fall now and then, comma-separated, up to 30 characters "
                         "each; a space falls as a gap ('' for none)")
    ap.add_argument("--background", type=_image, metavar="IMAGE", help="use an image as the background instead of the background gradient")
    ap.add_argument("--mask", type=_image, metavar="IMAGE", help="greyscale mask (same framing as --background): white = keep bright, no rain")
    ap.add_argument("--bg-gamma", type=_number(above=0), help="darkening curve for --background (default 2.0; 1 = unchanged)")
    ap.add_argument("--bg-gain", type=_number(low=0),
                    help="background brightness: the gradient's (the preset's otherwise: 0.6 for syncrain, 1 for "
                         "nixos and matrix; lower is darker) or --background's (default 0.42; 1 = unchanged)")
    ap.add_argument("--rainbow", choices=("logo", "all", "off"), action=_Rainbow,
                    help="the earlier spelling of --logo-cycle and --cycle: logo (as is), all (--cycle 600) or "
                         "off (--logo-cycle 0)")
    ap.add_argument("--spin", type=_period(), metavar="SECONDS",
                    help="seconds per logo revolution (the preset's otherwise: 300 for syncrain, 180 for nixos "
                         "and matrix; 0 = still)")
    ap.add_argument("--drift", type=_number(), metavar="FRACTION",
                    help="slow orbit of the logo / pan of the image, in screen heights (the preset's otherwise: "
                         "0 for syncrain, 0.03 for nixos and matrix; 0 = fixed)")
    ap.add_argument("--speed", type=_number(above=0), metavar="F",
                    help="how fast the symbols fall, times the preset's (default 1; 0.25 to 4)")
    ap.add_argument("--density", type=_number(low=0), metavar="F",
                    help="how often a column starts a new stream, times the preset's (the preset's otherwise: "
                         "1.15 for syncrain, 1 for nixos and matrix; 0 to 2.3)")
    ap.add_argument("--glow", type=_number(low=0), metavar="F",
                    help="the glow around the centre and the logo (the preset's otherwise: 0.5 for syncrain, 1 for "
                         "nixos and matrix; 0 = none)")
    ap.add_argument("--bloom", type=_number(low=0), metavar="F",
                    help="the glow around the falling symbols, times the preset's (default 1; 0 = none)")
    ap.add_argument("--snow", choices=("on", "off"), help="the falling snowflakes (the preset's otherwise: on for syncrain and nixos, off for matrix)")
    ap.add_argument("--hieroglyphs", type=_number(low=0, high=1), metavar="SHARE",
                    help="share of the changing symbols that are Egyptian hieroglyphs (default: as the symbol sets "
                         "say, 0.15 in the presets; 0 = none, 1 = only)")
    ap.add_argument("--config", metavar="FILE",
                    help="a settings file, as the web page exports it (default: ~/.config/syncrain/config.json "
                         "if there is one; 'none' for none); options given here go over it")
    ap.add_argument("--check-config", action="store_true",
                    help="read the settings file and the options, say what they come to, exit (status 2 if wrong)")
    ap.add_argument("--glyphs", metavar="FILE",
                    help="a symbols file: sets of characters and how often each falls (default: "
                         "~/.config/syncrain/glyphs.json if there is one, else the preset's; 'theme' for the preset's)")
    ap.add_argument("--write-glyphs", action="store_true",
                    help="write a starter symbols file (to --glyphs, or ~/.config/syncrain/glyphs.json) and exit")
    ap.add_argument("--scale", type=_number(above=0, high=4), default=1.0, help="render resolution scale, e.g. 0.75 on weak GPUs")
    ap.add_argument("--layer", choices=("background", "bottom"),
                    help="Wayland layer (default: bottom on KDE Plasma, whose own desktop sits on the background layer)")
    ap.add_argument("--window", action="store_true", help="ordinary window instead of a wallpaper")
    # within about 3000 years of now, which the millisecond grid still carries exactly
    ap.add_argument("--offset", type=_number(low=-1e11, high=1e11), default=0.0,
                    help="add this many seconds to the clock")
    ap.add_argument("--time", type=_number(low=0, high=1e11),
                    help="freeze the clock at this UNIX time (screenshots, tests)")
    ap.add_argument("--screenshot", metavar="PNG", help="render one frame and save it, then exit: on X11 the whole desktop as the wallpaper draws it; on Wayland, or with --window, a window of about --size (default 1280x720; device pixels, as the compositor sizes it)")
    ap.add_argument("--record", metavar="DIR", help="render a clip as numbered PNGs into DIR (from --time or now), exit")
    ap.add_argument("--record-seconds", type=_number(above=0), default=8.0, help="how long --record is (default 8)")
    ap.add_argument("--record-fps", type=_number(above=0, high=1000), default=30.0,
                    help="frames per second of --record (default 30)")
    ap.add_argument("--video", metavar="FILE",
                    help="make a video of the rain that plays on anything (.mp4, .mkv, .webm or .gif; needs ffmpeg), "
                         "from --time or now, at --size (default 1920x1080, 640x360 for a GIF), exit")
    ap.add_argument("--seconds", type=_number(above=0, high=3600), metavar="N",
                    help="how long --video is (default 30, a GIF 10)")
    ap.add_argument("--video-fps", type=_number(above=0, high=240), metavar="FPS",
                    help="frames per second of --video (default 30, a GIF 15)")
    ap.add_argument("--size", type=_size, help="window size for --window / --record (default 1280x720), the size of --video, "
                                   "or the size --benchmark draws at (default: the first screen), e.g. 1920x1080")
    ap.add_argument("--list-themes", action="store_true", help="list the presets and exit")
    ap.add_argument("--benchmark", action="store_true",
                    help="time each pass on this machine's graphics card, print the table, exit")
    ap.add_argument("--power-sweep", action="store_true",
                    help="measure the graphics card's power with syncrain at several settings (a few minutes), "
                         "print the table and save it; every screen goes black in its last two phases")
    ap.add_argument("--sweep-seconds", type=int, default=25, help="seconds per --power-sweep phase (default 25)")
    ap.add_argument("--write-scene", metavar="PATH", help=argparse.SUPPRESS)   # the lock screen's scene
    ap.add_argument("--write-config", metavar="PATH",
                    help="write the default settings file (config.json, what no settings file draws) to PATH, "
                         "which must not exist yet, and exit; install.sh makes one this way where it finds none")
    ap.add_argument("--diagnose", action="store_true",
                    help="check whether syncrain can draw on this machine, print what it found, exit")
    ap.add_argument("--build", action=_ShowBuild, help="print the build number and the stream fingerprint, exit")
    ap.add_argument("--version", action=_ShowBuild, help=argparse.SUPPRESS)   # the reflex spelling; says the build
    argv = list(sys.argv[1:] if argv is None else argv)
    # what says the build or the help reads no settings file, so a broken one cannot stop it (the
    # installer runs --build before it puts a good one in its place); --diagnose says it and goes on
    path = None if INFO_ONLY.intersection(argv) else _config_path(argv)
    settings, sets = [], None
    if path:
        try:
            settings, sets = _read_settings(ap, path)
        except SystemExit:
            if "--diagnose" not in argv:
                raise
            print(f"syncrain: {path} is not used (see above)", file=sys.stderr)
            path = None
    args = ap.parse_args(settings + argv)        # the command line's last, so it goes over the file
    args.config_file = path
    args.typed = argv                             # the command line alone (--power-sweep passes it on)
    if args.theme is None:                        # the preset with nothing said
        from .engine import default_preset, load_meta
        args.theme = default_preset(load_meta())
    if sets is not None and args.glyphs is None:
        args.glyphs = sets                        # the file's symbol sets, unless --glyphs names others
    # the channel as the web page takes it: spaces around it (what JavaScript's trim() takes, which is
    # not quite what str.strip() takes) are no part of the name, and none is public
    args.channel = args.channel.strip(JS_SPACE) or "public"
    if args.video:                                # said now, not after the window has opened
        from . import video
        if args.record or args.screenshot:
            ap.error("--video makes one file: not with --record or --screenshot")
        try:
            video.settle(args)
        except ValueError as e:
            ap.error(f"argument --video: {e}")
    return args


def _preload_layer_shell():
    """gtk4-layer-shell has to be loaded before libwayland-client. Nix wrappers set LD_PRELOAD;
    elsewhere, re-exec once with it set."""
    if not os.environ.get("WAYLAND_DISPLAY") or os.environ.get("SYNCRAIN_REEXEC"):
        return
    if "gtk4-layer-shell" in os.environ.get("LD_PRELOAD", ""):
        return
    import ctypes.util                         # only here: it brings subprocess with it
    lib = ctypes.util.find_library("gtk4-layer-shell")
    if not lib:
        return
    os.environ["LD_PRELOAD"] = (lib + " " + os.environ.get("LD_PRELOAD", "")).strip()
    os.environ["SYNCRAIN_REEXEC"] = "1"
    os.execv(sys.executable, [sys.executable, "-m", "syncrain"] + sys.argv[1:])


def _x11_desktop_hints(xid):
    """Mark an X11 window as the desktop: below everything, on all workspaces, not in taskbars."""
    try:
        x11 = ctypes.CDLL("libX11.so.6")
    except OSError:
        return
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XInternAtom.restype = ctypes.c_ulong
    x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x11.XChangeProperty.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
    x11.XMoveWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int]
    x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    dpy = x11.XOpenDisplay(None)
    if not dpy:
        return
    atom = lambda n: x11.XInternAtom(dpy, n.encode(), 0)  # noqa: E731

    def set_atoms(prop, names):
        arr = (ctypes.c_ulong * len(names))(*[atom(n) for n in names])
        x11.XChangeProperty(dpy, xid, atom(prop), 4, 32, 0, ctypes.cast(arr, ctypes.c_void_p), len(names))

    set_atoms("_NET_WM_WINDOW_TYPE", ["_NET_WM_WINDOW_TYPE_DESKTOP"])
    set_atoms("_NET_WM_STATE", ["_NET_WM_STATE_BELOW", "_NET_WM_STATE_STICKY",
                                "_NET_WM_STATE_SKIP_TASKBAR", "_NET_WM_STATE_SKIP_PAGER"])
    x11.XMoveWindow(dpy, xid, 0, 0)
    x11.XSync(dpy, 0)
    x11.XCloseDisplay(dpy)


def gl_context_problem(ctx, Gdk):
    """Why a realized GTK GL context cannot run the shaders, or None when it can.

    Which API a context gets is GTK's choice, not ours: it creates every context to share with
    the display's own, and since GTK 4.14 that one is OpenGL ES unless GDK_DEBUG=gl-prefer-gl.
    So a GLArea must not ask for a version only one of the two APIs has (desktop GL 3.3 asked
    of OpenGL ES is 3.3 > 3.2 and nothing is tried); it takes what GTK offers and checks it here.
    """
    es = ctx.get_api() == Gdk.GLAPI.GLES if hasattr(ctx, "get_api") else bool(ctx.get_use_es())
    have = tuple(ctx.get_version())
    need = MIN_GL[es]
    if have < need:
        api = "OpenGL ES" if es else "OpenGL"
        return es, f"{api} {have[0]}.{have[1]} is too old; syncrain needs {api} {need[0]}.{need[1]}"
    return es, None


def describe_context(ctx, Gdk):
    from . import gl
    es = ctx.get_api() == Gdk.GLAPI.GLES if hasattr(ctx, "get_api") else bool(ctx.get_use_es())
    major, minor = ctx.get_version()
    try:
        renderer = gl.get_string(gl.GL_RENDERER) or "unknown renderer"
    except Exception:  # noqa: BLE001 - informational only
        renderer = "unknown renderer"
    return f"{'OpenGL ES' if es else 'OpenGL'} {major}.{minor} on {renderer}"


def use_gl_renderer():
    """Have GTK put our OpenGL picture on screen with its own OpenGL renderer, unless told otherwise.

    On Wayland, GTK 4.16 and later draw windows with Vulkan where they can, and then hand a GLArea's
    OpenGL texture to Vulkan every frame: without the GL driver's dmabuf export, by copying it through
    the processor, a full screen per frame per screen. Its OpenGL renderer uses the texture where it
    is. (GTK 4.14 spells its newer OpenGL renderer "ngl"; "gl" there is the older one, which also
    uses the texture as it is.) A GSK_RENDERER set by the user wins; the power sweep compares both.

    With the OpenGL renderer, GTK's dmabuf support is turned off too (GDK_DISABLE=dmabuf, which
    GTK 4.16 and later read). From 4.16 a GLArea hands each frame over as a dmabuf where the driver
    can export one (NVIDIA's can, and Mesa's on real hardware), so that it could be given to the
    compositor directly; syncrain's frames never are, so every frame was exported, wrapped and
    imported back by the same renderer that could have drawn the texture itself, and the first one
    made GTK start a whole Vulkan renderer beside it (`gdk_vulkan_init_dmabuf`), kept for the life
    of the process. Without dmabufs the renderer draws the GLArea's texture as it is, as GTK 4.14
    does and as every machine without the export already did.
    """
    os.environ.setdefault("GSK_RENDERER", "gl")
    if os.environ["GSK_RENDERER"].strip().lower() in ("gl", "ngl", "opengl"):
        disabled = [f.strip() for f in os.environ.get("GDK_DISABLE", "").split(",") if f.strip()]
        if "dmabuf" not in disabled:
            os.environ["GDK_DISABLE"] = ",".join(disabled + ["dmabuf"])


def avoid_the_explicit_sync_leak():
    """NVIDIA's Wayland driver keeps a small allocation for every frame it presents while explicit
    sync is on: on the operator's desktop the wallpaper grew by about 0.9 MiB a minute (two screens
    at 30 fps), in either host, and only while it drew; on Mesa it stays flat. With explicit sync
    off the driver falls back to implicit sync, which does not leak; __GL_YIELD=USLEEP lets the
    driver sleep while it waits for a frame there, rather than spin. Both are NVIDIA's own
    variables, which other drivers ignore; a value the user set wins. Set before GTK starts and
    before the native wallpaper, which inherits them through execve."""
    os.environ.setdefault("__NV_DISABLE_EXPLICIT_SYNC", "1")
    os.environ.setdefault("__GL_YIELD", "USLEEP")


def _libc_function(name):
    """A glibc function by name, or None (another C library, or none of that name)."""
    try:
        return getattr(ctypes.CDLL(None), name)
    except (OSError, AttributeError):
        return None


#: How often freed memory goes back to the system while syncrain runs.
TRIM_SECONDS = 300


def settle_memory():
    """After startup (and after the screens changed): give back what starting left behind.

    Starting leaves garbage and freed memory inside the C heap: the decoded images uploaded to the
    card, the shader compiler's working space, the import machinery, the old screens' objects after
    a change. gc.collect frees what only cycles kept, and malloc_trim hands the free pages back to
    the system (glibc; elsewhere nothing happens). A frame makes no cycles, so after this the
    collector has nothing to do (none ran in 30 s of two screens at 30 fps).
    """
    gc.collect()
    trim = _libc_function("malloc_trim")
    if trim is not None:
        trim.argtypes = [ctypes.c_size_t]
        trim(0)


def resident_mib() -> float:
    """This process's resident memory (VmRSS), in MiB, or 0 where /proc does not say."""
    try:
        with open("/proc/self/status", encoding="ascii") as fh:
            return next(int(line.split()[1]) for line in fh if line.startswith("VmRSS:")) / 1024
    except (OSError, StopIteration, ValueError):
        return 0.0


def renderer_name(widget) -> str:
    """The short name of the renderer GTK draws this widget's window with."""
    native = widget.get_native()
    renderer = native.get_renderer() if native is not None else None
    if renderer is None:
        return "unknown"
    name = type(renderer).__name__.removeprefix("Gsk")      # PyGObject names it GLRenderer, C GskGLRenderer
    return {"GLRenderer": "gl", "NglRenderer": "ngl", "VulkanRenderer": "vulkan",
            "CairoRenderer": "cairo"}.get(name, name)


def debug_fps_interval() -> float:
    """SYNCRAIN_DEBUG_FPS: report the frame rate every N seconds (any non-number: every 5)."""
    value = os.environ.get("SYNCRAIN_DEBUG_FPS", "")
    if not value:
        return 0.0
    try:
        return max(0.5, float(value))
    except ValueError:
        return 5.0


DEBUG_FPS = debug_fps_interval()


def install_quit_signals(GLib, quit_callback):
    """Ctrl+C, `systemctl --user stop` and a closed terminal all end the main loop cleanly.

    PyGObject installs a SIGINT fallback that raises KeyboardInterrupt after the loop ends (the
    traceback build 2 printed on Ctrl+C) unless Python's default handler has already been
    replaced, so it is replaced first and GLib owns the signals from then on.
    """
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    def on_signal(*_):
        quit_callback()
        return GLib.SOURCE_REMOVE

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        GLib.unix_signal_add(GLib.PRIORITY_HIGH, sig, on_signal)


def main(argv=None):
    args = parse_args(argv)
    if args.list_themes:
        from .engine import load_meta
        for name, th in load_meta()["themes"].items():
            print(f"{name:10s} {th['label']}")
        return 0
    if args.write_glyphs:
        from . import glyphs
        named = args.glyphs if isinstance(args.glyphs, str) else None
        print(f"syncrain: {glyphs.write_starter(named or glyphs.default_path())}")
        return 0
    if args.check_config:
        from . import glyphs
        from .engine import DATA_DIR, load_meta
        from .renderer import compose_for, from_args
        if isinstance(args.glyphs, dict):         # the wallpaper would fall back to the preset's: say it
            meta = load_meta()
            try:                                  # counted with the words the file names, as drawn
                glyphs.resolve(meta, compose_for(meta, args), DATA_DIR, args.glyphs, str(args.config_file),
                               args.hieroglyphs)
            except glyphs.GlyphsError as e:
                print(f"syncrain: {e}", file=sys.stderr)
                return 2
        r = from_args(args)
        try:                                      # what the wallpaper makes before its first frame
            r.glyphs.words_bytes()
            if r.logo_choice != "none":
                from .logo import texture
                from .renderer import rgba_pil
                texture(r.logo_choice, r.data_dir, rgba_pil)
        except Exception as e:  # noqa: BLE001 - a picture or a word it cannot use, said as such
            print(f"syncrain: {type(e).__name__}: {e}", file=sys.stderr)
            return 2
        print(f"syncrain: {args.config_file or 'no settings file'}: preset {r.theme_name}, channel "
              f"{r.channel!r}, {len(r.glyphs.sets)} symbol sets from {r.glyphs.source}")
        return 0
    if args.write_config:
        return write_default_config(args.write_config)
    if args.write_scene:                      # for the lock screen: no window, no GTK
        try:
            return native.write_scene(args, args.write_scene)
        except Exception as e:  # noqa: BLE001 - a picture or font the scene cannot use, said as such
            print(f"syncrain: the scene could not be made ({type(e).__name__}: {e})", file=sys.stderr)
            return 1
    # Before GTK is imported: PyGObject initialises GTK on import, and GDK reads GDK_DISABLE then.
    use_gl_renderer()
    avoid_the_explicit_sync_leak()
    if args.host != "gtk" and not (args.power_sweep or args.benchmark or args.diagnose):
        if native.applies(args):
            path = native.binary()
            if path:
                why = native.run(args, sys.argv[1:] if argv is None else argv, path)   # returns only on failure
                print(f"syncrain: {why}; the GTK host draws instead", file=sys.stderr, flush=True)
            elif args.host == "native":
                print("syncrain: the native wallpaper is not built here (install.sh builds it; "
                      "`syncrain --diagnose` says what it needs)", file=sys.stderr)
                return 2                                  # a restart cannot build it
        elif args.host == "native":
            print("syncrain: the native wallpaper draws only the wallpaper on a Wayland session, paced by the "
                  "refresh; use --host gtk for X11, --window, --screenshot, --record, --video and --pacing timer",
                  file=sys.stderr)
            return 2                                      # nor change what was asked
    _preload_layer_shell()
    if args.power_sweep:
        from .power import run_sweep
        return run_sweep(args)
    if args.benchmark:
        from .bench import run_benchmark
        return run_benchmark(args)
    if args.diagnose:
        from .diagnose import run
        return run(args)

    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, GLib, Gtk

    Gtk.init()
    display = Gdk.Display.get_default()
    if display is None:
        print("syncrain: no display (run it inside your desktop session)", file=sys.stderr)
        return 1
    backend = type(display).__name__          # GdkWaylandDisplay / GdkX11Display
    from . import gl
    from .renderer import from_args as renderer_from_args

    LayerShell = None
    # a still, frames or a video are drawn in a window of their own size here: as a wallpaper, two
    # screens wrote one file twice, and GNOME (no wallpaper layer) none
    if "Wayland" in backend and not (args.window or args.record or args.video or args.screenshot):
        try:
            gi.require_version("Gtk4LayerShell", "1.0")
            from gi.repository import Gtk4LayerShell as LayerShell
            if not LayerShell.is_supported():
                LayerShell = None
        except (ValueError, ImportError, GLib.Error):  # GLib.Error: a typelib without its library
            LayerShell = None
        if LayerShell is None:
            print("syncrain: this Wayland compositor has no wlr-layer-shell support (GNOME?). "
                  "Use --window, or the web version, index.html at the top of the syncrain folder.", file=sys.stderr)
            return EXIT_NO_LAYER

    # Until the first frame, and if OpenGL never comes, a window shows its theme background:
    # black, not the light grey a GTK window is by default.
    css = Gtk.CssProvider()
    rule = "window.syncrain { background-color: #000000; }"
    if hasattr(css, "load_from_string"):
        css.load_from_string(rule)
    else:
        css.load_from_data(rule.encode())
    add_provider = getattr(Gtk, "style_context_add_provider_for_display", None) \
        or Gtk.StyleContext.add_provider_for_display
    add_provider(display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    from .pacing import Pacer, spacing, steady

    class RainArea(Gtk.GLArea):
        def __init__(self, rects=None, screens=()):
            super().__init__()
            self.rects = rects                 # callable(width, height) -> [(x, y, w, h)] device px, or None
            self.screens = tuple(screens)      # connector names of the screens it shows (none: a window)
            self.renderer = None
            self.pacer = Pacer(args.fps)
            self.hidden = False                # every screen it shows is covered: nothing is drawn
            self._due = None                   # the GLib source that asks for the next frame
            self._drawn_for = 0                # the monotonic moment the frame being drawn is drawn for
            self.frames = 0                    # frames drawn since it was realized
            self._drawn = []                   # (GTK frame counter, target, drawn for) until GTK knows when shown
            self._shown = []                   # SYNCRAIN_DEBUG_FPS: (when shown, refresh interval, drawn for)
            # No set_required_version: see gl_context_problem. GTK's own minimums are GL 3.3 core
            # and GLES 3.0, exactly what the shaders need.
            self.set_has_depth_buffer(False)
            self.set_has_stencil_buffer(False)
            self.set_auto_render(False)
            self.connect("realize", self._realize)
            self.connect("unrealize", self._unrealize)
            self.connect("resize", self._resize)
            self.connect("render", self._render)
            self._off = {}                     # (w, h) -> (framebuffer, texture) for --scale
            self.fb = None

        def _resize(self, _area, w, h):            # framebuffer size in device pixels
            self.fb = (int(w), int(h))

        def _realize(self, _area):
            self.make_current()
            if self.get_error() is not None:
                app.fail(f"OpenGL is not available: {self.get_error().message}")
                return
            ctx = self.get_context()
            use_es, problem = gl_context_problem(ctx, Gdk)
            if problem:
                app.fail(problem)
                return
            try:
                r = renderer_from_args(args)
                r.init(use_es)
            except RuntimeError as e:          # a shader this driver will not compile
                app.fail(f"the shaders did not compile here: {e}")
                return
            except Exception as e:  # noqa: BLE001 - a picture, a font or a symbols file it cannot use
                if type(e).__module__.startswith("OpenGL"):  # the driver's, not a setting's
                    app.fail(f"OpenGL failed while getting ready: {e}")
                else:
                    app.fail(f"the picture could not be made ready: {type(e).__name__}: {e}", code=EXIT_CONFIG)
                return
            self.renderer = r
            app.started(describe_context(ctx, Gdk) + f", GTK renderer {renderer_name(self)}")

        def _unrealize(self, _area):
            """The area is going (the screens changed, or the app stops): delete what was made for
            its context. Textures belong to every context GTK shares objects between, so they would
            outlive this one; the programs and textures every screen reads stay for the next one."""
            if self.renderer is None and not self._off:
                return
            self.make_current()
            # make_current does not say when it fails, and framebuffers and vertex arrays are each
            # context's own: delete only with this area's context current, never in GTK's.
            ctx = self.get_context()
            if self.get_error() is None and ctx is not None and Gdk.GLContext.get_current() == ctx:
                if self.renderer is not None:
                    self.renderer.release()
                gl.delete_framebuffers([fbo for fbo, _tex in self._off.values()])
                gl.delete_textures([tex for _fbo, tex in self._off.values()])
            self._off = {}
            self.renderer = None

        def _offscreen(self, w, h, keep=2):        # one reduced-size target per viewport size (--scale)
            if (w, h) in self._off:
                self._off[(w, h)] = self._off.pop((w, h))      # the latest used last
            else:
                # a window resized again and again keeps the sizes it uses last (one per monitor it
                # covers, at least two), not every size it ever had (each a texture on the card)
                while len(self._off) >= keep:
                    old_fbo, old_tex = self._off.pop(next(iter(self._off)))
                    gl.delete_framebuffers([old_fbo])
                    gl.delete_textures([old_tex])
                fbo, tex = gl.gen_framebuffer(), gl.gen_texture()
                gl.glBindTexture(gl.GL_TEXTURE_2D, tex)
                gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, w, h, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
                gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, tex, 0)
                self._off[(w, h)] = (fbo, tex)
            return self._off[(w, h)][0]

        def _moment(self):
            """The stream time this frame is drawn for: the refresh it will be shown on, when known."""
            now = GLib.get_monotonic_time()
            self._drawn_for = self.pacer.target if self.pacer.target is not None else now
            if args.time is not None:
                return args.time
            return time.time() + args.offset + (self._drawn_for - now) / 1e6

        def _schedule(self):
            """Ask for the next frame at the time the pacer gives (syncrain/pacing.py)."""
            if self._due is not None:
                GLib.source_remove(self._due)
                self._due = None
            if self.hidden or args.pacing == "timer":     # timer: App.tick asks, as in build 4
                return
            now = GLib.get_monotonic_time()
            refresh = vblank = 0
            clock = self.get_frame_clock()
            if clock is not None:
                refresh, vblank = clock.get_refresh_info(now)
            delay, _target = self.pacer.plan(now, refresh, vblank)
            self._due = GLib.timeout_add(max(1, int(delay // 1000)), self._on_due, priority=GLib.PRIORITY_HIGH)

        def _on_due(self):
            self._due = None
            if not self.hidden:
                self.queue_render()
            return GLib.SOURCE_REMOVE

        def set_hidden(self, value):
            """Covered: stop asking for frames. Shown again: draw at once, then on the cadence."""
            if value == self.hidden:
                return
            self.hidden = value
            if DEBUG_FPS:
                what = "covered, drawing stops" if value else "shown again, drawing resumes"
                print(f"syncrain: {', '.join(self.screens)} {what}", flush=True)
            if value:
                if self._due is not None:
                    GLib.source_remove(self._due)
                    self._due = None
            else:
                self.pacer.restart()
                self._frames, self._since = 0, time.monotonic()    # the next report counts from now
                self._drawn, self._shown = [], []
                self.queue_render()

        def retire(self):
            """The monitors changed and this area is being replaced: ask for no more frames."""
            self.hidden = True
            if self._due is not None:
                GLib.source_remove(self._due)
                self._due = None

        def _note_presented(self):
            """When GTK learns when a drawn frame was shown, tell the pacer whether it made its refresh
            (`Pacer.shown`), and keep it for the SYNCRAIN_DEBUG_FPS report. GTK holds 16 frames' timings."""
            clock = self.get_frame_clock()
            if clock is None:
                return
            waiting = []
            for counter, target, drawn_for in self._drawn:
                timings = clock.get_timings(counter)
                if timings is None:
                    continue
                if not timings.get_complete():
                    waiting.append((counter, target, drawn_for))
                    continue
                shown, refresh = timings.get_presentation_time(), timings.get_refresh_interval()
                if shown > 0:
                    if target is not None:
                        self.pacer.shown(target, shown, refresh)
                    if DEBUG_FPS:
                        self._shown.append((shown, refresh, drawn_for))
            self._drawn = waiting + [(clock.get_frame_counter(), self.pacer.target, self._drawn_for)]

        def _timing(self):
            """', spacing 2 refreshes 100%, steady 100%, lead 14.3 ms': of the frames shown since the last
            report, how many came the expected number of refreshes after the one before, how many were
            shown the usual delay after the moment they were drawn for (syncrain/pacing.py, steady), and
            how long before its refresh a frame is now asked for."""
            shown, self._shown = self._shown, self._shown[-1:]
            refresh = shown[-1][1] if shown else 0
            steps = spacing([p for p, _, _ in shown], refresh)
            if len(steps) < 2 or refresh <= 0:
                return ""
            n = self.pacer.step(refresh)
            even = 100.0 * sum(1 for s in steps if s == n) / len(steps)
            calm = 100.0 * steady([p - drawn_for for p, _, drawn_for in shown[1:]])
            return (f", spacing {n} refresh{'es' if n != 1 else ''} {even:.0f}%, steady {calm:.0f}%, "
                    f"lead {self.pacer.lead(refresh) / 1000:.1f} ms")

        def _render(self, _area, _ctx):
            if self.renderer is None:
                return False
            try:
                return self._draw()
            finally:
                # The next frame is asked for whatever happened to this one (a frame that raised
                # is reported by PyGObject and the wallpaper goes on), except after --screenshot
                # and --record, which end the app.
                if self.renderer is not None:
                    self._schedule()

        def _screen_pixels(self, W: int, H: int):
            """The screen's own pixels under this area, where the framebuffer (W x H) has more: at a
            fractional scale (GTK 4.12 on says it, gdk_surface_get_scale) GtkGLArea's follows the
            next whole one. None at a whole scale, where GTK cannot say, or where the framebuffer
            already has the screen's pixels. A still or a record keeps the framebuffer's: their
            files are its size, and the scale may not be known yet at the first frame."""
            if args.screenshot or args.record or self.rects:
                return None
            try:
                exact = self.get_native().get_surface().get_scale()
            except (AttributeError, TypeError):
                return None
            # rounded as the native wallpaper rounds a fractional scale's size (wallpaper.c)
            sw, sh = int(self.get_width() * exact + 0.5), int(self.get_height() * exact + 0.5)
            return (sw, sh) if 0 < sw < W and 0 < sh <= H else None

        def _draw(self):
            if self.fb:                              # GLArea does not reset the viewport between frames
                W, H = self.fb
            else:
                s = self.get_scale_factor()
                W, H = self.get_width() * s, self.get_height() * s
            if W <= 0 or H <= 0:
                return False
            out = gl.get_integer(gl.GL_FRAMEBUFFER_BINDING)
            t = self._moment()
            areas = self.rects(W, H) if self.rects else [(0, 0, W, H)]
            # At a fractional scale (1.25) GtkGLArea's framebuffer has the next whole scale's pixels and
            # the compositor shrinks it to the screen's: the frame is drawn at the screen's own pixels,
            # the grid the native wallpaper draws there, and each pixel of it blown up whole
            screen = self._screen_pixels(W, H)
            scale = min(args.scale, 1.0)             # above 1 draws as 1 does, on both hosts
            for (x, y, w, h) in areas:
                if scale < 0.999 or screen:
                    bw, bh = screen or (w, h)
                    sw, sh = (bw, bh) if scale >= 0.999 else (max(64, round(bw * scale)), max(36, round(bh * scale)))
                    off = self._offscreen(sw, sh, keep=max(2, len(areas)))
                    # drawn into fewer pixels: the grid is still the screen's (engine.geometry)
                    self.renderer.cell_scale = scale
                    try:
                        self.renderer.render(t, off, 0, 0, sw, sh)
                    finally:
                        self.renderer.cell_scale = 1.0
                    gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, off)
                    gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, out)
                    # nearest at the screen's pixels: the compositor's shrinking then lands on them
                    # (linear here and there again would soften it twice); --scale's is softer anyway
                    gl.glBlitFramebuffer(0, 0, sw, sh, x, y, x + w, y + h, gl.GL_COLOR_BUFFER_BIT,
                                         gl.GL_LINEAR if scale < 0.999 else gl.GL_NEAREST)
                    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, out)
                else:
                    self.renderer.render(t, out, x, y, w, h)
            self._note_presented()
            self.frames += 1
            if self.frames == 1:
                app.settle_soon()
            if DEBUG_FPS:
                now = time.monotonic()
                self._frames = getattr(self, "_frames", 0) + 1
                if now - getattr(self, "_since", now) >= DEBUG_FPS:
                    print(f"syncrain: {self._frames / (now - self._since):.1f} fps at {W}x{H} "
                          f"(area {app.areas.index(self) if self in app.areas else 0}){self._timing()}",
                          flush=True)
                    self._frames, self._since = 0, now
                elif not hasattr(self, "_since"):
                    self._since = now
            if args.video:
                # a slice of the video each frame, so the window goes on answering its compositor (a
                # window that does not is offered to be killed) and Ctrl+C is heard
                try:
                    if not self._video():
                        return True
                except (OSError, ValueError, RuntimeError) as e:     # a folder it cannot write, ffmpeg's no
                    print(f"\nsyncrain: not saved: {e}", file=sys.stderr, flush=True)
                    app.exit_code = app.exit_code or 1
                except Exception as e:  # noqa: BLE001 - anything else ends this video too, said, not again each frame
                    print(f"\nsyncrain: not saved: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
                    app.exit_code = app.exit_code or 1
                if app.video is not None:            # stopped part way: no half video left behind
                    try:
                        app.video.abort()
                    except Exception:  # noqa: BLE001
                        pass
                    app.video = None
                self.renderer = None                 # one video only; then out
                GLib.idle_add(app.quit, priority=GLib.PRIORITY_HIGH)
            elif args.screenshot or args.record:
                try:
                    if args.screenshot:
                        self._save(out, W, H, args.screenshot)
                        print(f"syncrain: saved {args.screenshot} ({W}x{H})", flush=True)
                    else:
                        os.makedirs(args.record, exist_ok=True)
                        n = max(1, round(args.record_seconds * args.record_fps))
                        t0 = args.time if args.time is not None else time.time() + args.offset
                        for i in range(n):
                            self.renderer.render(t0 + i / args.record_fps, out, 0, 0, W, H)
                            self._save(out, W, H, os.path.join(args.record, f"frame_{i:05d}.png"))
                        print(f"syncrain: recorded {n} frames ({W}x{H}) into {args.record}", flush=True)
                except (OSError, ValueError, KeyError) as e:   # a folder it cannot write, a name with no type
                    print(f"syncrain: not saved: {e}", file=sys.stderr, flush=True)
                    app.exit_code = app.exit_code or 1
                self.renderer = None                 # one frame, or one clip, only; then out
                GLib.idle_add(app.quit, priority=GLib.PRIORITY_HIGH)
            return True

        def _video(self) -> bool:
            """--video: frames drawn off the screen at the video's size, read back and handed to ffmpeg,
            for a tenth of a second at a time; True once the video is saved."""
            from . import video
            w, h = args.video_size
            if app.video is None:
                limit = gl.get_integer(gl.GL_MAX_TEXTURE_SIZE)
                if w > limit or h > limit:
                    raise ValueError(f"this graphics card draws at most {limit}x{limit}: {w}x{h}")
                off = self._offscreen(w, h)
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, off)
                if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
                    raise ValueError(f"this graphics card cannot draw {w}x{h} off the screen")
                t0 = args.time if args.time is not None else time.time() + args.offset

                def draw(t):
                    self.renderer.render(t, off, 0, 0, w, h)
                    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, off)
                    return gl.read_pixels(0, 0, w, h)
                app.video = video.Writer(args.video, w, h, args.video_fps,
                                         video.plan(args.seconds, args.video_fps, t0), draw)
            writer, until = app.video, time.monotonic() + 0.1
            while time.monotonic() < until:
                if writer.step():
                    app.video = None
                    if sys.stderr.isatty():
                        print(file=sys.stderr)
                    print(f"syncrain: saved {args.video} ({w}x{h}, {writer.done} frames at {args.video_fps:g} "
                          "fps)", flush=True)
                    return True
            if sys.stderr.isatty():
                video.progress_line(writer.done, len(writer.frames))
            return False

        @staticmethod
        def _save(fbo, W, H, path):
            from PIL import Image
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
            data = gl.read_pixels(0, 0, W, H)
            Image.frombytes("RGBA", (W, H), data).transpose(Image.FLIP_TOP_BOTTOM).convert("RGB").save(path)

    layer_name = args.layer or ("bottom" if "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "") else "background")

    class App(Gtk.Application):
        def __init__(self):
            super().__init__(application_id=None)
            self.windows, self.areas = [], []
            self.exit_code = 0
            self.announced = False
            self.screens = 0
            self.watch = None
            self.watch_said = False
            self._settle = None                # the GLib source that will settle memory, while it waits
            self._rebuild = None               # the GLib source that will rebuild the screens, while it waits
            self.settled = False               # memory settled since the screens were last built
            self.video = None                  # --video's syncrain.video.Writer, while it is being made

        def do_activate(self):
            self.hold()
            self.build()
            # a screen plugged in or out rebuilds the wallpaper's windows; a one-shot window (a still,
            # frames, a video) keeps its own: rebuilt, it lost the renderer its video was drawing with
            if not (args.video or args.screenshot or args.record):
                display.get_monitors().connect("items-changed", lambda *_: self.rebuild_soon())
            if args.pacing == "timer":
                GLib.timeout_add(max(1, int(round(1000.0 / max(1.0, args.fps)))), self.tick)
            self.start_watch()

        def tick(self):
            """--pacing timer: build 4's frame timing, a frame asked of every screen every 1/fps seconds."""
            for a in self.areas:
                if not a.hidden:
                    a.queue_render()
            return GLib.SOURCE_CONTINUE

        def start_watch(self):
            """On KDE Plasma, ask KWin which screens a window covers (syncrain/hidden.py)."""
            if args.pause_under == "never" or LayerShell is None or self.screens == 0:
                return
            watch = hidden.Watch(self.update_hidden, maximized=args.pause_under == "maximized")
            why = watch.start()
            if why is None:
                self.watch = watch
                GLib.timeout_add(1500, self._watch_check, False)
            elif "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "") or "not on the session bus" not in why:
                print(f"syncrain: {why}; drawing goes on under covering windows", flush=True)

        def _watch_check(self, retried):
            """No answer 1.5 s after the script was run: ask KWin to start it once more (hidden.Watch.retry);
            still none 1.5 s later: give up and draw as before."""
            if self.watch is None or self.watch.answered:
                return GLib.SOURCE_REMOVE
            if not retried:
                self.watch.retry()
                GLib.timeout_add(1500, self._watch_check, True)
                return GLib.SOURCE_REMOVE
            print("syncrain: KWin loaded the script but it reported nothing (KWin 5?); "
                  "drawing goes on under covering windows", flush=True)
            self.watch.stop()
            self.watch = None
            self.update_hidden()
            return GLib.SOURCE_REMOVE

        def update_hidden(self):
            if self.watch is not None and self.watch.answered and not self.watch_said:
                self.watch_said = True
                which = "maximized and full-screen" if args.pause_under == "maximized" else "full-screen"
                print(f"syncrain: drawing pauses on a screen under {which} windows (KWin)", flush=True)
            for a in self.areas:
                a.set_hidden(self.watch.hidden(a.screens) if self.watch is not None else False)

        def stop_watch(self):
            if self.watch is not None:
                self.watch.stop()
                self.watch = None

        def settle_soon(self):
            """Once every screen has drawn its first frame, startup is over: settle_memory, once."""
            if self._settle is None and not self.settled and self.areas and all(a.frames for a in self.areas):
                self._settle = GLib.timeout_add(500, self._settle_now)

        def _settle_now(self):
            self._settle = None
            self.settled = True
            settle_memory()
            if DEBUG_FPS:
                print(f"syncrain: memory handed back after the first frames ({resident_mib():.0f} MiB resident)",
                      flush=True)
            if not getattr(self, "_trimming", None):     # and again every five minutes, as the native one does
                self._trimming = GLib.timeout_add_seconds(TRIM_SECONDS, self._trim)
            return GLib.SOURCE_REMOVE

        @staticmethod
        def _trim():
            settle_memory()
            return GLib.SOURCE_CONTINUE

        def started(self, context):
            """One line when the first viewport is up: what draws, where (it lands in the journal)."""
            if not self.announced:
                self.announced = True
                n = self.screens
                where = "a window" if n == 0 else f"{n} screen{'s' if n != 1 else ''}"
                print(f"{build.describe()}: {context}, {where}", flush=True)

        def fail(self, reason, code=EXIT_NO_GL):
            """Give the desktop back at once and exit with `code` (a status the services do not
            restart on); said once, not once per screen."""
            if self.exit_code == 0:
                self.exit_code = code
                print(f"syncrain: {reason}\n"
                      "syncrain: nothing can be drawn, so the wallpaper is closed again. "
                      "`syncrain --diagnose` shows what this machine offers.", file=sys.stderr, flush=True)
            for w in self.windows:
                w.set_visible(False)
            GLib.idle_add(self.quit, priority=GLib.PRIORITY_HIGH)

        def rebuild_soon(self):
            """One rebuild for a burst of screen changes, at default priority: an idle one waits behind
            the frames (their timers run at high priority) for as long as drawing keeps the loop
            busy, which on slow OpenGL is for good."""
            if self._rebuild is None:
                self._rebuild = GLib.timeout_add(50, self.rebuild, priority=GLib.PRIORITY_DEFAULT)

        def rebuild(self):
            self._rebuild = None
            for a in self.areas:
                a.retire()
            for w in self.windows:
                w.destroy()
            self.windows, self.areas = [], []
            if self._settle is not None:
                GLib.source_remove(self._settle)
                self._settle = None
            self.settled = False                       # settle again once the new screens have drawn
            self.build()
            self.update_hidden()
            return False

        def build(self):
            monitors = [display.get_monitors().get_item(i) for i in range(display.get_monitors().get_n_items())]
            # a still on Wayland is drawn in a window (as layers, two screens wrote one file twice and
            # GNOME none); on X11 the wallpaper is one window over every screen, and its still is the desktop
            windowed = (args.window or args.record or args.video
                        or (args.screenshot and ("Wayland" in backend or not monitors)))
            self.screens = 0 if windowed else len(monitors)
            if windowed:
                # a video is drawn at its own size off the screen: its window only gives the drawing a context
                w, h = (320, 180) if args.video else (int(v) for v in (args.size or "1280x720").lower().split("x"))
                self.add_window(Gtk.Window(application=self), RainArea(), size=(w, h))
            elif LayerShell is not None:
                layer = LayerShell.Layer.BOTTOM if layer_name == "bottom" else LayerShell.Layer.BACKGROUND
                for mon in monitors:
                    win = Gtk.Window(application=self)
                    LayerShell.init_for_window(win)
                    LayerShell.set_namespace(win, "syncrain")
                    LayerShell.set_layer(win, layer)
                    LayerShell.set_monitor(win, mon)
                    for edge in (LayerShell.Edge.LEFT, LayerShell.Edge.RIGHT, LayerShell.Edge.TOP, LayerShell.Edge.BOTTOM):
                        LayerShell.set_anchor(win, edge, True)
                    LayerShell.set_exclusive_zone(win, -1)
                    LayerShell.set_keyboard_mode(win, LayerShell.KeyboardMode.NONE)
                    connector = mon.get_connector()
                    self.add_window(win, RainArea(screens=(connector,) if connector else ()), click_through=True)
            else:                               # X11: one desktop window, one viewport per monitor
                geos = [m.get_geometry() for m in monitors] or [None]
                if geos[0] is None:
                    self.add_window(Gtk.Window(application=self), RainArea(), size=(1280, 720))
                    return
                x0 = min(g.x for g in geos); y0 = min(g.y for g in geos)
                bw = max(g.x + g.width for g in geos) - x0; bh = max(g.y + g.height for g in geos) - y0

                def rects(W, H, geos=geos, x0=x0, y0=y0, bw=bw, bh=bh):
                    sx, sy = W / bw, H / bh
                    return [(round((g.x - x0) * sx), round((bh - (g.y - y0) - g.height) * sy),
                             round(g.width * sx), round(g.height * sy)) for g in geos]
                win = Gtk.Window(application=self)
                self.add_window(win, RainArea(rects), size=(bw, bh), x11=True)

        def add_window(self, win, area, size=None, x11=False, click_through=False):
            win.add_css_class("syncrain")
            win.set_decorated(args.window)
            win.set_title("syncrain")
            if size:
                win.set_default_size(*size)
            win.set_child(area)
            if x11 and not args.window:
                win.realize()
                gi.require_version("GdkX11", "4.0")
                from gi.repository import GdkX11
                xid = GdkX11.X11Surface.get_xid(win.get_surface())
                _x11_desktop_hints(xid)
                win.connect("map", lambda *_: _x11_desktop_hints(xid))
            self.windows.append(win)
            self.areas.append(area)
            win.present()
            if click_through:                    # clicks pass through to whatever is underneath (Plasma's desktop)
                try:
                    import cairo
                    win.get_surface().set_input_region(cairo.Region())
                except Exception as e:  # noqa: BLE001 - cosmetic, never fatal
                    print(f"syncrain: could not make the wallpaper click-through: {e}", file=sys.stderr)

    app = App()
    install_quit_signals(GLib, app.quit)
    try:
        rc = app.run([])
    finally:
        app.stop_watch()                         # the script leaves KWin with us
        if app.video is not None:                # stopped (Ctrl+C) before it was whole: nothing kept
            app.video.abort()
            print(f"\nsyncrain: {args.video} not made (stopped)", file=sys.stderr)
            app.exit_code = app.exit_code or 1
    return app.exit_code or rc
