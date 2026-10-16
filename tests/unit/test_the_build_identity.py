"""A tree knows one number about itself, and says which stream it draws."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys

from syncrain import build


def test_the_build_number_is_the_file_beside_the_package(root):
    assert build.BUILD_NUMBER == int((root / "BUILD_NUMBER").read_text().strip())


def test_the_stream_id_is_the_start_of_the_fingerprint():
    assert re.fullmatch(r"[0-9a-f]{64}", build.stream_fingerprint())
    assert build.stream_id() == build.stream_fingerprint()[:8]
    assert build.describe() == f"syncrain build {build.BUILD_NUMBER} (stream {build.stream_id()})"


def test_any_stream_file_moving_moves_the_fingerprint():
    digests = build.file_digests()
    for name in build.STREAM_FILES:
        changed = dict(digests, **{name: "0" * 64})
        assert build.fingerprint_of(changed) != build.fingerprint_of(digests), name


def test_the_stream_is_what_the_code_computes_not_how_it_is_written(root):
    """No source file is a stream file (a comment changed the stream before build 44); what the code
    computes is, written in data/stream-reference.json: every preset's scene with and without the
    settings that change it, and its grid at every --scale."""
    assert not [f for f in build.STREAM_FILES if f.endswith(".py")]
    assert "data/stream-reference.json" in build.STREAM_FILES
    from syncrain import engine, stream
    parts = stream.written(root / "syncrain/data/stream-reference.json")
    for name in engine.load_meta()["themes"]:
        assert f"grid:{name}" in parts and all(f"scene:{name}:{s}" in parts for s in stream.SETTINGS)
    assert {"clock", "seed", "fit"} <= set(parts)
    assert 0.3 in stream.SCALES and (1680, 1050) in stream.SIZES


def test_the_reference_draws_nothing_with_this_machine_s_fonts(monkeypatch):
    """Every symbol it uses is in the shipped atlas: a font of this machine's in it would make the
    stream id this machine's."""
    from syncrain import glyphs, stream

    def no_fonts(*_a, **_k):
        raise AssertionError("the reference asked for this machine's fonts")
    monkeypatch.setattr(glyphs, "font_list", no_fonts)
    assert stream.reference()


def test_a_package_with_neither_file_nor_metadata_refuses_to_guess(tmp_path, root):
    """Copied out of its tree and never installed, the package cannot know its build, and says so."""
    shutil.copytree(root / "syncrain", tmp_path / "syncrain", ignore=shutil.ignore_patterns("__pycache__"))
    probe = subprocess.run([sys.executable, "-c", "import syncrain.build"], cwd=tmp_path, capture_output=True,
                           text=True, env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(tmp_path),
                                           "PYTHONNOUSERSITE": "1"})
    assert probe.returncode != 0
    assert "cannot tell which syncrain build this is" in probe.stderr


def test_the_command_line_says_the_build_and_never_a_version(root):
    def run(*args):
        return subprocess.run([sys.executable, "-m", "syncrain", *args], cwd=root, capture_output=True, text=True,
                              timeout=60)
    built, reflex, helped = run("--build"), run("--version"), run("--help")
    assert built.returncode == 0 and built.stdout.strip() == build.describe()
    assert reflex.stdout == built.stdout, "--version is only the reflex spelling of --build"
    assert "--build" in helped.stdout
    assert "version" not in helped.stdout.lower()


def test_a_lower_scale_draws_the_same_grid():
    """--scale below 1 draws fewer pixels, not another picture: the rows and where the columns start
    are the scale of 1's, to the rounding of the pixels drawn (below about 0.4 the smallest cell was
    taken in the pixels drawn)."""
    from syncrain import engine
    cols = engine.load_meta()["cols"]
    for w, h in ((1920, 1080), (1280, 720), (800, 450), (390, 844)):
        full = engine.geometry(w, h, cols)
        for scale in (0.5, 0.3, 0.25):
            low = engine.geometry(round(w * scale), round(h * scale), cols, scale)
            assert abs(low["col0"] - full["col0"]) < 0.2 and abs(low["rows"] - full["rows"]) <= 1, (w, h, scale)
