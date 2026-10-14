# Build 21: try every setting on the page, then give the desktop the same

**Type: feature; the picture is unchanged unless a settings file is given** (stream `def5684f`).
Made on 2026-10-14, as the operator asked at 15:26: "a live previewer that lets you directly see
what it'll look like, and then lets you export/save the json config file, if then applied with
that exported json, it should look exactly like it did in the html previewer".

## The page

* **Settings** opens a panel beside the rain (a sheet from below on a phone); the rain shrinks to
  stay in view and changes as anything moves: theme, channel, rainbow, logo, snow, speed, density,
  logo turn and drift, glow, bloom, background, frame rate, pause under.
* **Symbols**: the sets with their share of the rain (a bar and a percentage each), weight or
  share, mirrored, the characters to type into; add any set the themes or the starter file have, or
  your own characters; start from a theme's sets or "a bit of everything"; per set or per symbol.
* **Screen shape**: 16:9, 21:9, 32:9 and others, drawn as a desktop of that shape draws it.
* **Save config.json**, **Copy**, **Open a settings file** (or drop one on the page; a
  `glyphs.json` loads as the sets), **Reset all**. What is being tried is kept in the browser.
* The page checks what it saves the way the desktop does, so a saved file is always one the
  desktop takes. Characters not among the 489 shipped symbols are drawn by the browser's fonts and
  named, as the desktop draws them with its own.
* The atlas is now built as the desktop builds it (only the glyphs used, the hidden words' first).
* As a wallpaper page (`hud=0`) a cell stops shrinking at 12 px, as on the desktop: under about
  900 px wide the two drew differently (open item L12). URL `scale` and `fps` take what the command
  line takes.

## The desktop

* `syncrain --config FILE`, else `~/.config/syncrain/config.json` when it is there; `--config none`
  for none. Options given on the command line go over it. `--check-config` says what it comes to.
* `./install.sh --config config.json` checks the file, keeps it (one there before as
  `config.json.before`), writes the service again without options so the file decides, and gives
  the login screen's rain a copy. Without `--login-screen` the login is untouched, as always.
* `--theme` refuses a theme there is not with status 2 (it ended with status 1, which the service
  restarts on, for good).

## From the review (an agent that did not write it)

* The settings file's options go to the command line as one word each (`--channel=-x`), so a
  channel or a negative number that starts with "-" is not read as an option; the installer's
  `--theme`, `--channel` and `--rainbow` too.
* A broken settings file stops neither `--build` nor `--help` (the installer's own check comes
  before it can put a good file in place); `--diagnose` says it and goes on.
* The login screen draws the settings file's sets, not a `glyphs.json` beside it, and draws them
  ahead of time.
* `./install.sh --config` given the kept file itself works; a link in its place is replaced, not
  written through; the service's options from before that go are said.
* The page: a settings file with only sets starts from the defaults, as the desktop does; a
  `glyphs.json` without its contract loads; one unfinished set no longer loses the whole draft; a
  wallpaper page in the same browser takes the whole draft, not half of it.
* `--check-config` says sets the wallpaper would not draw (status 2); `--power-sweep` passes the
  settings file on; a shortened option (`--conf`) is refused; a number too large is said.

## Tests

* The browser lane draws one settings file (every setting moved, its own sets) on the page and the
  desktop and compares the frames; uses the panel at a desk and on a phone and saves; the desktop
  reads what was saved; the page refuses what the desktop refuses; a narrow wallpaper page matches a
  narrow desktop.
* Settings file and installer tests in the unit lane.

## Open items

* In `docs/ROADMAP.md`: L8, L11, L20, L21, a font file name that is not UTF-8, and the settings
  file holding no `background`, `mask`, `scale` or `layer`.

## What the operator does

* Open the page, press Settings and try anything. Save config.json, then in the `syncrain_build_21/`
  folder: `./install.sh --config ~/Downloads/config.json` (where the browser saved it).
* Nothing changes on screen until a settings file is given.

## Verification

346 passed in 786.52s (0:13:06)
