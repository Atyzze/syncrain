"""Which symbols fall: sets of characters with weights or shares, the atlas they are drawn from, and
the table the state shader picks from (syncrain/data/shaders/state.frag, pickGlyph).

A theme says its own sets (themes.json, "glyphs"); a symbols file says yours:
`~/.config/syncrain/glyphs.json`, or `--glyphs PATH` (`syncrain --write-glyphs` writes a starter).
Every symbol shipped is drawn in syncrain/data/glyphs.png (tools/build_assets.py makes it); a
symbol that is not there is drawn from a font on this machine, found with fontconfig. A wallpaper
keeps only the symbols its sets use, so a short list costs little memory.

The drops still fall the same on every machine of a channel; which symbol a drop shows is the
symbols file's, so two machines show the same symbols only with the same file.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import unicodedata

CELL = 64                     # atlas pixels per rain cell
SLOT = CELL * 3 // 2          # 96: a slot spans 1.5 cells, the glyph centred, room for its glow
GRID = 16                     # slots per atlas row
WORD_CELLS = 40               # a hidden word or sentence's longest (the words texture's width; state.frag)
GAP = 254                     # a space in one: no glyph, the column dark there (255 ends one)
MAX_GLYPHS = 640              # 40 rows: 3840 px, within what any card takes (4096)
MAX_SETS = 16                 # state.frag's uSets
MAX_TABLE = 2048              # the table texture's width
RENDER = 1                    # how glyphs are drawn here: a new number throws the drawn ones away
CONTRACT = "syncrain-glyphs-1"

# ---------------------------------------------------------------------------- the characters

KATAKANA = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン"
HIRAGANA = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
KANJI = "日月火水木金土山川田人口目耳手足力上下中大小本天"
DIGITS = "0123456789"
UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
NIX32 = "0123456789abcdfghijklmnpqrsvwxyz"          # Nix's base-32 alphabet (no e, o, u, t)
LOWER = "".join(ch for ch in NIX32 if not ch.isdigit())
MATRIX_SYMS = 'Z:.=*+-<>¦|"'
NIX_SYMS = "{}[];=/:.'\"-"
SNOW = "❄❅❆"
CYRILLIC = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
GREEK = "ΓΔΘΛΞΠΣΦΨΩαβγδεζηθικλμνξπρστυφχψω"
ARABIC = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي٠١٢٣٤٥٦٧٨٩"
FRENCH = "àâæçéèêëîïôœùûüÿÀÇÉÈŒ"
# Egyptian hieroglyphs by Gardiner's sign list: people, gods, body, animals, birds, plants, sky and
# water, buildings, crowns and sceptres, tools.
GARDINER = """A1 A2 A40 B1 C1 C10 C11 D4 D10 D21 D28 D50 D58 E1 E9 E13 E15 E20 E23 E34 F4 F13 F31 F34 F35
G1 G5 G7 G17 G25 G36 G38 G39 G43 H6 I3 I8 I9 I10 I12 K1 L1 M4 M8 M12 M17 M23 N1 N5 N8 N14 N27 N29 N35 N36
N37 N41 O1 O4 O28 O34 O49 P1 Q1 Q3 Q7 R4 R8 R11 R14 S1 S3 S7 S12 S29 S34 S38 S40 S42 S45 T3 T14 U1 U7 U33
V1 V13 V20 V28 V31 W24 X1 Y5 Z11 Aa1""".split()
GARDINER_MORE = """A12 A28 D1 D2 D19 E6 E17 F9 G14 G21 G29 G40 H1 I1 I14 K5 L2 M1 M2 N2 O10 O24 P5 S24 T22 V6
W10 X8 Y1 Aa2""".split()


def gardiner(code: str) -> str:
    letters, number, variant = re.match(r"([A-Za-z]+)(\d+)([A-Z]?)$", code).groups()
    return unicodedata.lookup(f"EGYPTIAN HIEROGLYPH {letters.upper()}{int(number):03d}{variant}")


HIEROGLYPHS = "".join(gardiner(c) for c in GARDINER)
HIEROGLYPHS_MORE = "".join(gardiner(c) for c in GARDINER_MORE)


def is_hieroglyph(ch: str) -> bool:
    return 0x13000 <= ord(ch) <= 0x1345F


def is_cjk(ch: str) -> bool:
    o = ord(ch)
    return 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF


def starter() -> dict:
    """`syncrain --write-glyphs`: a bit of everything, every set as likely as the next."""
    return {
        "contract": CONTRACT,
        "about": ("syncrain's symbols. Each set: its characters, and a weight (how often its symbols fall "
                  "next to the other sets'; 0 leaves it out) or a share (that fraction of all symbols, "
                  "0.1 = 10%). balance 'sets': a set's weight is for the whole set; 'glyphs': for each of "
                  "its characters. Optional per set: font (a family or a file), size (of the cell, 0.9), "
                  "mirror (true). Restart syncrain after a change."),
        "balance": "sets",
        "sets": [
            {"name": "katakana", "chars": KATAKANA, "weight": 1},
            {"name": "hiragana", "chars": HIRAGANA, "weight": 1},
            {"name": "kanji", "chars": KANJI, "weight": 1},
            {"name": "latin", "chars": UPPER + LOWER, "weight": 1},
            {"name": "digits", "chars": DIGITS, "weight": 1},
            {"name": "cyrillic", "chars": CYRILLIC, "weight": 1},
            {"name": "greek", "chars": GREEK, "weight": 1},
            {"name": "arabic", "chars": ARABIC, "weight": 1},
            {"name": "french", "chars": FRENCH, "weight": 1},
            {"name": "hieroglyphs", "chars": HIEROGLYPHS + HIEROGLYPHS_MORE, "weight": 1},
            {"name": "symbols", "chars": "".join(dict.fromkeys(NIX_SYMS + MATRIX_SYMS)), "weight": 1},
            {"name": "favourites", "chars": "λ❄𓆙", "weight": 1},
        ],
    }


def default_path() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "syncrain", "glyphs.json")


def cache_dir() -> str:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "syncrain")


# ---------------------------------------------------------------------------- reading a symbols file

class GlyphsError(ValueError):
    pass


def read_config(path: str) -> dict:
    """A symbols file, checked: GlyphsError says what is wrong, where."""
    try:
        with open(path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except OSError as e:
        raise GlyphsError(f"{path}: {e.strerror}") from e
    except json.JSONDecodeError as e:
        raise GlyphsError(f"{path}: not JSON ({e.msg}, line {e.lineno} column {e.colno})") from e
    except UnicodeDecodeError as e:
        raise GlyphsError(f"{path}: not UTF-8 text (save it as UTF-8)") from e
    return check_config(cfg, path)


def check_config(cfg, where="the symbols") -> dict:
    if not isinstance(cfg, dict) or not isinstance(cfg.get("sets"), list) or not cfg["sets"]:
        raise GlyphsError(f"{where}: needs a list \"sets\"")
    balance = cfg.get("balance", "sets")
    if balance not in ("sets", "glyphs"):
        raise GlyphsError(f"{where}: balance is \"sets\" or \"glyphs\", not {balance!r}")
    sets = []
    for i, s in enumerate(cfg["sets"]):
        name = s.get("name", f"set {i + 1}") if isinstance(s, dict) else f"set {i + 1}"
        if not isinstance(name, str):
            raise GlyphsError(f"{where}: set {i + 1}'s name is text")
        if not isinstance(s, dict) or not isinstance(s.get("chars"), str) or not s["chars"].strip():
            raise GlyphsError(f"{where}: {name} needs \"chars\", a string of characters")
        for key in ("weight", "share", "size"):
            if key in s and (not isinstance(s[key], (int, float)) or isinstance(s[key], bool) or s[key] < 0):
                raise GlyphsError(f"{where}: {name}'s {key} must be a number, 0 or more")
        if "size" in s and not 0.2 <= s["size"] <= 2:
            raise GlyphsError(f"{where}: {name}'s size is in cells, 0.2 to 2")
        if "font" in s and not isinstance(s["font"], str):
            raise GlyphsError(f"{where}: {name}'s font is a family name or a file")
        if "mirror" in s and not isinstance(s["mirror"], bool):     # "no" would mirror them
            raise GlyphsError(f"{where}: {name}'s mirror is true or false")
        if s.get("share", 0) > 1:
            raise GlyphsError(f"{where}: {name}'s share is a fraction of all symbols, 0 to 1")
        sets.append(dict(s, name=name))
    if _total(s.get("share", 0) for s in sets) > 1.0 + 1e-9:
        raise GlyphsError(f"{where}: the shares add up to more than 1")
    if len(sets) > MAX_SETS:
        raise GlyphsError(f"{where}: at most {MAX_SETS} sets")
    return {"balance": balance, "sets": sets}


def _total(values) -> float:
    """A sum taken left to right, as JavaScript's reduce takes it (Python's sum() compensates)."""
    out = 0.0
    for v in values:
        out += v
    return out


def chars_of(s: dict) -> list[str]:
    """A set's characters, each once, white space left out."""
    return [ch for ch in dict.fromkeys(s["chars"]) if not ch.isspace()]


