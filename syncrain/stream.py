"""What decides the stream besides the data it is drawn from: what the code computes, not how it is
written. For every preset, with its own settings and with settings that change it (colours, cycles,
the logo, words, motion and the look at their ends), the scene the native wallpaper is given (the
shaders as assembled, every texture, every fixed uniform, the logo's place: what all three hosts
draw from); the grid at screen sizes and --scale; the clock; channel seeds; a picture's fit.

Computing that takes seconds, so it is written down once, on purpose (`tools/stream_freeze.py
--write`), into data/stream-reference.json, one of the stream's files: the stream id stays a hash of
files, read at every start for nothing, and the gate computes it again and names the part that moved.
"""
from __future__ import annotations

import hashlib
import json

#: Screens of the shapes people have, and the corners (a phone, a tall screen, an ultrawide).
SIZES = ((3840, 2160), (2560, 1440), (1920, 1080), (1680, 1050), (1366, 768), (1280, 720), (800, 450),
         (390, 844), (1080, 1920), (3440, 1440), (5120, 1440), (150, 100))
#: --scale: 1, and below it (drawn into fewer pixels, at least 64 x 36 as every host draws).
SCALES = (1.0, 0.5, 0.3, 0.25)
#: Moments: the epoch, a known one, a fraction, the millisecond grid's edges, 2038, and after.
MOMENTS = (0.0, 1791331207.0, 1791331207.5, 1791331207.0333333, 1700000000.999, 2147483647.999, 3e9 + 0.001)
PERIODS = (0, 5, 10, 37.5, 440, 600, 3600, 86400)
CHANNELS = ("public", "friends", "été", "", "a" * 64)
FITS = ((1920, 1080, 3840, 2160), (1920, 1080, 1000, 1500), (1080, 1920, 1920, 1080), (1, 1, 1, 1))
#: Settings over each preset that change what is drawn, as the command line gives them.
SETTINGS = {
    "own": [],
    "rainbow-all": ["--rainbow", "all"],
    "rainbow-off": ["--rainbow", "off"],
    "colours": ["--rain-colors", "#202040,#8040c0,0.9/0.7/1,#ffffff", "--glow-color", "#6030a0",
                "--background-colors", "#050008,#0a0010,#200838", "--vignette", "0.2", "--logo-color", "#ffaa33"],
    "flavours": ["--flavours", "9", "--flavour-layout", "wave", "--cycle", "30"],
    "logo": ["--logo", "none"],
    "motion": ["--spin", "-15", "--drift", "0.1", "--logo-size", "0.3", "--logo-cycle", "0"],
    "look-low": ["--speed", "0.25", "--density", "0", "--glow", "0", "--bloom", "0", "--bg-gain", "0",
                 "--snow", "off", "--hieroglyphs", "0"],
    "look-high": ["--speed", "4", "--density", "2.3", "--glow", "2", "--bloom", "2", "--bg-gain", "1",
                  "--snow", "on", "--hieroglyphs", "1"],
    "words": ["--words", "HELLO,SYNC ME"],
}
#: Scene lines that say nothing about the picture: which build wrote it, and the script that tells
#: the wallpaper when it is covered.
NOT_PICTURE = (b"describe ", b"kwin-script ")


def _digest(value) -> str:
    # no default=: a value json cannot write exactly (a set, an object's repr) is an error, never
    # something that differs from process to process
    text = json.dumps(value, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def _scene_digest(data: bytes) -> str:
    end = data.index(b"\nend\n") + len(b"\nend\n")
    header = b"\n".join(line for line in data[:end].split(b"\n") if not line.startswith(NOT_PICTURE))
    return hashlib.sha256(header + data[end:]).hexdigest()


def reference() -> dict[str, str]:
    """{part: sha256 of its values}, from this tree's code and data. Seconds: tools only."""
    from . import engine, native
    from .app import parse_args
    from .renderer import from_args, geometry
    meta = engine.load_meta()
    cols, epoch0 = meta["cols"], meta["epoch0"]
    parts = {
        "clock": _digest([[t, list(engine.split_time(t, epoch0))] for t in MOMENTS]
                         + [[p, engine.cycles_per_hour(p)] for p in PERIODS]),
        "seed": _digest([[c, engine.channel_seed(c)] for c in CHANNELS]),
        "fit": _digest([[list(f), [list(v) for v in engine.cover_fit(*f)]] for f in FITS]),
    }
    for name in sorted(meta["themes"]):
        for setting, words in SETTINGS.items():
            args = parse_args(["--config", "none", "--preset", name, *words])
            parts[f"scene:{name}:{setting}"] = _scene_digest(native.scene_bytes(args, None))
        r = from_args(parse_args(["--config", "none", "--preset", name]))
        grids = []
        for w, h in SIZES:
            for s in SCALES:
                sw, sh = (max(64, round(w * s)), max(36, round(h * s))) if s < 0.999 else (w, h)
                r.cell_scale = s if s < 0.999 else 1.0
                g = vars(geometry(sw, sh, cols, r))
                grids.append([w, h, s, {k: list(v) if isinstance(v, tuple) else v for k, v in sorted(g.items())}])
        parts[f"grid:{name}"] = _digest(grids)
    return parts


def written(path) -> dict[str, str]:
    """The reference as data/stream-reference.json holds it."""
    return json.loads(open(path, encoding="utf-8").read())["parts"]


def write(path) -> dict[str, str]:
    import os
    if not os.path.exists(path):
        # a scene names its build and stream, which names this file: there first, empty (the
        # line is no part of the picture, and left out of the digest)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('{"contract": "syncrain-stream-reference-1", "parts": {}}\n')
    parts = reference()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"contract": "syncrain-stream-reference-1", "parts": parts}, indent=1, sort_keys=True) + "\n")
    return parts
