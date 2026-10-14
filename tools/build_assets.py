#!/usr/bin/env python3
"""Build the assets shared by every host.

Outputs (into syncrain/data/):
  glyphs.png     every shipped glyph, 16 slots a row, 96 px each (1.5 x 1.5 rain cells, the glyph
                 centred, so its glow can spill into the neighbouring cells). R = coverage, G = near
                 glow, B = tight bloom for the white heads. A wallpaper copies the ones its symbols
                 use into its own atlas (syncrain/glyphs.py).
  themes.json    the presets (each one's palette, symbol sets, hidden words, snow and logo settings),
                 which one is the default, and the list of glyphs.png's slots.
  logo-white.png / logo-colours.png   the official NixOS snowflake (CC-BY 4.0), with colour bled into the
                 transparent area so mipmapped edges stay clean (only with --nixos-artwork).
                 logo-syncrain.png comes from its drawing, by tools/build_logo.py.

Run from the repository root:  python3 tools/build_assets.py [--nixos-artwork /path/to/nixos-artwork]
Fonts: Noto Sans Mono CJK JP and DejaVu Sans (Debian's fonts-noto-cjk, fonts-dejavu-core), Noto Sans
Egyptian Hieroglyphs and Noto Sans Arabic (github.com/notofonts, OFL 1.1).
"""
import argparse, json, os, subprocess, sys, tempfile
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from syncrain import glyphs as G  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--nixos-artwork', help='checkout of github.com/NixOS/nixos-artwork (without it the logos stay)')
ap.add_argument('--hieroglyph-font', default='/usr/share/fonts/truetype/noto/NotoSansEgyptianHieroglyphs-Regular.ttf')
ap.add_argument('--arabic-font', default='/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf')
ap.add_argument('--out', default=os.path.join(os.path.dirname(__file__), '..', 'syncrain', 'data'))
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)

CJK = ('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', 5)       # Noto Sans Mono CJK JP Bold
DEJAVU = ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 0)   # snowflake dingbats
HIERO = (args.hieroglyph_font, 0)
ARABIC = (args.arabic_font, 0)

# Every shipped glyph, in slot order: (char, font, how it is drawn).
library = []
def add(chars, font, **kw):
    for ch in chars:
        key = G.spec_key(ch, kw.get('mirror', False))
        if key not in [k for k, _, _ in library]:
            library.append((key, font, kw))
add(G.KATAKANA, CJK, size=0.80, mirror=True, squeeze=0.88)
add(G.DIGITS, CJK, size=0.90)
add(G.UPPER, CJK, size=0.90)
add(G.LOWER, CJK, size=0.90)
add('λ', CJK, size=0.90)
add(G.MATRIX_SYMS, CJK, size=0.83)
add(G.NIX_SYMS, CJK, size=0.83)
add(G.SNOW, DEJAVU, size=1.0)
add(G.HIEROGLYPHS + G.HIEROGLYPHS_MORE, HIERO, fit=0.86, grow=9)
add(G.KATAKANA + G.HIRAGANA + G.KANJI, CJK, size=0.80, squeeze=0.88)
add(G.CYRILLIC + G.GREEK + G.FRENCH, CJK, size=0.90)
add(G.ARABIC, ARABIC, size=0.90)
assert len(library) <= G.MAX_GLYPHS

