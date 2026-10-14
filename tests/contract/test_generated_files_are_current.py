"""Generated files are what their generator makes of the tree, byte for byte.

`index.html` carries the shaders, the presets, the images and the build's identity inline. A page
filled before a shader edit, or before the release wrote the build number, would draw another
stream or claim another build; the release fills it, and this refuses a tree where it drifted.
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
        committed = (root / name).read_text(encoding="utf-8")
        assert committed == text, f"{name} is stale: run `python3 tools/build_web.py`"


def test_the_pages_say_this_build_and_this_stream(root):
    from syncrain import build
    page = (root / "index.html").read_text(encoding="utf-8")
    assert f"const BUILD = /*@BUILD*/{build.BUILD_NUMBER}/*@/BUILD*/, STREAM = /*@STREAM*/\"{build.stream_id()}\"/*@/STREAM*/" in page


def test_the_live_page_is_the_page_without_its_document(root):
    builder = load_builder(root)
    text = (root / "index.html").read_text(encoding="utf-8")
    live = builder.artifact(text)
    assert live.startswith("<title>Syncrain</title>") and "<!doctype" not in live.lower() and "</body>" not in live
    assert "const META = /*@META*/{" in live
