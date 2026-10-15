"""The web page checks symbol sets and shares them out with its own JavaScript (index.html:
checkGlyphs, setShares); the desktop with syncrain/glyphs.py (check_config, set_shares). The page's
own functions, taken from index.html as they are, run in Node on the same sets as Python's: what one
takes the other takes, and the shares are the same. (This checked once that two lines of the page
were there.)
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from syncrain import glyphs
from tests.conftest import ROOT, need

#: The page's pieces these need, by how each starts in index.html.
PIECES = ("const own = ", "const PY_SPACE = ", "const PY_BLANK = ", "const charsOf = ",
          "function pyRepr(", "function checkGlyphs(", "function setShares(")

CASES = [
    {"sets": [{"name": "a", "chars": "ABC"}]},
    {"sets": [{"name": "a", "chars": "AB", "weight": 3}, {"name": "b", "chars": "xyz", "weight": 1}]},
    {"balance": "glyphs", "sets": [{"name": "a", "chars": "AB"}, {"name": "b", "chars": "xyz"}]},
    {"sets": [{"name": "a", "chars": "AB", "share": 0.25}, {"name": "b", "chars": "xyz"}]},
    {"sets": [{"name": "a", "chars": "AB", "share": 0.6}, {"name": "b", "chars": "x", "share": 0.4},
              {"name": "c", "chars": "q"}]},
    {"sets": [{"name": "a", "chars": "AB", "weight": 0}, {"name": "b", "chars": "x", "weight": 0}]},
    {"sets": [{"name": "katakana", "chars": glyphs.KATAKANA, "weight": 135, "mirror": True},
              {"name": "hieroglyphs", "chars": glyphs.HIEROGLYPHS, "share": 0.15},
              {"name": "latin", "chars": glyphs.UPPER + glyphs.LOWER, "weight": 8}]},
    {"sets": [{"name": "a", "chars": "A A\tA", "weight": 1}]},
    {"sets": []},
    {"sets": [{"name": "x"}]},
    {"sets": [{"name": "x", "chars": "   "}]},
    {"sets": [{"name": "x", "chars": "a", "weight": -1}]},
    {"sets": [{"name": "x", "chars": "a", "share": 0.7}, {"name": "y", "chars": "b", "share": 0.5}]},
    {"balance": "evenly", "sets": [{"chars": "a"}]},
    # what the refusal says, as Python's repr says it, for values that are no text too
    *({"balance": b, "sets": [{"chars": "a"}]} for b in
      (True, False, None, 3, 1e-07, 2.5e+300, [1, "x"], {"k": None}, "it's", 'say "hi"', "a\\b\n\x01\x7f", "")),
    {"sets": [{"name": "x", "chars": "a", "mirror": "yes"}]},
    {"sets": [{"name": 5, "chars": "a"}]},
    {"sets": [{"name": "x", "chars": "a", "size": 3}]},
    {"sets": [{"name": f"s{i}", "chars": "a"} for i in range(17)]},
]
HIEROGLYPHS = [None, 0.0, 0.5, 1.0]


def page_source() -> str:
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    out = []
    for start in PIECES:
        i = page.index("\n" + start) + 1
        end = page.index("\n", i) if start.startswith("const ") else page.index("\n}\n", i) + 2
        out.append(page[i:end])
    return "\n".join(out)


def run_page(cases) -> list:
    script = page_source() + r"""
const cases = JSON.parse(require("fs").readFileSync(0, "utf8"));
const out = cases.map(([g, h]) => {
  try {
    const checked = checkGlyphs(g, "the symbols");
    return { ok: true, shares: setShares(checked, h) };
  } catch (e) { return { ok: false, error: e.message }; }
});
process.stdout.write(JSON.stringify(out));
"""
    done = subprocess.run(["node", "-e", script], input=json.dumps(cases), capture_output=True, text=True,
                          timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def run_python(g, h) -> dict:
    try:
        checked = glyphs.check_config(json.loads(json.dumps(g)), "the symbols")
    except glyphs.GlyphsError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "shares": glyphs.set_shares(checked, h)}


def test_the_page_takes_and_shares_out_symbol_sets_as_the_desktop_does():
    need(shutil.which("node") is not None, "no Node")
    cases = [[g, h] for g in CASES for h in HIEROGLYPHS]
    for (g, h), page in zip(cases, run_page(cases)):
        desktop = run_python(g, h)
        assert page["ok"] == desktop["ok"], (g, h, page, desktop)
        if desktop["ok"]:
            assert page["shares"] == pytest.approx(desktop["shares"], abs=1e-12), (g, h)
        else:
            assert page["error"] == desktop["error"], (g, h)


def test_the_page_s_pieces_are_found():
    source = page_source()
    assert all(re.search(re.escape(p), source) for p in PIECES)