rows = -(-len(library) // G.GRID)
sheet = Image.new('RGBA', (G.GRID * G.SLOT, rows * G.SLOT), (0, 0, 0, 255))
for i, (key, font, kw) in enumerate(library):
    y, x = divmod(i, G.GRID)
    sheet.paste(G.glow_slot(G.render_glyph(key[0], font, **kw)), (x * G.SLOT, y * G.SLOT))
sheet.save(os.path.join(args.out, 'glyphs.png'), optimize=True)

def rgb(hexstr, k=1.0):
    h = hexstr.lstrip('#')
    return [round(int(h[i:i + 2], 16) / 255 * k, 4) for i in (0, 2, 4)]

# the snow every preset can show (on by default where the preset says so)
# cell (power of two, in 1/1080ths of the screen height), speed (whole units per second),
# density, brightness | radius min, max, sway, star | colour, front
SNOW = [
    {'cell': 32,  'speed': 17, 'density': 0.22, 'bright': 0.24, 'rmin': 0.7,  'rmax': 1.3,  'sway': 5,  'star': 0, 'color': rgb('#9fb4d4'), 'front': 0},
    {'cell': 64,  'speed': 29, 'density': 0.30, 'bright': 0.42, 'rmin': 1.4,  'rmax': 2.4,  'sway': 10, 'star': 0, 'color': rgb('#c9d9ef'), 'front': 0},
    {'cell': 128, 'speed': 50, 'density': 0.20, 'bright': 0.62, 'rmin': 6.0,  'rmax': 10.0, 'sway': 18, 'star': 1, 'color': rgb('#e4eefa'), 'front': 0},
    {'cell': 256, 'speed': 88, 'density': 0.16, 'bright': 0.70, 'rmin': 14.0, 'rmax': 22.0, 'sway': 28, 'star': 1, 'color': rgb('#ffffff'), 'front': 1},
]
# A preset is where the settings start: every value here is one the settings (syncrain/app.py,
# CONFIG_KEYS) can change, but for the rain's inner workings (word and glint rates, veil, contrast).
RAIN = {'density': 0.43, 'wordRate': 0.085, 'glintRate': 0.23, 'veil': 0.35, 'contrast': 1,
        'cycle': 0, 'flavours': 1, 'flavourLayout': 'random'}

MATRIX_GLYPHS = {'balance': 'sets', 'sets': [
    # build 12's weights: each mirrored katakana 3, each digit 1.6, each symbol 0.6
    {'name': 'katakana', 'chars': G.KATAKANA, 'weight': 135, 'mirror': True},
    {'name': 'digits', 'chars': G.DIGITS, 'weight': 16},
    {'name': 'symbols', 'chars': G.MATRIX_SYMS, 'weight': 7.2},
    {'name': 'hieroglyphs', 'chars': G.HIEROGLYPHS + G.HIEROGLYPHS_MORE, 'share': 0.15}]}
MATRIX_COLORS = {'deep': [0.0, 0.62, 0.22], 'mid': [0.12, 1.0, 0.36], 'pale': [0.6, 1.0, 0.68],
                 'head': [0.85, 1.0, 0.9], 'glow': [0.04, 0.6, 0.22]}
MATRIX_BACKGROUND = {'mode': 'gradient', 'top': rgb('#020604'), 'bottom': rgb('#03090a'),
                     'center': rgb('#06180f'), 'vignette': 0.4}

themes = {
    # the operator's own (their settings file of 2026-10-14): the matrix colours, 64 of them at once
    # turning every 55 s, their logo (drawn as logo-syncrain.svg) in its own colour, more bloom
    'syncrain': {
        'label': 'Syncrain',
        'glyphs': MATRIX_GLYPHS,
        'wordText': ['AI', 'sSs', 'NEURAL', 'TENSOR', 'AGENT', 'LINUX', 'ONLINE', 'MATRIX'],
        'colors': MATRIX_COLORS,
        'background': MATRIX_BACKGROUND,
        'logo': {'default': 'syncrain', 'size': 0.34, 'glow': [0.3, 0.9, 0.6], 'glowStrength': 0.0,
                 'spin': 180, 'hueCycle': 0, 'drift': 0.03},
        'rain': dict(RAIN, bloom=2.5, cycle=55, flavours=64, flavourLayout='random'),
        'snow': SNOW,
        'snowDefault': False,
    },
    'nixos': {
        'label': 'NixOS snow',
        # the weights build 12 drew them with: each base-32 character 1, the lambda 2.6, the snowflakes
        # 0.9, 0.5 and 0.5, each Nix symbol 0.25; and hieroglyphs among 15% of them
        'glyphs': {'balance': 'sets', 'sets': [
            {'name': 'nix32', 'chars': G.NIX32, 'weight': 32},
            {'name': 'lambda', 'chars': 'λ', 'weight': 2.6},
            {'name': 'snowflake', 'chars': '❄', 'weight': 0.9},
            {'name': 'snowflakes', 'chars': '❅❆', 'weight': 1.0},
            {'name': 'symbols', 'chars': G.NIX_SYMS, 'weight': 3.0},
            {'name': 'hieroglyphs', 'chars': G.HIEROGLYPHS + G.HIEROGLYPHS_MORE, 'share': 0.15}]},
        'wordText': ['NIXOS', 'FLAKE', 'NIXPKGS', 'LAMBDA', 'DERIVATION', 'DECLARATIVE', 'REPRODUCIBLE', 'HYDRA',
                     'OVERLAY', 'ROLLBACK'],
        'colors': {'deep': rgb('#132a52'), 'mid': rgb('#3d6ed2'), 'pale': rgb('#8cc0ee'),
                   'head': rgb('#eef7ff'), 'glow': rgb('#2858b8')},
        'background': {'mode': 'gradient', 'top': rgb('#03050a'), 'bottom': rgb('#060b14'),
                       'center': rgb('#0a1a33'), 'vignette': 0.55},
        'logo': {'default': 'white', 'size': 0.40, 'glow': rgb('#7ebae4'), 'glowStrength': 0.22,
                 'spin': 180, 'hueCycle': 90, 'drift': 0.03},
        'rain': dict(RAIN, bloom=1.0),
        'snow': SNOW,
        'snowDefault': True,
    },
    'matrix': {
        'label': 'Matrix green',
        'glyphs': MATRIX_GLYPHS,
        'wordText': ['AI', 'NEURAL', 'TENSOR', 'AGENT', 'LINUX', 'ONLINE', 'MATRIX'],
        'colors': MATRIX_COLORS,
        'background': MATRIX_BACKGROUND,
        'logo': {'default': 'none', 'size': 0.40, 'glow': [0.3, 0.9, 0.6], 'glowStrength': 0.0,
                 'spin': 180, 'hueCycle': 90, 'drift': 0.03},
        'rain': dict(RAIN, bloom=1.25),
        'snow': SNOW,
        'snowDefault': False,
    },
}

meta = {
    'contract': 'syncrain-themes-3',   # the file's format; a reader checks it, a build number is not it
    'epoch0': 1704067200,          # 2024-01-01T00:00:00Z; time is passed as whole seconds since this + fraction
    'cols': 64,
    'library': {'file': 'glyphs.png', 'grid': G.GRID, 'slot': G.SLOT, 'cell': G.CELL,
                'glyphs': [k for k, _, _ in library]},
    'themes': themes,
    'default': 'syncrain',          # the preset with nothing said
}
for name, theme in themes.items():                    # every symbol a theme names is shipped
    for s in theme['glyphs']['sets']:
        for ch in s['chars']:
            assert G.spec_key(ch, s.get('mirror', False)) in meta['library']['glyphs'], (name, ch)
    for word in theme['wordText']:                    # the words texture holds 8 bits (the page's slots)
        assert all(meta['library']['glyphs'].index(ch) < 256 for ch in word), word
with open(os.path.join(args.out, 'themes.json'), 'w', encoding='utf-8') as fh:
    json.dump(meta, fh, ensure_ascii=False, separators=(',', ':'))

# ---- official NixOS logo, rasterised, with colour bled outward under the transparent area
for variant, svg in (('white', 'nix-snowflake-white.svg'), ('colours', 'nix-snowflake-colours.svg')):
    if not args.nixos_artwork:
        break
    import cv2
    import numpy as np
    logo_dir = os.path.join(args.nixos_artwork, 'logo')
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

print(f'{len(library)} glyphs in {rows} rows, themes: {", ".join(themes)}')
