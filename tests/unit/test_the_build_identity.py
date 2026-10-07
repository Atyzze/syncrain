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