# ---------------------------------------------------------------------------- choosing

def set_shares(cfg: dict, hieroglyphs: float | None = None) -> list[float]:
    """Each set's share of the symbols, in order (they add up to 1, or are all 0 for no sets).
    Shares are given; the rest is split by weight (`balance` "glyphs": weight times characters).
    `hieroglyphs` gives the set named so that share (`--hieroglyphs`)."""
    sets = cfg["sets"]
    given = [s.get("share") for s in sets]
    if hieroglyphs is not None:
        for i, s in enumerate(sets):
            if s["name"] == "hieroglyphs":
                given[i] = hieroglyphs
    fixed = _total(g for g in given if g is not None)
    if fixed > 1.0:
        given = [None if g is None else g / fixed for g in given]
        fixed = 1.0
    weights = []
    for s, g in zip(sets, given):
        w = 0.0 if g is not None else float(s.get("weight", 1))
        if cfg["balance"] == "glyphs":
            w *= len(chars_of(s))
        weights.append(w)
    total = _total(weights)
    rest = 1.0 - fixed
    out = []
    for g, w in zip(given, weights):
        out.append(g if g is not None else (rest * w / total if total > 0 else 0.0))
    norm = _total(out)
    if norm <= 0:
        return [0.0] * len(sets)
    return [x / norm for x in out]


