"""Host-side pieces of the engine that must match the web runner bit for bit.

Everything random happens on the GPU from integer hashes; the host only provides
  * the time, split into whole seconds since EPOCH0 and the fraction of the second,
  * the channel seed (32-bit FNV-1a of the channel name, UTF-8),
  * static tables (glyph lookup, words, colours) from themes.json, whose presets ("themes") are
    where the settings start (`compose`).
"""
import json
import math
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


THEMES_CONTRACT = "syncrain-themes-3"


def load_meta(data_dir=DATA_DIR):
    with open(os.path.join(data_dir, "themes.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    if meta.get("contract") != THEMES_CONTRACT:
        raise RuntimeError(f"themes.json is {meta.get('contract')!r}, this code reads {THEMES_CONTRACT!r}")
    return meta


def channel_seed(name: str) -> int:
    h = 0x811C9DC5
    for b in name.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def split_time(unix_seconds: float, epoch0: int):
    """(whole seconds since epoch0 as uint32, fraction of the second), same as the web runner."""
    ms = math.floor(unix_seconds * 1000.0 + 1e-6)       # millisecond grid, like Date.now()
    whole = ms // 1000
    return (whole - epoch0) & 0xFFFFFFFF, (ms - whole * 1000) / 1000.0


def grid_rows(width: int, height: int, cols: int) -> int:
    return math.ceil(height / (width / cols))


def cover_fit(screen_w, screen_h, img_w, img_h):
    """uv transform so an image covers the screen without distortion: uv = screen_uv * scale + offset."""
    sa, ia = screen_w / screen_h, img_w / img_h
    if sa > ia:
        k = ia / sa
        return (1.0, k), (0.0, 0.5 - 0.5 * k)
    k = sa / ia
    return (k, 1.0), (0.5 - 0.5 * k, 0.0)


def cycles_per_hour(seconds) -> float:
    """Whole cycles per hour for a period in seconds (0 or less: off), so the motion has no seam at the hour."""
    if not seconds or seconds <= 0:
        return 0.0
    return float(max(1, round(3600.0 / seconds)))


#: The settings `compose` puts over a preset, by their command-line names (the options' dests).
LOOK_OPTIONS = ("rain_colors", "glow_color", "background_colors", "vignette", "logo_size", "logo_cycle", "cycle",
                "flavours", "flavour_layout", "words")

#: What --rainbow all cycles the rain at, in seconds a turn of the hue wheel, so a setting that
#: names it keeps the picture it had.
ALL_CYCLE = 600


def colour(value):
    """A colour as the settings give it: "#rrggbb" (each channel c/255, to 4 places, as the presets
    are written) or three numbers 0 to 1. ValueError if it is neither."""
    if isinstance(value, str):
        h = value.strip()
        if len(h) == 7 and h[0] == "#":
            try:
                return [round(int(h[i:i + 2], 16) / 255, 4) for i in (1, 3, 5)]
            except ValueError:
                pass
        raise ValueError(f"not a colour: {value!r} (#rrggbb)")
    if isinstance(value, (list, tuple)) and len(value) == 3 and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1 for v in value):
        return [float(v) for v in value]
    raise ValueError(f"not a colour: {value!r} (#rrggbb, or three numbers 0 to 1)")


def compose(meta, preset="nixos", rainbow=None, rain_colors=None, glow_color=None, background_colors=None,
            vignette=None, logo_size=None, logo_cycle=None, cycle=None, flavours=None, flavour_layout=None,
            words=None):
    """The look a frame is drawn with: a preset (themes.json's "themes") with the settings over it.
    The page does the same (`composeLook` in index.html)."""
    th = json.loads(json.dumps(meta["themes"][preset]))
    if rainbow == "off":
        th["logo"]["hueCycle"] = 0
    elif rainbow == "all":
        th["rain"]["cycle"] = ALL_CYCLE
    if logo_cycle is not None:
        th["logo"]["hueCycle"] = logo_cycle
    if cycle is not None:
        th["rain"]["cycle"] = cycle
    if rain_colors is not None:
        for key, value in zip(("deep", "mid", "pale", "head"), rain_colors):
            th["colors"][key] = colour(value)
    if glow_color is not None:
        th["colors"]["glow"] = colour(glow_color)
    if background_colors is not None:
        for key, value in zip(("top", "bottom", "center"), background_colors):
            th["background"][key] = colour(value)
    if vignette is not None:
        th["background"]["vignette"] = float(vignette)
    if logo_size is not None:
        th["logo"]["size"] = float(logo_size)
    if flavours is not None:
        th["rain"]["flavours"] = int(flavours)
    if flavour_layout is not None:
        th["rain"]["flavourLayout"] = flavour_layout
    if words is not None:
        th["wordText"] = list(words)
    return th


def motion(theme, spin=None, drift=None):
    """Anti burn-in motion for a look: logo spin, colour cycles and drift (shader uniforms)."""
    logo, rain = theme["logo"], theme["rain"]
    return {
        "uSpinCph": cycles_per_hour(logo.get("spin", 0) if spin is None else spin),
        "uLogoHueCph": cycles_per_hour(logo.get("hueCycle", 0)),
        "uRainHueCph": cycles_per_hour(rain.get("cycle", 0)),
        "uDrift": float(logo.get("drift", 0.0) if drift is None else drift),
    }


#: Each picture option's range, and what the preset says when the option is not given.
LOOK = {"speed": (0.25, 4.0), "density": (0.0, 2.3), "glow": (0.0, 2.0), "bloom": (0.0, 2.0),
        "hieroglyphs": (0.0, 1.0)}


def look(theme, speed=None, density=None, snow=None, glow=None, bloom=None, hieroglyphs=None):
    """The picture options as multipliers of the preset's own values (1: as the preset has it), the
    share of hieroglyphs among the changing glyphs (None: as the symbol sets say), and whether the
    snow falls."""
    given = dict(speed=speed, density=density, glow=glow, bloom=bloom, hieroglyphs=hieroglyphs)
    out = {}
    for key, value in given.items():
        lo, hi = LOOK[key]
        if value is None:
            if key == "hieroglyphs":          # the sets' own share (syncrain/glyphs.py)
                out[key] = None
                continue
            value = 1.0
        out[key] = float(min(hi, max(lo, value)))
    if snow is None:                          # as the preset has it
        out["snow"] = bool(theme.get("snowDefault", True))
    else:
        out["snow"] = snow if isinstance(snow, bool) else snow != "off"
    return out
