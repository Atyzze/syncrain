"""The symbol sets (syncrain/glyphs.py): how often each symbol falls, what goes into a wallpaper's
atlas, and what a symbols file may say. Pinned to answers worked out by hand, because the web page
(web/template.html, setShares) must compute the same."""
from __future__ import annotations

import json
from collections import Counter

import pytest

from syncrain import engine, glyphs


def resolve(cfg, theme="nixos", **kw):
    meta = engine.load_meta()
    return glyphs.resolve(meta, meta["themes"][theme], engine.DATA_DIR, glyphs.check_config(cfg), "test", **kw)


def chance(r):
    """Each symbol's chance, as state.frag's pickGlyph gives it: the set by its share, then alike."""
    out = Counter()
    lo = 0.0
    for end, first, count in r.uniform():
        for slot in r.table[first:first + count]:
            out[r.keys[slot]] += (end - lo) / count
        lo = end
    return out


def test_weights_split_what_the_shares_leave():
    cfg = {"sets": [{"name": "a", "chars": "AB", "weight": 3}, {"name": "b", "chars": "C", "weight": 1},
                    {"name": "c", "chars": "D", "share": 0.2}]}
    assert glyphs.set_shares(glyphs.check_config(cfg)) == pytest.approx([0.6, 0.2, 0.2])
    cfg["balance"] = "glyphs"                       # weight a character: A and B 3 each, C 1
    assert glyphs.set_shares(glyphs.check_config(cfg)) == pytest.approx([0.8 * 6 / 7, 0.8 / 7, 0.2])


def test_hieroglyphs_given_their_share_on_the_command_line():
    cfg = {"sets": [{"name": "latin", "chars": "AB"}, {"name": "hieroglyphs", "chars": glyphs.HIEROGLYPHS}]}
    assert glyphs.set_shares(glyphs.check_config(cfg), hieroglyphs=0.25) == pytest.approx([0.75, 0.25])
    assert glyphs.set_shares(glyphs.check_config(cfg), hieroglyphs=0.0) == pytest.approx([1.0, 0.0])


def test_the_themes_fall_with_build_12_s_weights():
    """nixos: each base-32 character 1, the lambda 2.6, the snowflakes 0.9, 0.5, 0.5, each Nix symbol
    0.25 (a symbol in two of build 12's groups counted once), and 15% hieroglyphs."""
    meta = engine.load_meta()
    r = glyphs.resolve(meta, meta["themes"]["nixos"], engine.DATA_DIR)
    c = chance(r)
    assert sum(c.values()) == pytest.approx(1.0)
    rest = 0.85 / (32 + 2.6 + 0.9 + 1.0 + 3.0)
    assert c["a"] == pytest.approx(rest) and c["λ"] == pytest.approx(2.6 * rest)
    assert c["❄"] == pytest.approx(0.9 * rest) and c["❅"] == pytest.approx(0.5 * rest)
    assert c["{"] == pytest.approx(0.25 * rest)
    assert c["𓆙"] == pytest.approx(0.15 / len(glyphs.HIEROGLYPHS + glyphs.HIEROGLYPHS_MORE))


def test_a_wallpaper_s_atlas_holds_only_what_its_sets_use():
    r = resolve({"sets": [{"name": "few", "chars": "ЖΩ𓆙"}]})
    assert r.keys[:5] == list("NIXOS")              # the hidden words' letters first: 8 bits each
    words = "".join(engine.load_meta()["themes"]["nixos"]["wordText"])
    assert set(r.keys) == set(words) | set("ЖΩ𓆙")
    assert r.rows == 2 and not r.missing
    w, h, data = r.atlas()
    assert (w, h, len(data)) == (16 * 96, 2 * 96, 16 * 96 * 2 * 96 * 4)


def test_the_web_page_resolves_the_shares_the_same_way():
    """setShares in web/template.html is this function in JavaScript: the same steps in the same order."""
    page = open(engine.DATA_DIR.replace("syncrain/data", "web/template.html"), encoding="utf-8").read()
    assert "function setShares(cfg, hieroglyphs)" in page and "rest * weights[i] / total" in page