# ---------------------------------------------------------------------------- the atlas

def spec_key(ch: str, mirror: bool) -> str:
    return ch + ("~" if mirror else "")


def set_key(ch: str, s: dict) -> str:
    """A character as a set draws it: the shipped glyph's key, or (with a font or size of its own) a
    key of its own, drawn here."""
    key = spec_key(ch, bool(s.get("mirror", False)))
    if "font" in s or "size" in s:
        key += f"|{s.get('font', '')}|{s.get('size', '')}"
    return key


class Library:
    """The shipped glyph images: syncrain/data/glyphs.png and its list in themes.json."""

    def __init__(self, meta, data_dir):
        lib = meta["library"]
        self.path = os.path.join(data_dir, lib["file"])
        self.keys = lib["glyphs"]
        self.index = {k: i for i, k in enumerate(self.keys)}
        self._image = None

    def image(self):
        if self._image is None:
            from PIL import Image
            self._image = Image.open(self.path).convert("RGBA")
        return self._image

    def release(self):
        self._image = None

    def slot(self, key):
        i = self.index[key]
        y, x = divmod(i, GRID)
        return self.image().crop((x * SLOT, y * SLOT, (x + 1) * SLOT, (y + 1) * SLOT))


class Resolved:
    """What a wallpaper draws its symbols with: the atlas (only the glyphs used), the table of atlas
    slots the sets pick from, the sets' shares, the hidden words in atlas slots."""

    def __init__(self, keys, table, sets, shares, words, source, missing, render):
        self.keys = keys                  # atlas slot -> "char" or "char~" (mirrored)
        self.table = table                # glyph table entries -> atlas slot
        self.sets = sets                  # [(name, first table entry, entries)]
        self.shares = shares
        self.words = words
        self.source = source              # where the sets came from, for --diagnose
        self.missing = missing            # characters no font here can draw
        self._render = render

    @property
    def rows(self) -> int:
        return max(1, -(-len(self.keys) // GRID))

    def uniform(self):
        """state.frag's uSets: cumulative share, first table entry, entries; and how many."""
        chosen = [((first, count), share) for (_, first, count), share in zip(self.sets, self.shares)
                  if share > 0 and count > 0]
        whole = _total(share for _, share in chosen)
        out, acc = [], 0.0
        for (first, count), share in chosen:
            acc += share / whole
            out.append((acc, first, count))
        if not out:                       # nothing chosen: every symbol alike
            out = [(1.0, 0, len(self.table))]
        out[-1] = (1.0, out[-1][1], out[-1][2])
        return out

    def table_bytes(self) -> bytes:
        data = bytearray(len(self.table) * 4)
        for i, slot in enumerate(self.table):
            data[i * 4:i * 4 + 4] = bytes((slot & 255, slot >> 8, 0, 255))
        return bytes(data)

    def words_bytes(self):
        n = max(1, len(self.words))
        out = bytearray([255]) * (WORD_CELLS * n * 4)
        for row, w in enumerate(self.words):
            for i, g in enumerate(w[:WORD_CELLS]):
                out[(row * WORD_CELLS + i) * 4] = g
        return bytes(out), n

    def atlas(self):
        """(width, height, RGBA bytes)."""
        return self._render()


def resolve(meta, theme, data_dir, config=None, source="the preset", hieroglyphs=None) -> Resolved:
    """The symbols for `theme`, from `config` (a checked symbols file) or the preset's own sets."""
    library = Library(meta, data_dir)
    cfg = config or check_config(theme["glyphs"], "themes.json")
    keys, slots = [], {}

    def slot_of(key):
        if key not in slots:
            slots[key] = len(keys)
            keys.append(key)
        return slots[key]

    # a file far over the limits is refused before any work on it (a set of millions of characters)
    given = sum(len(set(s["chars"])) for s in cfg["sets"])
    if given > 8 * MAX_TABLE:
        raise GlyphsError(f"{source}: {given} characters in all sets together; at most {MAX_TABLE} symbols")
    words, specs = [], {}                              # key -> (character, the set that names it)
    for word in theme.get("wordText", []):             # first: the words texture holds 8 bits
        for ch in word:
            if ch != " ":
                specs.setdefault(spec_key(ch, False), (ch, {}))
        words.append([GAP if ch == " " else slot_of(spec_key(ch, False)) for ch in word])
    table, sets = [], []
    for s in cfg["sets"]:
        first = len(table)
        for ch in chars_of(s):
            key = set_key(ch, s)
            specs.setdefault(key, (ch, s))
            table.append(slot_of(key))
        sets.append((s["name"], first, len(table) - first))
    if len(keys) > MAX_GLYPHS:
        raise GlyphsError(f"{source}: {len(keys)} different symbols; at most {MAX_GLYPHS}")
    if len(table) > MAX_TABLE:
        raise GlyphsError(f"{source}: {len(table)} symbols in all sets together; at most {MAX_TABLE}")
    shares = set_shares(cfg, hieroglyphs)
    drawn = [k for k in keys if k not in library.index]
    fonts = font_list() if drawn else []
    missing = [specs[k][0] for k in drawn if not font_candidates(specs[k][0], fonts, specs[k][1].get("font"))]

    def render():
        nonlocal fonts
        try:
            return build_atlas(keys, library, specs, fonts)
        finally:
            library.release()
            fonts = []

    return Resolved(keys, table, sets, shares, words, source, missing, render)


def for_theme(meta, theme, data_dir, path=None, hieroglyphs=None, warn=None) -> Resolved:
    """The symbols a wallpaper uses: `path` ("" or "theme": the preset's own), else the default symbols
    file if there is one. A broken file is said (`warn`) and the preset's symbols are used."""
    if path in ("", "theme"):
        return resolve(meta, theme, data_dir, hieroglyphs=hieroglyphs)
    path = path or default_path()
    if not os.path.exists(path) and path == default_path():
        return resolve(meta, theme, data_dir, hieroglyphs=hieroglyphs)
    try:
        return resolve(meta, theme, data_dir, read_config(path), path, hieroglyphs)
    except GlyphsError as e:
        if warn:
            warn(f"{e}; the preset's own symbols instead")
        return resolve(meta, theme, data_dir, hieroglyphs=hieroglyphs)


# ---------------------------------------------------------------------------- drawing glyphs

def font_list() -> list[dict]:
    """Every font fontconfig knows: file, face index, family, style, and the characters it has."""
    try:
        # a font file whose name is not UTF-8 is still a font: its name goes through as it is
        done = subprocess.run(["fc-list", "--format", "%{file}\t%{index}\t%{family[0]}\t%{style[0]}\t%{charset}\n"],
                              capture_output=True, text=True, errors="surrogateescape", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    fonts = []
    for line in done.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 5 or not parts[0].lower().endswith((".ttf", ".otf", ".ttc", ".otc")):
            continue
        ranges = []
        for r in parts[4].split():
            lo, _, hi = r.partition("-")
            try:
                ranges.append((int(lo, 16), int(hi or lo, 16)))
            except ValueError:
                pass
        fonts.append(dict(file=parts[0], index=int(parts[1] or 0), family=parts[2], style=parts[3], ranges=ranges))
    return fonts


#: The families tried first, in order, for a character no set names a font for.
PREFERRED = ("Noto Sans Mono CJK JP", "Noto Sans CJK JP", "DejaVu Sans", "Noto Sans", "Noto Sans Arabic",
             "Noto Naskh Arabic", "Noto Sans Egyptian Hieroglyphs", "Noto Sans Symbols", "Noto Sans Symbols 2")


def font_candidates(ch: str, fonts, wanted=None) -> list:
    """(file, index) of the fonts with `ch`, best first: a file the set names, its family, the
    preferred families, bold before the rest. Empty: no font here has it."""
    out = []
    if wanted and os.path.isfile(str(wanted)):
        out.append((wanted, 0))
    code = ord(ch)
    having = [f for f in fonts if any(lo <= code <= hi for lo, hi in f["ranges"])]
    order = ([wanted] if wanted else []) + list(PREFERRED)

    def rank(f):
        fam = order.index(f["family"]) if f["family"] in order else len(order)
        colour = "Color" in f["family"] or "Emoji" in f["family"]      # bitmap colour fonts last
        return (colour, fam, 0 if "Bold" in f["style"] else 1, "Italic" in f["style"] or "Oblique" in f["style"],
                f["file"])
    out += [(f["file"], f["index"]) for f in sorted(having, key=rank)]
    return list(dict.fromkeys(out))


def font_for(ch: str, fonts, wanted=None):
    found = font_candidates(ch, fonts, wanted)
    return found[0] if found else None


def render_glyph(ch, font, size=0.9, mirror=False, squeeze=1.0, fit=None, grow=0):
    """One glyph's coverage, a SLOT x SLOT greyscale image: centred, `size` of a cell tall (as a font
    size), or with `fit` its longer side `fit` cells (the hieroglyphs, whose strokes `grow`)."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    S = 4                                               # supersample
    file, index = font
    if fit:
        f = ImageFont.truetype(file, int(CELL * S * 1.2), index=index)
        big = Image.new("L", (SLOT * S * 3, SLOT * S * 3), 0)
        ImageDraw.Draw(big).text((SLOT * S, SLOT * S), ch, font=f, fill=255)
        box = big.getbbox()
        if not box:
            return Image.new("L", (SLOT, SLOT), 0)
        big = big.crop(box)
        k = fit * CELL * S / max(big.size)
        big = big.resize((max(1, round(big.width * k)), max(1, round(big.height * k))), Image.LANCZOS)
        if grow:
            big = big.filter(ImageFilter.MaxFilter(grow))
        out = Image.new("L", (SLOT * S, SLOT * S), 0)
        out.paste(big, ((SLOT * S - big.width) // 2, (SLOT * S - big.height) // 2))
        return out.resize((SLOT, SLOT), Image.LANCZOS)
    f = ImageFont.truetype(file, int(round(size * CELL * S)), index=index)
    big = Image.new("L", (SLOT * S * 2, SLOT * S * 2), 0)
    d = ImageDraw.Draw(big)
    bb = d.textbbox((0, 0), ch, font=f)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text((big.width / 2 - w / 2 - bb[0], big.height / 2 - h / 2 - bb[1]), ch, font=f, fill=255)
    if mirror:
        big = big.transpose(Image.FLIP_LEFT_RIGHT)
    if squeeze != 1.0:
        big = big.resize((int(big.width * squeeze), big.height), Image.LANCZOS)
    cx, cy = big.width // 2, big.height // 2
    big = big.crop((cx - SLOT * S // 2, cy - SLOT * S // 2, cx + SLOT * S // 2, cy + SLOT * S // 2))
    return big.resize((SLOT, SLOT), Image.LANCZOS)


def render_kwargs(ch: str, s: dict) -> dict:
    """How a character a set names is drawn, when the library does not have it."""
    if is_hieroglyph(ch):
        return dict(fit=s.get("size", 0.86), grow=9)
    if is_cjk(ch):
        return dict(size=s.get("size", 0.8), squeeze=0.88, mirror=bool(s.get("mirror", False)))
    return dict(size=s.get("size", 0.9), mirror=bool(s.get("mirror", False)))


def draw_slot(ch, s, fonts):
    """A slot drawn from the best font that can draw `ch` (a font that fails, a colour bitmap font
    say, gives way to the next); a blank slot if none can."""
    from PIL import Image
    for font in font_candidates(ch, fonts, s.get("font")):
        try:
            return glow_slot(render_glyph(ch, font, **render_kwargs(ch, s)))
        except Exception:  # noqa: BLE001 - Pillow's errors for fonts it cannot use are of every kind
            continue
    return Image.new("RGBA", (SLOT, SLOT), (0, 0, 0, 255))


def glow_slot(coverage):
    """A slot as the atlas holds it: R coverage, G its near glow, B the tight bloom of white heads."""
    from PIL import Image, ImageFilter
    near = coverage.filter(ImageFilter.GaussianBlur(0.139 * CELL))
    tight = coverage.filter(ImageFilter.GaussianBlur(0.069 * CELL))
    return Image.merge("RGBA", (coverage, near, tight, Image.new("L", coverage.size, 255)))


def font_stamp(font):
    try:
        st = os.stat(font[0])
        return [font[0], font[1], st.st_mtime_ns, st.st_size]
    except OSError:
        return list(font)


def build_atlas(keys, library, specs, fonts):
    """The atlas for these slots: shipped glyphs copied from the library, the rest drawn here (and
    kept in the cache, as drawing a few hundred takes seconds; the eight used last stay)."""
    from PIL import Image
    rows = max(1, -(-len(keys) // GRID))
    drawn = [k for k in keys if k not in library.index]
    own = {}
    if drawn:
        sig = hashlib.sha256(json.dumps([RENDER, CELL, SLOT] + [
            [specs[k][0], render_kwargs(*specs[k]), [font_stamp(f) for f in font_candidates(
                specs[k][0], fonts, specs[k][1].get("font"))[:3]]] for k in drawn],
            ensure_ascii=False).encode()).hexdigest()[:16]
        cached = os.path.join(cache_dir(), f"glyphs-{sig}.png")
        try:
            img = Image.open(cached).convert("RGBA")
            if img.width != GRID * SLOT or img.height < -(-len(drawn) // GRID) * SLOT:
                raise ValueError("another size")
            os.utime(cached)
            for i, k in enumerate(drawn):
                y, x = divmod(i, GRID)
                own[k] = img.crop((x * SLOT, y * SLOT, (x + 1) * SLOT, (y + 1) * SLOT))
        except Exception:  # noqa: BLE001 - none yet, or a broken one: drawn again
            own = {k: draw_slot(specs[k][0], specs[k][1], fonts) for k in drawn}
            sheet = Image.new("RGBA", (GRID * SLOT, -(-len(drawn) // GRID) * SLOT), (0, 0, 0, 255))
            for i, k in enumerate(drawn):
                y, x = divmod(i, GRID)
                sheet.paste(own[k], (x * SLOT, y * SLOT))
            try:
                os.makedirs(os.path.dirname(cached), exist_ok=True)
                tmp = f"{cached}.{os.getpid()}.tmp"
                sheet.save(tmp, format="PNG")
                os.replace(tmp, cached)
                old = sorted((os.path.join(cache_dir(), n) for n in os.listdir(cache_dir())
                              if n.startswith("glyphs-") and n.endswith(".png")), key=os.path.getmtime)
                for path in old[:-8]:
                    os.remove(path)
            except OSError:
                pass
    atlas = Image.new("RGBA", (GRID * SLOT, rows * SLOT), (0, 0, 0, 255))
    for i, k in enumerate(keys):
        y, x = divmod(i, GRID)
        atlas.paste(library.slot(k) if k in library.index else own[k], (x * SLOT, y * SLOT))
    data = atlas.tobytes()
    return atlas.width, atlas.height, data


def write_starter(path: str) -> str:
    """`syncrain --write-glyphs`: the starter file, unless one is there."""
    if os.path.exists(path):
        return f"{path} is there already; edit it, or move it away for a new one"
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    text = json.dumps(starter(), ensure_ascii=False, indent=2)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    return f"wrote {path}: a bit of everything, every set as likely as the next"
