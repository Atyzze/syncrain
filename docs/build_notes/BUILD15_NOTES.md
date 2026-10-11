# Build 15: your own symbols

**Type: feature; the stream changes** (`def5684f`): machines on build 14 and build 15 stop
matching. Made on 2026-10-11.

## The symbols file (`syncrain/glyphs.py`)

* `~/.config/syncrain/glyphs.json` (or `--glyphs FILE`): sets of characters, each with a weight or
  a share; `"balance": "glyphs"` makes every symbol alike. `syncrain --write-glyphs` writes a starter
  with a bit of everything: katakana, hiragana, kanji, Latin, digits, Cyrillic, Greek, Arabic,
  French, hieroglyphs, symbols, and favourites (λ ❄ 𓆙).
* 489 glyphs are shipped (`syncrain/data/glyphs.png`, up from 220), 𓆙 among 30 more hieroglyphs;
  a character not shipped is drawn from this machine's fonts. `--diagnose` lists the sets, their
  shares, and what no font has.
* A wallpaper keeps only the glyphs its sets use: the themes' atlas is 195 glyphs, not 220.
* The themes keep build 12's weights, now as sets; which symbol a drop shows changed, so the stream
  did.

## The Plasma wallpaper, removed

* Builds 13 and 14's Plasma wallpaper was "severely broken" on the operator's desktop. Gone:
  `syncrain/plasma/`, `nix/plasma.nix`, the plasma lane, `--write-scene`, `install.sh --plasma`.
* Any install or uninstall takes it away again and puts Plasma's desktops and lock screen back on
  their image wallpaper (`remove_plasma_wallpaper` in `install.sh`).
* Kept: the six passes in `syncrain/native/passes.c`.

## Inside

* `state.frag` picks a set by its share, then a symbol of it (`pickGlyph`), from a table of atlas
  slots; a slot is 16 bits (B and A of the state). The atlas is 16 slots wide and as tall as needed.
* The scene's `lut` texture is now `table` (`syncrain-scene-2`); uniforms carry 64 values.
* A font that cannot be drawn (a colour emoji font, a broken file) gives way to the next; drawn
  glyphs are cached by their fonts' files and dates; a file not in UTF-8 is said.
* Tests: the shares (`tests/unit/test_the_symbol_sets.py`); a symbols file changes the frame and a
  broken one is said (`tests/render/`); native and GTK host draw the same frame with one
  (`tests/wayland/`), and the page and the app with the themes' sets (`tests/browser/`).

## What the operator does

* `./install.sh` from `syncrain_build_15/`: it also takes the Plasma wallpaper away.
* `syncrain --write-glyphs`, then edit `~/.config/syncrain/glyphs.json`: weights, shares, your own
  sets; restart syncrain to see them.

## Verification

222 passed in 503.30s (0:08:23)