@pytest.mark.parametrize("cfg, says", [
    ({"sets": []}, "needs a list"),
    ({"sets": [{"name": "x"}]}, "needs \"chars\""),
    ({"sets": [{"name": "x", "chars": "a", "weight": -1}]}, "0 or more"),
    ({"sets": [{"name": "x", "chars": "a", "share": 0.7}, {"name": "y", "chars": "b", "share": 0.5}]}, "more than 1"),
    ({"balance": "evenly", "sets": [{"chars": "a"}]}, "balance"),
    ({"sets": [{"name": "x", "chars": "   "}]}, "needs \"chars\""),
    ({"sets": [{"name": "x", "chars": "a", "size": 0}]}, "0.2 to 2"),
])
def test_a_symbols_file_that_cannot_work_says_why(cfg, says):
    with pytest.raises(glyphs.GlyphsError, match=says):
        glyphs.check_config(cfg)


def test_a_broken_file_falls_back_to_the_theme_and_says_so(tmp_path):
    path = tmp_path / "glyphs.json"
    path.write_text("{ not json", encoding="utf-8")
    said = []
    meta = engine.load_meta()
    r = glyphs.for_theme(meta, meta["themes"]["nixos"], engine.DATA_DIR, path=str(path), warn=said.append)
    assert r.source == "the theme" and "not JSON" in said[0]


def test_the_starter_file_is_a_bit_of_everything(tmp_path):
    path = tmp_path / "syncrain" / "glyphs.json"
    assert "wrote" in glyphs.write_starter(str(path))
    cfg = glyphs.read_config(str(path))
    names = [s["name"] for s in cfg["sets"]]
    for wanted in ("katakana", "cyrillic", "arabic", "french", "hieroglyphs", "favourites"):
        assert wanted in names
    assert "𓆙" in json.loads(path.read_text(encoding="utf-8"))["sets"][-1]["chars"]
    r = resolve(json.loads(path.read_text(encoding="utf-8")))
    shipped = glyphs.Library(engine.load_meta(), engine.DATA_DIR).index
    assert all(k in shipped for k in r.keys), "every starter symbol is shipped, so no font is needed"
    assert "is there already" in glyphs.write_starter(str(path))


def test_a_set_with_its_own_font_or_size_draws_its_own_glyphs():
    """A shipped character still comes from the set's font when the set names one."""
    r = resolve({"sets": [{"name": "plain", "chars": "AB"}, {"name": "big", "chars": "AB", "size": 1.2}]})
    shipped = glyphs.Library(engine.load_meta(), engine.DATA_DIR).index
    assert [k in shipped for k in r.keys if k.startswith(("A", "B"))] == [True, True, False, False]


def test_a_font_that_cannot_be_drawn_gives_way_to_the_next(tmp_path):
    """A colour bitmap font (emoji), or a broken file, must not stop the wallpaper."""
    broken = tmp_path / "broken.ttf"
    broken.write_bytes(b"not a font")
    fonts = glyphs.font_list()
    slot = glyphs.draw_slot("A", {"font": str(broken)}, fonts)
    assert slot.size == (glyphs.SLOT, glyphs.SLOT) and slot.split()[0].getbbox(), "drawn from the next font"
    assert glyphs.draw_slot("\U0010FFFD", {}, fonts).split()[0].getbbox() is None, "no font: a blank slot"


def test_shares_of_sets_with_nothing_to_draw_go_to_the_rest():
    r = resolve({"sets": [{"name": "a", "chars": "AB", "weight": 1}, {"name": "b", "chars": "C", "weight": 1}]})
    r.sets[1] = ("b", r.sets[1][1], 0)                 # as if it had nothing
    assert r.uniform() == [(1.0, 0, 2)]




def test_any_problem_with_a_file_s_symbols_falls_back_to_the_theme(tmp_path, capsys):
    """Not only a file that is not right: characters or a font that cannot be drawn (here half of a
    character, which JSON can spell). The wallpaper draws the theme's symbols and says why."""
    from syncrain import renderer
    path = tmp_path / "glyphs.json"
    path.write_text('{"sets": [{"name": "mine", "chars": "\\u4e00\\ud83d"}]}', encoding="utf-8")
    r = renderer.from_args(__import__("syncrain.app", fromlist=["parse_args"]).parse_args(["--glyphs", str(path)]))
    sources, _bg, _mask = renderer.texture_sources(r, renderer.rgba_pil)
    assert r.glyphs.source == "the theme" and sources["atlas"][0] > 0
    assert "could not be used (UnicodeEncodeError" in capsys.readouterr().err
