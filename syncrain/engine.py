"""Host-side pieces of the engine that must match the web runner bit for bit.

Everything random happens on the GPU from integer hashes; the host only provides
  * the time, split into whole seconds since EPOCH0 and the fraction of the second,
  * the channel seed (32-bit FNV-1a of the channel name, UTF-8),
  * static tables (glyph lookup, words, theme colours) from themes.json.
"""
import json
import math
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


THEMES_CONTRACT = "syncrain-themes-1"


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


def motion(theme, rainbow=None, spin=None, drift=None):
    """Anti burn-in motion for a theme: logo spin, rainbow cycles and drift (shader uniforms).
    rainbow: 'logo' (logo colours cycle), 'all' (the rain cycles too) or 'off'."""
    logo, rain = theme["logo"], theme["rain"]
    mode = rainbow or rain.get("rainbow", "logo")
    return {
        "uSpinCph": cycles_per_hour(logo.get("spin", 0) if spin is None else spin),
        "uLogoHueCph": cycles_per_hour(logo.get("hueCycle", 0)) if mode in ("logo", "all") else 0.0,
        "uRainHueCph": cycles_per_hour(rain.get("allHueCycle", 0)) if mode == "all" else 0.0,
        "uDrift": float(logo.get("drift", 0.0) if drift is None else drift),
    }


def lut_bytes(theme) -> bytes:
    out = bytearray(256 * 4)
    for i, g in enumerate(theme["lut"]):
        out[i * 4] = g
        out[i * 4 + 3] = 255
    return bytes(out)


def words_bytes(theme):
    words = theme["words"]
    n = max(1, len(words))
    out = bytearray([255]) * (16 * n * 4)
    for row, w in enumerate(words):
        for i, g in enumerate(w[:16]):
            out[(row * 16 + i) * 4] = g
    return bytes(out), n
