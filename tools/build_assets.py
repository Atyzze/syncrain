#!/usr/bin/env python3
"""Build the assets shared by the web and native runners.

Outputs (into syncrain/data/):
  atlas.png      glyph atlas, 16x16 slots of 96 px. Each slot covers 1.5 x 1.5 rain cells with the glyph
                 centred, so glow halos can spill a little into the neighbouring cell.
                 R = glyph coverage, G = near glow (blurred glyph), B = tight bloom for the bright heads.
  themes.json    palettes, glyph lookup tables (256 weighted entries), hidden words, snow and logo settings.
  logo-white.png / logo-colours.png   the official NixOS snowflake (CC-BY 4.0), with colour bled into the
                 transparent area so mipmapped edges stay clean.

Run from the repository root:  python3 tools/build_assets.py --nixos-artwork /path/to/nixos-artwork
"""
import argparse, json, os, subprocess, tempfile
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument('--nixos-artwork', required=True, help='checkout of github.com/NixOS/nixos-artwork')
ap.add_argument('--out', default=os.path.join(os.path.dirname(__file__), '..', 'syncrain', 'data'))
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)

CJK = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'          # index 5: Noto Sans Mono CJK JP Bold
DEJAVU = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'      # snowflake dingbats

CELL = 64                     # atlas pixels per rain cell
SLOT = CELL * 3 // 2          # 96: the slot spans 1.5 cells
GRID = 16                     # 16 x 16 slots -> 1536 x 1536 atlas

KATAKANA = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン'
DIGITS = '0123456789'
UPPER = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
NIX32 = '0123456789abcdfghijklmnpqrsvwxyz'          # Nix's base-32 alphabet (no e, o, u, t)
LOWER = ''.join(ch for ch in NIX32 if not ch.isdigit())
MATRIX_SYMS = 'Z:.=*+-<>¦|"'
NIX_SYMS = '{}[];=/:.\'"-'
SNOW = '❄❅❆'

# (char, font, index, size as fraction of the cell, mirror, horizontal squeeze)
glyph_specs = []
def add(chars, font, idx, size, mirror=False, squeeze=1.0):
    for ch in chars:
        if not any(g[0] == ch and g[4] == mirror for g in glyph_specs):
            glyph_specs.append((ch, font, idx, size, mirror, squeeze))
add(KATAKANA, CJK, 5, 0.80, mirror=True, squeeze=0.88)
add(DIGITS, CJK, 5, 0.90)
add(UPPER, CJK, 5, 0.90)
add(LOWER, CJK, 5, 0.90)
add('λ', CJK, 5, 0.90)
add(MATRIX_SYMS, CJK, 5, 0.83)
add(''.join(ch for ch in NIX_SYMS if ch not in MATRIX_SYMS), CJK, 5, 0.83)
add(SNOW, DEJAVU, 0, 1.0)
assert len(glyph_specs) <= GRID * GRID
index = {(g[0], g[4]): i for i, g in enumerate(glyph_specs)}
def gid(ch, mirror=False):
    return index[(ch, mirror)]

def render(ch, font, idx, size, mirror, squeeze):
    S = 4                                               # supersample
    f = ImageFont.truetype(font, int(round(size * CELL * S)), index=idx)
    big = Image.new('L', (SLOT * S * 2, SLOT * S * 2), 0)
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

atlas = np.zeros((GRID * SLOT, GRID * SLOT, 4), np.uint8)
atlas[..., 3] = 255
for i, spec in enumerate(glyph_specs):
    g = render(*spec)
    ga = np.asarray(g).astype(np.float32)
    near = cv2.GaussianBlur(ga, (0, 0), 0.139 * CELL)      # same glow radius as the offline renders (5 px @ 36 px cells)
    tight = cv2.GaussianBlur(ga, (0, 0), 0.069 * CELL)     # tight bloom used on the white heads
    y, x = divmod(i, GRID)
    sl = (slice(y * SLOT, (y + 1) * SLOT), slice(x * SLOT, (x + 1) * SLOT))
    atlas[sl[0], sl[1], 0] = ga.astype(np.uint8)
    atlas[sl[0], sl[1], 1] = np.clip(near + 0.5, 0, 255).astype(np.uint8)
    atlas[sl[0], sl[1], 2] = np.clip(tight + 0.5, 0, 255).astype(np.uint8)
