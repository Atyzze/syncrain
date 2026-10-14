#!/usr/bin/env python3
"""Fill `index.html` (at the top of the tree) with what it draws from, in place:

  the shaders, the presets and the glyph table (syncrain/data/themes.json), the images, the
  starter symbol sets, and the build's number and stream id, each between its markers
  (/*@NAME*/ ... /*@/NAME*/) in the page's script.

`index.html` is one self-contained file: open it in a browser, or point a web-wallpaper host at it
(it fetches nothing at runtime). It is also the page's source; to edit it with its data out of the
way:

  python3 tools/build_web.py --strip     # the blocks emptied (a few hundred lines to read)
  ...edit...
  python3 tools/build_web.py             # filled again

The live page (claude.ai) wraps a page in its own document, so it is published from
`python3 tools/build_web.py --artifact <file>`: the page's head and body without the document.

tools/package_release.py fills it after it writes the build number, and the gate fails when the
committed page differs from what this script makes of the tree
(`tests/contract/test_generated_files_are_current.py`).
"""
import argparse
import base64
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
PAGE = os.path.join(ROOT, 'index.html')
DATA = os.path.join(ROOT, 'syncrain', 'data')
SH = os.path.join(DATA, 'shaders')
sys.path.insert(0, ROOT)
from syncrain import build, glyphs  # noqa: E402

SHADER_FILES = {'common': 'common.glsl', 'rain': 'rain.glsl', 'vert': 'fullscreen.vert', 'state': 'state.frag',
                'field': 'field.frag', 'glyphs': 'glyphs.frag', 'blur': 'blur.frag', 'composite': 'composite.frag'}
BLOCK = re.compile(r'/\*@([A-Z]+)\*/(.*?)/\*@/\1\*/', re.S)


def read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def blocks():
    """{marker: the text between its markers}, from the tree as it is now."""
    shaders = {name: read(os.path.join(SH, fname)) for name, fname in SHADER_FILES.items()}
    meta = json.loads(read(os.path.join(DATA, 'themes.json')))
    images = {}
    for name in ('glyphs', 'logo-white', 'logo-colours', 'logo-syncrain'):
        with open(os.path.join(DATA, name + '.png'), 'rb') as fh:
            images[name] = 'data:image/png;base64,' + base64.b64encode(fh.read()).decode('ascii')
    compact = dict(ensure_ascii=False, separators=(',', ':'))
    return {'META': json.dumps(meta, **compact), 'SHADERS': json.dumps(shaders), 'IMAGES': json.dumps(images),
            'STARTER': json.dumps(glyphs.starter()['sets'], **compact), 'BUILD': str(build.BUILD_NUMBER),
            'STREAM': json.dumps(build.stream_id())}


def fill(text, stripped=False):
    """The page with every block filled (or emptied: null, 0 or '')."""
    made = blocks()
    empty = {'BUILD': '0', 'STREAM': "''"}

    def put(m):
        name = m.group(1)
        if name not in made:
            raise SystemExit(f'index.html: no block {name} is known')
        value = empty.get(name, 'null') if stripped else made[name]
        return f'/*@{name}*/{value}/*@/{name}*/'
    out, n = BLOCK.subn(put, text)
    if n != len(made):
        raise SystemExit(f'index.html: {n} blocks, expected {len(made)}')
    return out


def pages():
    """{file name at the top of the tree: its text}, filled from the tree as it is now."""
    return {'index.html': fill(read(PAGE))}


def artifact(text):
    """The page's head and body without the document around them, for a host that wraps it."""
    head = re.search(r'<!--@HEAD-->\n(.*?)<!--@/HEAD-->', text, re.S).group(1)
    body = re.search(r'<!--@BODY-->\n(.*?)<!--@/BODY-->', text, re.S).group(1)
    return head + body


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--strip', action='store_true', help='empty the blocks, for editing the page')
    ap.add_argument('--artifact', metavar='FILE', help='also write the page without its document, for the live page')
    args = ap.parse_args()
    text = fill(read(PAGE), stripped=args.strip)
    with open(PAGE, 'w', encoding='utf-8') as fh:
        fh.write(text)
    print(f'{"emptied" if args.strip else "filled"} index.html ({os.path.getsize(PAGE) / 1024:.0f} KiB)')
    if args.artifact:
        with open(args.artifact, 'w', encoding='utf-8') as fh:
            fh.write(artifact(text))
        print(f'wrote {args.artifact}')


if __name__ == '__main__':
    main()
