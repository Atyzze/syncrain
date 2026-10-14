#!/usr/bin/env python3
"""Make syncrain's own logo texture, syncrain/data/logo-syncrain.png, from its drawing,
syncrain/data/logo-syncrain.svg.

The texture is made as the NixOS logos are (tools/build_assets.py): the drawing at 1024 px in the
middle two thirds of a 1536 px square, so the blurred mip levels the glow is drawn from have room,
and under its transparent pixels the drawing's own colour, so filtering at its edges brings in no
other. A new texture changes the stream (`python3 tools/stream_freeze.py --write`).

Draws with rsvg-convert (librsvg) where there is one, else with CairoSVG.

    python3 tools/build_logo.py
"""
import io
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageChops, ImageStat

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'syncrain', 'data')
SVG, PNG = os.path.join(DATA, 'logo-syncrain.svg'), os.path.join(DATA, 'logo-syncrain.png')
SIDE, PAD = 1024, 1536


def draw(svg, side):
    """The drawing as RGBA, side x side."""
    if shutil.which('rsvg-convert'):
        out = subprocess.run(['rsvg-convert', '-w', str(side), '-h', str(side), svg], capture_output=True, check=True).stdout
    else:
        import cairosvg
        out = cairosvg.svg2png(url=svg, output_width=side, output_height=side)
    return Image.open(io.BytesIO(out)).convert('RGBA')


def main():
    im = draw(SVG, SIDE)
    r, g, b, a = im.split()
    weight = ImageStat.Stat(a).sum[0] or 1
    # the drawing's alpha-weighted colour, under every pixel it leaves transparent
    colour = tuple(round(ImageStat.Stat(ImageChops.multiply(ch, a)).sum[0] * 255 / weight) for ch in (r, g, b))
    seen = a.point(lambda v: 255 if v > 0 else 0)
    rgb = Image.composite(Image.merge('RGB', (r, g, b)), Image.new('RGB', im.size, colour), seen)
    out = Image.new('RGBA', (PAD, PAD), colour + (0,))
    out.paste(Image.merge('RGBA', (*rgb.split(), a)), ((PAD - SIDE) // 2, (PAD - SIDE) // 2))
    out.save(PNG, optimize=True)
    print(f'wrote {os.path.relpath(PNG)} ({os.path.getsize(PNG) // 1024} KiB)')


if __name__ == '__main__':
    sys.exit(main())
