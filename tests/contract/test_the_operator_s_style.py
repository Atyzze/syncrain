"""How this project writes, as the operator asked for it.

* No long dashes in anything written to them or kept in the tree: a hyphen, a comma, a
  semicolon or a full stop (their standing preference, and GSD's rule).
* The operator is "the operator" or "they", never a gendered pronoun.
* Comments say why, not when: a comment does not open with a build label; the history is in
  the notes and `docs/HISTORY.md`. A build number inside a sentence, where it carries meaning,
  is fine.
"""
from __future__ import annotations

import re

from tests.support import our_text_files

LONG_DASHES = ("\u2014", "\u2013")   # em dash, en dash
PRONOUN = re.compile(r"\b(he|He|him|Him|his|His|himself|she|She|her|Her|herself)\b")
LABEL = re.compile(r"^\s*(?:#+|//+|/\*+)\s*:?\s*(?:Builds?\s+)?\d+[a-z]?(?:\s*(?:,|and|to|&|/)\s*\d+)*\s*[:.]\s")


def test_no_long_dashes(root):
    found = []
    for path in our_text_files():
        for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if any(d in line for d in LONG_DASHES):
                found.append(f"{path.relative_to(root)}:{n}: {line.strip()[:90]}")
    assert not found, "use - , ; or . instead:\n" + "\n".join(found)


def test_the_operator_is_they(root):
    found = []
    for path in our_text_files():
        if path.name == "test_the_operator_s_style.py":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if PRONOUN.search(line):
                found.append(f"{path.relative_to(root)}:{n}: {line.strip()[:90]}")
    assert not found, 'say "the operator" or "they":\n' + "\n".join(found)


def test_comments_say_why_not_when(root):
    found = []
    for path in our_text_files():
        if path.suffix not in {".py", ".sh", ".nix", ".glsl", ".frag", ".vert", ".js"} and path.name != "template.html":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if LABEL.match(line):
                found.append(f"{path.relative_to(root)}:{n}: {line.strip()[:90]}")
    assert not found, "comments that open with a build label:\n" + "\n".join(found)


def test_the_label_rule_refuses_a_label_and_spares_a_sentence():
    for label in ("# Build 2: the launcher", "# 3: gone", "// Build 12. why", "# Builds 4 and 5: both"):
        assert LABEL.match(label), label
    for sentence in ("# Build 2 started the unpacked copy", "# 30 fps is the cap", "# 64 columns: why"):
        assert not LABEL.match(sentence), sentence
