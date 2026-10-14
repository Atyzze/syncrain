# Roadmap

Open questions, planned builds, the cadence and the constraints. What shipped: `docs/HISTORY.md`.

## Questions for the operator

* **Default frame rate** (asked 2026-10-07; numbers from their sweep of build 8): 30 fps +11.9 W
  (now), 20 fps +7.3 W, 15 fps +3.5 W. Below about 21 fps the fastest streams skip a row now and
  then. Recommended: `syncrain --fps 20` for a day, then judge by eye.
* **Pause behind maximized windows too, or only full-screen ones?** (2026-10-07) Both now; behind a
  see-through window the rain then stands still. Recommended: both.

## Decisions answered

* **2026-10-14 15:26**: "continue as recommended" (the review first, build 19); then the page "a
  live previewer that lets you directly see what it'll look like, and then lets you export/save
  the json config file, if then applied with that exported json, it should look exactly like it
  did in the html previewer"; "fix the bugs first of course". Builds 19 and 21 (20 is the
  consolidation).
* **2026-10-14 12:10**: a full review of build 17; "Yes, make build 18 please" with M1 to M3 and
  the one-line fixes; on GitHub, "makes sure that the login screen replacement remains fully
  optional, and that those who just want the wallpaper that their existing login method isn't
  touched". Build 18.
* **2026-10-13 15:29**: build 16 works; the box on all screens, always; no Plasma logo or old
  wallpaper between the login and the rain. Build 17.
* Earlier answers, dated: `docs/HISTORY.md`, "The operator's words".

## Planned builds

1. **The previewer page (build 21)**: every option and symbol set on the page, drawn live;
   "Export config" saves `config.json`; the desktop reads it (`./install.sh --config config.json`,
   or the file in `~/.config/syncrain/`) and draws the same frame. Needs L11, L12 and L20 first.
2. **The boot splash**: a still frame of the rain (Plymouth), until the login screen's live one.
3. **A NixOS image** with syncrain as its wallpaper and login screen.

## Open items

What the documents and the review of build 17 leave to a build that changes code.

| Item | Where the fix goes |
| --- | --- |
| L8: KDE's wallet does not open after greetd's text login | not known yet; the wallet lines are `install.sh`'s, in greetd's PAM service |
| L11: `--scale` below about 0.4 changes the picture | the cell size in `syncrain/renderer.py` (`geometry`), `syncrain/native/timing.c` (`geometry_compute`), `web/template.html` |
| L12: on screens under about 900 px wide the page and the desktop differ: a cell is at least 12 device px in the hosts, 14 CSS px times the scale in the page | the same three places |
| L20: the stream id does not cover `renderer.py`'s geometry, `native/timing.c` or `web/template.html` | `syncrain/build.py` (`STREAM_FILES`) |
| L21: no `flake.lock`, so a Nix build takes whatever nixpkgs is current | `flake.lock` |
| A font file name that is not UTF-8 makes a symbols file fall back to the theme's symbols | `syncrain/glyphs.py`, a stream file: waits for a build that changes the stream |
| The page clamps `scale` to 0.25 to 3 and `fps` to 1 to 240; the command line takes `--scale` up to 4 and `--fps` up to 1000 | `web/template.html` or `syncrain/app.py`, with the previewer |

## Build cadence

Consolidation builds: every build number ending in 0, and no other build. Fixed: the operator's
rule, adopted at build 3. A consolidation changes no behaviour: it folds older notes into the
history, makes every document true and short again, and writes down what it finds as open items.

Next consolidation: 20

`tests/contract/test_the_working_documents_are_current.py` reads the two lines above.

## Standing constraints

* **Release**: only `tools/package_release.py` makes an archive and writes `BUILD_NUMBER`; notes in
  the same pass, ending in GATE_RESULT; the gate runs every lane; generated pages are regenerated
  and compared.
* **Picture**: the stream changes only on purpose; the hosts draw the same frame; nothing
  flashes (the fastest colour cycle is 90 s).
* **OpenGL**: never ask GTK for a version; take what it hands out and check it.
* **Writing**: short and plain; no long dashes; "the operator" or "they"; comments say why, not
  when; one home per fact.

## Not scheduled

* A public randomness beacon (drand) in the seed: truly random, still in sync.
* Two screens in the Sway lane (the KWin lane has two).
* Pausing on wlroots compositors that keep asking a hidden wallpaper for frames, if one turns up.
