"""The pages a reader opens first must describe this build, and a release cannot leave them behind.

Three of these fail by one between releases and pass inside the release gate, where BUILD_NUMBER
is the build being made: `docs/agent/NEXT_BUILD.md` names the build after it, and
`docs/WHERE_WE_ARE.md` and the handoff name it. A page that must be rewritten to release is a
page that is current (GSD's rule, adopted at build 3).
"""
from __future__ import annotations

import re

EVERY = 10          # consolidation builds: every build number ending in 0
HANDOFF_MAX_LAG = 5


def current(root) -> int:
    return int((root / "BUILD_NUMBER").read_text(encoding="utf-8").strip())


def first_line(path) -> str:
    return path.read_text(encoding="utf-8").splitlines()[0].strip()


def test_the_next_build_is_named_and_is_the_next_one(root):
    line = first_line(root / "docs/agent/NEXT_BUILD.md")
    match = re.fullmatch(r"# The next build is (\d+)", line)
    assert match, f"the first line must read '# The next build is <N>'; it reads {line!r}"
    assert int(match.group(1)) == current(root) + 1, (
        f"NEXT_BUILD.md describes build {match.group(1)} and the tree is {current(root)}: "
        f"rewrite it for build {current(root) + 1}")


def test_the_next_build_page_says_how_and_what_blocks_it(root):
    body = (root / "docs/agent/NEXT_BUILD.md").read_text(encoding="utf-8")
    for needed in ("## How to make a build", "GATE_RESULT", "tools/package_release.py", "Acceptance"):
        assert needed in body, f"NEXT_BUILD.md does not mention {needed!r}"
    assert "blocker" in body.lower(), "an instruction without its known obstacles sends the reader to find them again"


def test_where_we_are_names_this_build_on_one_page(root):
    page = root / "docs/WHERE_WE_ARE.md"
    match = re.fullmatch(r"# Where we are, at build (\d+)", first_line(page))
    assert match and int(match.group(1)) == current(root), first_line(page)
    text = page.read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 80, "one page; the detail belongs in the handoff"
    for heading in ("## What syncrain is", "## Where it stands", "## What comes next",
                    "## The decision in front of you"):
        assert heading in text, heading


def test_the_readme_sends_a_reader_to_the_one_page_first(root):
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert readme.index("docs/WHERE_WE_ARE.md") < readme.index("docs/agent/HANDOFF.md")


def test_the_handoff_describes_a_recent_build(root):
    line = first_line(root / "docs/agent/HANDOFF.md")
    match = re.search(r"build\s+(\d+)", line)
    assert match, f"the handoff's first line names the build it describes; it reads {line!r}"
    described = int(match.group(1))
    assert described <= current(root), f"the handoff claims build {described}, the tree is {current(root)}"
    assert current(root) - described <= HANDOFF_MAX_LAG, "the handoff opens with 'this is what is true': rewrite it"


def cadence(root) -> str:
    roadmap = (root / "docs/ROADMAP.md").read_text(encoding="utf-8")
    assert "## Build cadence" in roadmap
    return roadmap.split("## Build cadence", 1)[1].split("\n## ", 1)[0]


def next_consolidation(build: int) -> int:
    return -(-build // EVERY) * EVERY


def test_consolidation_builds_are_every_number_ending_in_zero(root):
    section = cadence(root)
    assert re.search(r"^Consolidation builds: every build number ending in 0\b", section, re.M)
    found = re.search(r"^Next consolidation: (\d+)$", section, re.M)
    assert found and int(found.group(1)) == next_consolidation(current(root)), (
        f"the next consolidation is {next_consolidation(current(root))}; it is fixed and does not move")
    assert [next_consolidation(b) for b in (1, 9, 10, 11)] == [10, 10, 10, 20]


def test_a_build_is_a_consolidation_exactly_when_its_number_ends_in_zero(root):
    build = current(root)
    notes = root / f"docs/build_notes/BUILD{build}_NOTES.md"
    kind = re.search(r"^\*\*Type: ([^*\n]+)", notes.read_text(encoding="utf-8"), re.M)
    assert kind, f"{notes.name} must open with a '**Type: ...' line"
    assert ("consolidation" in kind.group(1).lower()) == (build % EVERY == 0), kind.group(1)
