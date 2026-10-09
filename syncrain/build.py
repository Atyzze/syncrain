"""Which build this is, and which stream it draws.

The build number is the only identity a syncrain tree has. It lives in `BUILD_NUMBER` at the
root of the tree; an installed wheel carries it as its package metadata instead. There are no
version strings: every archive that leaves the build machine has its own number, written by
`tools/package_release.py` and by nothing else.

The stream fingerprint names what decides the picture at a given second: the shaders, the
themes, the glyph atlas, the logos, and the code that turns a channel name and the clock into
shader inputs. Two machines draw the same frame exactly when their fingerprints match and
their clocks agree, so it is shown beside the build (`syncrain --build`, the web page's footer).
`tests/fixtures/stream_freeze.json` holds the fingerprint the tree promises; a change to any
of these files fails the gate until the freeze is re-taken on purpose
(`python3 tools/stream_freeze.py --write`) and the build's notes say the stream changed.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent
BUILD_FILE = ROOT / "BUILD_NUMBER"


def _read_build_number() -> int:
    if BUILD_FILE.is_file():
        return int(BUILD_FILE.read_text(encoding="utf-8").strip())
    # An installed wheel: the packaging metadata field holds the build number. Its METADATA file
    # sits beside the package; read there, it costs nothing, where importlib.metadata brings the
    # email package and a few mebibytes with it, so that is only the fallback.
    found = list(PACKAGE.parent.glob("syncrain-*.dist-info/METADATA"))
    if len(found) == 1:                      # more than one is a broken install: let importlib decide
        for line in found[0].read_text(encoding="utf-8").splitlines():
            if line.startswith("Version:"):
                return int(line.split(":", 1)[1].strip().split(".", 1)[0])
    from importlib.metadata import PackageNotFoundError, version as _distribution_field
    try:
        return int(_distribution_field("syncrain").split(".", 1)[0])
    except (PackageNotFoundError, ValueError) as exc:
        raise RuntimeError("cannot tell which syncrain build this is: "
                           "no BUILD_NUMBER beside the package and no package metadata") from exc


BUILD_NUMBER = _read_build_number()

#: What decides the stream, relative to the package. A file that changes what a frame looks
#: like at a given second belongs here; one that only changes how the app runs does not.
STREAM_FILES = (
    "engine.py",
    "data/themes.json",
    "data/atlas.png",
    "data/logo-white.png",
    "data/logo-colours.png",
    "data/shaders/common.glsl",
    "data/shaders/state.frag",
    "data/shaders/field.frag",
    "data/shaders/rain.glsl",
    "data/shaders/glyphs.frag",
    "data/shaders/blur.frag",
    "data/shaders/composite.frag",
    "data/shaders/fullscreen.vert",
)
STREAM_CONTRACT = b"syncrain-stream-1\n"


def file_digests(package: Path = PACKAGE) -> dict[str, str]:
    return {rel: hashlib.sha256((package / rel).read_bytes()).hexdigest() for rel in STREAM_FILES}


def fingerprint_of(digests: dict[str, str]) -> str:
    digest = hashlib.sha256(STREAM_CONTRACT)
    for rel in STREAM_FILES:
        digest.update(rel.encode() + b"\0" + bytes.fromhex(digests[rel]))
    return digest.hexdigest()


@lru_cache(maxsize=1)
def stream_fingerprint() -> str:
    return fingerprint_of(file_digests())


def stream_id() -> str:
    """The short form people compare: the first eight hex digits."""
    return stream_fingerprint()[:8]


def describe() -> str:
    return f"syncrain build {BUILD_NUMBER} (stream {stream_id()})"
