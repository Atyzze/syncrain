"""The app runs on the oldest Python pyproject.toml allows (requires-python), not only on the newer
one the lanes run. Python 3.12 (PEP 701) reads f-strings that 3.10 and 3.11 refuse: a backslash, a
comment or the f-string's own quotes inside a replacement field. Every file of the app is read for
those with this Python's tokenizer, and compiled by an older Python when one is here (without one,
the tokenizer's check stands for it)."""
from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import sys
import tokenize

import pytest

from tests.conftest import ROOT, need

#: f-strings, as source, and whether Python 3.10 and 3.11 refuse them (python3.11 agrees, below).
SAMPLES = {
    "f\"{'\\n'.join(a)}\"\n": True,             # a backslash in a replacement field
    "f\"{b'\\0'}\"\n": True,                     # one in a bytes literal there too (build 17's native.py)
    "f\"{d[\"k\"]}\"\n": True,                   # the f-string's own quote
    "f'{f\"{\"a\"}\"}'\n": True,                 # an enclosing f-string's quote
    "f\"\"\"{d[\"\"\"k\"\"\"]}\"\"\"\n": True,  # its own triple quotes
    "f\"\"\"{a # c\n}\"\"\"\n": True,           # a comment
    "f'{f\"\\n{x}\"}'\n": True,                  # a backslash in a nested f-string
    "f\"{d['k']}\"\n": False,
    "f\"\"\"{d[\"k\"]}\"\"\"\n": False,
    "f\"a\\n{b}\"\n": False,
    "f'{f\"{c}\"}'\n": False,
    "f\"{x:\\n}\"\n": False,
    "f\"{'''a'''}\"\n": False,
}

COMPILE = """
import sys
for path in sys.argv[1:]:
    with open(path, encoding="utf-8") as f:
        compile(f.read(), path, "exec", dont_inherit=True)
"""

VERDICTS = """
import json, sys
def refused(source):
    try:
        compile(source, "<sample>", "exec", dont_inherit=True)
    except SyntaxError:
        return True
    return False
print(json.dumps([refused(s) for s in json.load(sys.stdin)]))
"""


def oldest() -> tuple[int, int]:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    found = re.search(r'^requires-python\s*=\s*">=\s*(\d+)\.(\d+)"', text, re.M)
    assert found, "pyproject.toml names no oldest Python"
    return int(found[1]), int(found[2])


def app_files() -> list:
    return sorted(p for p in (ROOT / "syncrain").rglob("*.py") if "__pycache__" not in p.parts)


def quotes(token: str) -> str:
    """The quotes a string or an f-string opens with: ', ", ''' or \"\"\"."""
    body = token.lstrip("rRbBuUfFtT")
    return body[:3] if body[:3] in ("'''", '"""') else body[:1]


def newer_fstrings(text: str) -> list[int]:
    """The lines of f-strings that only Python 3.12 and later read (this Python's tokenizer must be
    3.12's or later: earlier ones keep an f-string as one token)."""
    found, inside = [], []                      # the quotes of the f-strings open here, outermost first
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        kind = tokenize.tok_name[tok.type]
        # Inside an f-string, every token but its own text is in a replacement field; a nested
        # f-string's text is in the field of the one around it.
        in_field = bool(inside) and (kind != "FSTRING_MIDDLE" or len(inside) > 1)
        if in_field and ("\\" in tok.string or kind == "COMMENT"):
            found.append(tok.start[0])
        elif in_field and kind in ("STRING", "FSTRING_START"):
            q = quotes(tok.string)
            if any(q[0] == outer[0] and (len(outer) == 1 or q == outer) for outer in inside):
                found.append(tok.start[0])
        if kind == "FSTRING_START":
            inside.append(quotes(tok.string))
        elif kind == "FSTRING_END":
            inside.pop()
    return sorted(set(found))


def refused_here(source: str) -> bool:
    try:
        compile(source, "<sample>", "exec", dont_inherit=True)
    except SyntaxError:
        return True
    return False


@pytest.mark.parametrize("source, refused", list(SAMPLES.items()))
def test_the_check_finds_what_the_older_pythons_refuse(source, refused):
    if sys.version_info >= (3, 12):
        assert bool(newer_fstrings(source)) == refused
    else:                                       # this Python is one of them
        assert refused_here(source) == refused


def test_the_app_has_no_f_string_only_newer_pythons_read():
    assert oldest() < (3, 12), "pyproject.toml now asks for 3.12: this check can go"
    if sys.version_info < (3, 12):
        for path in app_files():
            compile(path.read_text(encoding="utf-8"), str(path), "exec", dont_inherit=True)
        return
    found = {}
    for path in app_files():
        lines = newer_fstrings(path.read_text(encoding="utf-8"))
        if lines:
            found[str(path.relative_to(ROOT))] = lines
    assert found == {}, "f-strings Python 3.10 and 3.11 refuse (file: lines)"


def test_an_older_python_here_compiles_the_app_and_refuses_what_the_check_finds():
    major, minor = oldest()
    older = [exe for exe in (shutil.which(f"python{major}.{m}") for m in range(minor, 12)) if exe]
    need(bool(older), f"no Python {major}.{minor} to 3.11 here; the tokenizer's check stands for it")
    for exe in older:
        done = subprocess.run([exe, "-I", "-c", COMPILE, *map(str, app_files())], capture_output=True, text=True,
                              timeout=120)
        assert done.returncode == 0, f"{exe}: {done.stderr[-3000:]}"
        said = subprocess.run([exe, "-I", "-c", VERDICTS], input=json.dumps(list(SAMPLES)), capture_output=True,
                              text=True, timeout=60)
        assert json.loads(said.stdout) == list(SAMPLES.values()), f"{exe}: {said.stderr[-3000:]}"
