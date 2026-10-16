"""The stream is the promise: same channel, same second, same frame, on every machine of a build.

A change to a file that decides the picture changes the stream, and machines on this build stop
matching machines on the last one. That is allowed only on purpose: re-take the freeze with
`python3 tools/stream_freeze.py --write` and say in the build's notes that the stream changed.
"""
from __future__ import annotations

import json

from syncrain import build


def recorded(root) -> dict:
    return json.loads((root / "tests/fixtures/stream_freeze.json").read_text(encoding="utf-8"))


def test_the_freeze_names_exactly_the_stream_files(root):
    assert sorted(recorded(root)["files"]) == sorted(build.STREAM_FILES)
    for name in build.STREAM_FILES:
        assert (root / "syncrain" / name).is_file(), name


def test_nothing_that_decides_the_stream_moved_since_the_freeze(root):
    """The files, and what the code computes against stream-reference.json (seconds: scenes)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("stream_freeze", root / "tools/stream_freeze.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    moved = tool.drift(recorded(root))
    assert not moved, ("the stream changed: " + ", ".join(moved) + ". If that is the intent, run "
                       "`python3 tools/stream_freeze.py --write` and say so in the build's notes.")


def test_the_fingerprint_people_compare_is_the_frozen_one(root):
    assert recorded(root)["stream"] == build.stream_fingerprint()