Image.fromarray(atlas, 'RGBA').save(os.path.join(args.out, 'atlas.png'), optimize=True)

def lut(weights):
    """256 glyph indices, each glyph appearing in proportion to its weight (largest-remainder rounding)."""
    items = list(weights.items())
    total = sum(w for _, w in items)
    raw = [(g, 256 * w / total) for g, w in items]
    counts = {g: int(r) for g, r in raw}
    left = 256 - sum(counts.values())
    for g, r in sorted(raw, key=lambda t: (-(t[1] - int(t[1])), t[0]))[:left]:
        counts[g] += 1
    table = []
    for g, _ in items:
        table += [g] * counts[g]
    assert len(table) == 256
    # spread identical entries so neighbouring hash values do not cluster (purely cosmetic, deterministic)
    rng = np.random.default_rng(12345)
    return [int(v) for v in rng.permutation(table)]

def word_rows(words):
    return [[gid(ch) for ch in w] for w in words]

matrix_w = {}
for ch in KATAKANA: matrix_w[gid(ch, True)] = 3.0
for ch in DIGITS: matrix_w[gid(ch)] = 1.6
for ch in MATRIX_SYMS: matrix_w[gid(ch)] = 0.6

nix_w = {}
for ch in NIX32: nix_w[gid(ch)] = 1.0
nix_w[gid('λ')] = 2.6
nix_w[gid('❄')] = 0.9; nix_w[gid('❅')] = 0.5; nix_w[gid('❆')] = 0.5
for ch in NIX_SYMS: nix_w[gid(ch)] = 0.25

def rgb(hexstr, k=1.0):
    h = hexstr.lstrip('#')
    return [round(int(h[i:i + 2], 16) / 255 * k, 4) for i in (0, 2, 4)]

themes = {
    'nixos': {
        'label': 'NixOS snow',
        'lut': lut(nix_w),
        'words': word_rows(['NIXOS', 'FLAKE', 'NIXPKGS', 'LAMBDA', 'DERIVATION', 'DECLARATIVE',
                            'REPRODUCIBLE', 'HYDRA', 'OVERLAY', 'ROLLBACK']),
        'colors': {'deep': rgb('#132a52'), 'mid': rgb('#3d6ed2'), 'pale': rgb('#8cc0ee'),
                   'head': rgb('#eef7ff'), 'glow': rgb('#2858b8')},
        'background': {'mode': 'gradient', 'top': rgb('#03050a'), 'bottom': rgb('#060b14'),
                       'center': rgb('#0a1a33'), 'vignette': 0.55},
        'logo': {'default': 'white', 'size': 0.40, 'glow': rgb('#7ebae4'), 'glowStrength': 0.22,
                 'spin': 180, 'hueCycle': 90, 'drift': 0.03},
        'rain': {'density': 0.43, 'wordRate': 0.085, 'glintRate': 0.23, 'bloom': 1.0, 'veil': 0.35, 'contrast': 1,
                 'rainbow': 'logo', 'allHueCycle': 600},
        # cell (power of two, in 1/1080ths of the screen height), speed (whole units per second),
        # density, brightness | radius min, max, sway, star | colour, front
        'snow': [
            {'cell': 32,  'speed': 17, 'density': 0.22, 'bright': 0.24, 'rmin': 0.7,  'rmax': 1.3,  'sway': 5,  'star': 0, 'color': rgb('#9fb4d4'), 'front': 0},
            {'cell': 64,  'speed': 29, 'density': 0.30, 'bright': 0.42, 'rmin': 1.4,  'rmax': 2.4,  'sway': 10, 'star': 0, 'color': rgb('#c9d9ef'), 'front': 0},
            {'cell': 128, 'speed': 50, 'density': 0.20, 'bright': 0.62, 'rmin': 6.0,  'rmax': 10.0, 'sway': 18, 'star': 1, 'color': rgb('#e4eefa'), 'front': 0},
            {'cell': 256, 'speed': 88, 'density': 0.16, 'bright': 0.70, 'rmin': 14.0, 'rmax': 22.0, 'sway': 28, 'star': 1, 'color': rgb('#ffffff'), 'front': 1},
        ],
    },
    'matrix': {
        'label': 'Matrix green',
        'lut': lut(matrix_w),
        'words': word_rows(['AI', 'NEURAL', 'CACHYOS', 'TENSOR', 'AGENT', 'LINUX', 'ONLINE', 'MATRIX']),
        'colors': {'deep': [0.0, 0.62, 0.22], 'mid': [0.12, 1.0, 0.36], 'pale': [0.6, 1.0, 0.68],
                   'head': [0.85, 1.0, 0.9], 'glow': [0.04, 0.6, 0.22]},
        'background': {'mode': 'gradient', 'top': rgb('#020604'), 'bottom': rgb('#03090a'),
                       'center': rgb('#06180f'), 'vignette': 0.4},
        'logo': {'default': 'none', 'size': 0.40, 'glow': [0.3, 0.9, 0.6], 'glowStrength': 0.0,
                 'spin': 180, 'hueCycle': 90, 'drift': 0.03},
        'rain': {'density': 0.43, 'wordRate': 0.085, 'glintRate': 0.23, 'bloom': 1.25, 'veil': 0.35, 'contrast': 1,
                 'rainbow': 'logo', 'allHueCycle': 600},
        'snow': [],
    },
}

