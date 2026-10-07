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


def test_no_stream_file_moved_since_the_freeze(root):
    was = recorded(root)["files"]
    now = build.file_digests()
    moved = [name for name in build.STREAM_FILES if was[name] != now[name]]
    assert not moved, ("the stream changed: " + ", ".join(moved) + ". If that is the intent, run "
                       "`python3 tools/stream_freeze.py --write` and say so in the build's notes.")


def test_the_fingerprint_people_compare_is_the_frozen_one(root):
    assert recorded(root)["stream"] == build.stream_fingerprint()
