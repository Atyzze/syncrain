#!/usr/bin/env python3
"""Inline the shaders, theme tables, images and the build's identity into self-contained pages:

  web/index.html     full HTML document: open it in a browser or point a web-wallpaper host at it
                     (works from file:// because nothing is fetched at runtime)
  web/artifact.html  the same page without the document skeleton, for hosts that wrap it themselves

Both are generated files: tools/package_release.py rebuilds them after it writes the build number,
and the gate fails when the committed pages differ from what this script makes of the tree
(`tests/contract/test_generated_files_are_current.py`).
"""
import base64
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DATA = os.path.join(ROOT, 'syncrain', 'data')
SH = os.path.join(DATA, 'shaders')
sys.path.insert(0, ROOT)
from syncrain import build  # noqa: E402

SHADER_FILES = {'common': 'common.glsl', 'rain': 'rain.glsl', 'vert': 'fullscreen.vert', 'state': 'state.frag',
                'field': 'field.frag', 'glyphs': 'glyphs.frag', 'blur': 'blur.frag', 'composite': 'composite.frag'}


def read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def pages():
    """{file name: text} for both pages, from the tree as it is now."""
    shaders = {name: read(os.path.join(SH, fname)) for name, fname in SHADER_FILES.items()}
    meta = json.loads(read(os.path.join(DATA, 'themes.json')))
    images = {}
    for name in ('atlas', 'logo-white', 'logo-colours'):
        with open(os.path.join(DATA, name + '.png'), 'rb') as fh:
            images[name] = 'data:image/png;base64,' + base64.b64encode(fh.read()).decode('ascii')

    tpl = read(os.path.join(ROOT, 'web', 'template.html'))
    tpl = tpl.replace('/*@META@*/null', json.dumps(meta, ensure_ascii=False, separators=(',', ':')))
    tpl = tpl.replace('/*@SHADERS@*/null', json.dumps(shaders))
    tpl = tpl.replace('/*@IMAGES@*/null', json.dumps(images))
    tpl = tpl.replace('/*@BUILD@*/0', str(build.BUILD_NUMBER)).replace('/*@STREAM@*/', build.stream_id())
    tpl = tpl.replace('@BUILD@', str(build.BUILD_NUMBER)).replace('@STREAM@', build.stream_id())
    head = re.search(r'<!--@HEAD-->\n(.*?)<!--@/HEAD-->', tpl, re.S).group(1)
    body = re.search(r'<!--@BODY-->\n(.*?)<!--@/BODY-->', tpl, re.S).group(1)

    full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + head + '</head>\n<body>\n' + body + '</body>\n</html>\n')
    return {'index.html': full, 'artifact.html': head + body}


def main():
    for name, text in pages().items():
        out = os.path.join(ROOT, 'web', name)
        with open(out, 'w', encoding='utf-8') as fh:
            fh.write(text)
        print(f'wrote web/{name} ({os.path.getsize(out) / 1024:.0f} KiB)')


if __name__ == '__main__':
    main()
