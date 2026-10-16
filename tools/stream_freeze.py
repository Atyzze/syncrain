#!/usr/bin/env python3
"""Check, or deliberately re-take, the stream freeze.

The stream is what every machine on a channel agrees on: at a given second, the same frame.
`tests/fixtures/stream_freeze.json` records the files that decide it (`syncrain.build.STREAM_FILES`),
among them `syncrain/data/stream-reference.json`: what the code computes (`syncrain/stream.py`),
part by part. The check computes that again, so a change to the code's results is caught as a
change to a file would be. The gate fails when any of it changes, because a changed stream means a
machine on this build and one on the previous build stop drawing the same picture.

    python3 tools/stream_freeze.py            # check; exit 1 and name the parts that moved
    python3 tools/stream_freeze.py --write    # re-take it, on purpose; say so in the build's notes

Re-taking it is how a build changes the picture. It is never done to make a test pass.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from syncrain import build, stream  # noqa: E402

FREEZE = ROOT / "tests" / "fixtures" / "stream_freeze.json"
REFERENCE = ROOT / "syncrain" / "data" / "stream-reference.json"
CONTRACT = "syncrain-stream-freeze-2"


def current() -> dict:
    digests = build.file_digests()
    return {"contract": CONTRACT, "stream": build.fingerprint_of(digests), "files": digests}


def computed_drift() -> list[str]:
    """What the code computes now against what stream-reference.json says it computed."""
    was, now = stream.written(REFERENCE), stream.reference()
    moved = [f"computed: {part}" for part in sorted(now) if was.get(part) != now[part]]
    return moved + [f"computed: {part} (no longer computed)" for part in sorted(set(was) - set(now))]


def drift(recorded: dict) -> list[str]:
    now, was = current()["files"], recorded.get("files", {})
    moved = [name for name in build.STREAM_FILES if was.get(name) != now[name]]
    moved += [f"{name} (no longer a stream file)" for name in sorted(set(was) - set(now))]
    return moved + computed_drift()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="re-take the freeze at this tree's stream")
    args = ap.parse_args(argv)
    if args.write:
        stream.write(REFERENCE)
        build.stream_fingerprint.cache_clear()
        record = current()
        # Between releases the tree carries the last released number and its work is for the
        # next one, so a freeze re-taken now belongs to the build being made.
        record["taken_at_build"] = build.BUILD_NUMBER + 1
        FREEZE.parent.mkdir(parents=True, exist_ok=True)
        FREEZE.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"stream freeze re-taken: stream {record['stream'][:8]}, for build {record['taken_at_build']}")
        return 0
    recorded = json.loads(FREEZE.read_text(encoding="utf-8"))
    moved = drift(recorded)
    if moved:
        print("the stream moved since the freeze was taken; these parts changed:\n  " + "\n  ".join(moved))
        print("If that is the intent, re-take it with `python3 tools/stream_freeze.py --write` "
              "and say in the build's notes that the stream changed.")
        return 1
    print(f"stream {recorded['stream'][:8]}: unchanged since build {recorded.get('taken_at_build')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
