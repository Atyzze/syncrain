"""Every fact has one home, and every pointer to a home lands.

The README is a directory: where to look, and the few things that cost you if you get them wrong.
A second copy of a fact is a copy that goes stale without anything failing, so the recipes live in
`docs/OPERATIONS.md` only, and a document that names a file names one that exists.
"""
from __future__ import annotations

import re

from syncrain.app import parse_args

CANONICAL = {"ARCHITECTURE.md", "HISTORY.md", "LESSONS.md", "OPERATIONS.md", "ROADMAP.md", "WHERE_WE_ARE.md"}
AGENT = {"ENVIRONMENT.md", "HANDOFF.md", "NEXT_BUILD.md", "TARGET_ENVIRONMENT.md", "WORKING_WITH_THE_OPERATOR.md"}
#: A path in backticks that starts in one of these is a pointer and must resolve.
POINTER = re.compile(r"`((?:docs|tools|tests|syncrain|nix|web|extras)/[A-Za-z0-9_./-]*[A-Za-z0-9_/])`")


def documents(root):
    return [root / "README.md", *sorted((root / "docs").glob("*.md")), *sorted((root / "docs/agent").glob("*.md"))]


def test_the_documents_are_the_canonical_set(root):
    assert {p.name for p in (root / "docs").glob("*.md")} == CANONICAL
    assert {p.name for p in (root / "docs/agent").glob("*.md")} == AGENT
    notes = {p.name for p in (root / "docs/build_notes").glob("*")}
    assert notes and all(re.fullmatch(r"BUILD\d+_NOTES\.md", n) for n in notes), notes
    for retired in ("CHANGELOG.md", "START_HERE.md", "docs/CHANGELOG.md"):
        assert not (root / retired).exists(), f"{retired}: a second front door is how two copies drift apart"


def test_every_pointer_in_the_documents_lands(root):
    broken = []
    for doc in documents(root):
        for n, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for target in POINTER.findall(line):
                if not (root / target).exists():
                    broken.append(f"{doc.relative_to(root)}:{n} -> {target}")
    assert not broken, "dangling pointers:\n" + "\n".join(broken)


def test_every_command_line_option_is_documented_in_one_place(root):
    """Read the options from --help itself, so a new flag without a line in OPERATIONS.md fails."""
    import contextlib
    import io

    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.suppress(SystemExit):
        parse_args(["--help"])
    options = sorted(set(re.findall(r"(?<![\w-])(--[a-z][a-z-]+)", out.getvalue())) - {"--help"})
    assert "--theme" in options and "--diagnose" in options, options
    operations = (root / "docs/OPERATIONS.md").read_text(encoding="utf-8")
    missing = [o for o in options if f"`{o}" not in operations]
    assert not missing, f"options with no line in docs/OPERATIONS.md: {missing}"
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "| `--theme`" not in readme, "the options table lives in docs/OPERATIONS.md, not a second copy in the README"


def test_build_notes_end_in_their_verification(root):
    for notes in sorted((root / "docs/build_notes").glob("BUILD*_NOTES.md")):
        text = notes.read_text(encoding="utf-8")
        assert re.search(r"^# Build \d+: ", text, re.M), f"{notes.name}: '# Build <N>: what it did'"
        assert "## Verification" in text, notes.name
