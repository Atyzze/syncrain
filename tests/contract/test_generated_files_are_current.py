"""Generated files are what their generator makes of the tree, byte for byte.

`web/index.html` and `web/artifact.html` carry the shaders, the themes, the images and the build's
identity inline. A page built before a shader edit, or before the release wrote the build number,
would draw another stream or claim another build; the release rebuilds them, and this refuses a
tree where they drifted.
"""
from __future__ import annotations

import importlib.util


def load_builder(root):
    spec = importlib.util.spec_from_file_location("build_web", root / "tools/build_web.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_web_pages_are_current(root):
    pages = load_builder(root).pages()
    for name, text in pages.items():
        committed = (root / "web" / name).read_text(encoding="utf-8")
        assert committed == text, f"web/{name} is stale: run `python3 tools/build_web.py`"


def test_the_pages_say_this_build_and_this_stream(root):
    from syncrain import build
    page = (root / "web/index.html").read_text(encoding="utf-8")
    assert f"Build {build.BUILD_NUMBER} · stream {build.stream_id()}" in page
    assert f"const BUILD = {build.BUILD_NUMBER}, STREAM = '{build.stream_id()}'" in page