meta = {
    'contract': 'syncrain-themes-1',   # the file's format; a reader checks it, a build number is not it
    'epoch0': 1704067200,          # 2024-01-01T00:00:00Z; time is passed as whole seconds since this + fraction
    'cols': 64,
    'atlas': {'file': 'atlas.png', 'grid': GRID, 'slot': SLOT, 'cell': CELL, 'glyphs': len(glyph_specs)},
    'glyphs': [g[0] + ('~' if g[4] else '') for g in glyph_specs],
    'themes': themes,
}
with open(os.path.join(args.out, 'themes.json'), 'w', encoding='utf-8') as fh:
    json.dump(meta, fh, ensure_ascii=False, separators=(',', ':'))

# ---- official NixOS logo, rasterised, with colour bled outward under the transparent area
logo_dir = os.path.join(args.nixos_artwork, 'logo')
for variant, svg in (('white', 'nix-snowflake-white.svg'), ('colours', 'nix-snowflake-colours.svg')):
    with tempfile.TemporaryDirectory() as td:
        png = os.path.join(td, 'l.png')
        subprocess.run(['rsvg-convert', '-w', '1024', '-h', '1024', os.path.join(logo_dir, svg), '-o', png], check=True)
        im = np.asarray(Image.open(png).convert('RGBA')).astype(np.float32)
    rgbv, a = im[..., :3], im[..., 3] / 255.0
    # bleed colour outward: for transparent pixels take the alpha-weighted average colour of the
    # nearest opaque area (smallest blur radius that reaches it)
    out_rgb, filled = rgbv.copy(), a > 0.004
    for sigma in (1, 2, 4, 8, 16, 32, 64, 128):
        C = cv2.GaussianBlur(rgbv * a[..., None], (0, 0), sigma)
        A = cv2.GaussianBlur(a, (0, 0), sigma)
        newly = (~filled) & (A > 1e-3)
        out_rgb[newly] = (C / np.maximum(A, 1e-6)[..., None])[newly]
        filled |= newly
    out_rgb[~filled] = (rgbv * a[..., None]).sum(axis=(0, 1)) / max(a.sum(), 1e-6)
    out = np.dstack([np.clip(out_rgb + 0.5, 0, 255), im[..., 3]]).astype(np.uint8)
    # pad to 1536 (logo in the central 2/3) so the blurred mip levels used for the halo have room
    padded = np.zeros((1536, 1536, 4), np.uint8)
    edge = np.median(out[..., :3][out[..., 3] > 128], axis=0).astype(np.uint8)
    padded[..., :3] = edge
    padded[256:1280, 256:1280] = out
    Image.fromarray(padded, 'RGBA').save(os.path.join(args.out, f'logo-{variant}.png'), optimize=True)

print(f'{len(glyph_specs)} glyphs, atlas {GRID * SLOT}px, themes: {", ".join(themes)}')
