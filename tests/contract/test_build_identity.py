"""One tree, one number: a build number, its notes and nothing that looks like a version.

The operator, delivering build 3's request: "a clear build number (instead of these versionings
.... stop, no 'versions', only build numbers)". Builds 1 and 2 were both delivered as
`syncrain-0.1.0.tar.gz`: two different trees under one name, which is the failure a number per
archive exists to prevent. `tools/package_release.py` writes the number; everything else reads it.
"""
from __future__ import annotations

import re
import tomllib

from tests.support import our_text_files

NOTES = "docs/build_notes"


def current(root) -> int:
    return int((root / "BUILD_NUMBER").read_text(encoding="utf-8").strip())


def test_the_build_number_file_is_one_integer(root):
    assert re.fullmatch(r"[1-9][0-9]*\n", (root / "BUILD_NUMBER").read_text(encoding="utf-8"))


def test_the_packaging_metadata_reads_the_build_number(root):
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert "version" not in project["project"], "pyproject must not carry a second copy of the number"
    assert project["project"]["dynamic"] == ["version"]
    assert project["tool"]["setuptools"]["dynamic"]["version"] == {"file": "BUILD_NUMBER"}


def test_nix_reads_the_build_number(root):
    for name in ("nix/package.nix", "nix/web.nix"):
        assert "lib.fileContents ../BUILD_NUMBER" in (root / name).read_text(encoding="utf-8"), name


#: What a version string looks like in this tree's history. Notes and the history may quote it.
#: (Reading a library's own __version__ to report it is fine; giving syncrain one is not.)
VERSIONISH = re.compile(r"^\s*__version__\s*=|\b0\.1\.0\b|syncrain-\d+\.\d+")


def test_nothing_in_the_tree_carries_a_version(root):
    exempt = {"tests/contract/test_build_identity.py", "docs/HISTORY.md", "docs/LESSONS.md"}
    found = []
    for path in our_text_files():
        rel = path.relative_to(root).as_posix()
        if rel in exempt or rel.startswith(NOTES + "/"):
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if VERSIONISH.search(line):
                found.append(f"{rel}:{n}: {line.strip()[:100]}")
    assert not found, "build numbers only:\n" + "\n".join(found)


def test_this_build_has_notes(root):
    notes = root / NOTES / f"BUILD{current(root)}_NOTES.md"
    assert notes.is_file(), (f"no {notes.name} for BUILD_NUMBER {current(root)}: write the notes in the same "
                             "pass as the build, or the number was bumped without a build behind it")
    body = notes.read_text(encoding="utf-8")
    assert len(body.strip()) > 400, f"{notes.name} is a stub"
    assert "## Verification" in body, f"{notes.name} says nothing about what was run"


def declared_predecessor(root, number: int):
    notes = root / NOTES / f"BUILD{number}_NOTES.md"
    if not notes.is_file():
        return None
    match = re.search(r"^Follows build:\s*(\d+)\s*$", notes.read_text(encoding="utf-8"), re.M)
    return int(match.group(1)) if match else None


def test_the_previous_build_also_has_notes(root):
    """A gap means a number was spent without a build, or a build shipped without an account of itself."""
    build = current(root)
    if build == 1:
        return
    declared = declared_predecessor(root, build)
    previous = build - 1 if declared is None else declared
    assert previous < build
    assert (root / NOTES / f"BUILD{previous}_NOTES.md").is_file(), f"no BUILD{previous}_NOTES.md"


def test_no_notes_run_more_than_one_build_ahead(root):
    """One ahead is a build being made (the tree carries the last released number until the release
    writes the new one); two ahead is a skipped number or a release that never happened."""
    ahead = sorted(int(m.group(1)) for p in (root / NOTES).glob("BUILD*_NOTES.md")
                   if (m := re.fullmatch(r"BUILD(\d+)_NOTES\.md", p.name)) and int(m.group(1)) > current(root) + 1)
    assert not ahead, f"notes more than one build ahead of BUILD_NUMBER {current(root)}: {ahead}"
