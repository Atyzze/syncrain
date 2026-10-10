# Build 12: picture options, hieroglyphs, memory handed back

**Type: feature; the stream changes** (`c18f8be2`): machines on build 11 and build 12 stop
matching. With `--hieroglyphs 0` and the other options at their defaults, the frame is build 11's
to the pixel. Made on 2026-10-10.

## New options (command line, `nix/options.nix`, the page's URL)

| Option | Default | What |
| --- | --- | --- |
| `--bg-gain F` | 1 | Now darkens the gradient too (was `--background` only) |
| `--glow F` | 1 | Glow around the centre and the logo; 0 = none |
| `--bloom F` | 1 | Glow around the falling symbols |
| `--speed F` | 1 | Fall speed, 0.25 to 4 |
| `--density F` | 1 | How often a column starts a stream, 0 to 2.3 |
| `--snow off` | on | No falling snowflakes (the ❄ symbols in the rain stay) |
| `--hieroglyphs F` | 0.15 | Share of the changing symbols that are Egyptian hieroglyphs |

* 95 signs from Gardiner's list (Noto Sans Egyptian Hieroglyphs, OFL 1.1), thickened to the other
  glyphs' weight, after every older glyph in the atlas (`tools/build_assets.py`).
* Tests: each option changes the picture (`tests/render/`); the native wallpaper and the GTK host
  draw the same frame with every option set (`tests/wayland/`); so do the page and the app
  (`tests/browser/`).

## The glow flare-up

* Two hours of the stream rendered at 4 frames a second, and ten minutes at 30: no flare in the
  picture. The whole screen's brightness stays within about 12%, never jumps between frames.
* So what the operator saw is not in the frames syncrain computes. The time it happened (to the
  minute) is enough to draw that exact moment again and look.

## Memory (`syncrain/native/wallpaper.c`, `syncrain/app.py`)

* Build 11 on the operator's desktop: 110 MiB at start, 196 after 2.5 h, 217 after 7.6 h, 225 after
  18 h, then 170 at once. Memory that falls by itself was freed, not leaked: the C heap keeps freed
  memory until asked, and syncrain asked only after the first frames and when a screen changed.
* Both hosts now hand freed memory back every five minutes while drawing.
* The native wallpaper writes `~/.local/state/syncrain/memory.log`: a line after the first frames,
  then one an hour (resident MiB before and after, frames, malloc in use).
* `syncrain --diagnose` shows each running wallpaper (host, hours up, MiB, the explicit-sync
  variables it really got) and the record's last lines.

## Build 11's review, fixed

* The sweep keeps signals held until its record is saved, and asks the power source to describe
  itself once, at the start.
* Ctrl+C goes through the same handler as a hang-up, so the first signal already holds the rest.
* The signal tests pass under `nohup pytest` too.

## What the operator does

* Install it (`./install.sh` from `syncrain_build_12/`), then try, for example,
  `syncrain --glow 0.3 --bg-gain 0.6 --snow off`. For the autostart service:
  `./install.sh --autostart --arg --glow --arg 0.3`.
* Next time the glow flares, note the time.
* After a few hours, `syncrain --diagnose`: the memory record should stay level.

## Verification

204 passed in 613.47s (0:10:13)
