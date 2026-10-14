# Build 20: consolidation

**Type: consolidation; nothing changes on screen** (stream `def5684f`). Made on 2026-10-14.

## Folded

* Builds 9 to 18's notes folded into `docs/HISTORY.md` and removed: a few lines a build with their
  measurements (the memory timeline, the NVIDIA forum's explicit-sync leak, the glow check, each
  gate's count), the review of build 17 by finding, and the operator's words with their dates.
* `docs/ROADMAP.md` keeps the decisions since build 17; the earlier ones are in the history.
* `docs/LESSONS.md`: duplicates merged, a login-screen section, the sandbox traps left to
  `docs/agent/ENVIRONMENT.md`, the CMake rule gone with the Plasma wallpaper.

## Made true

* `README.md`: `syncrain/glyphs.py` is a stream file; the layout names the login screen's files.
* `docs/OPERATIONS.md`: `--size` for `--benchmark` defaults to the first screen; `--glow` and
  `--bloom` go to 2, `--scale` to 4; an upgrade restarts the autostart service only if it runs;
  what `--diagnose` shows; the installer's other options.
* `docs/ARCHITECTURE.md`: the native wallpaper exits after 5 s of frames that cannot be shown; the
  login screen as it is since build 19; which files the stream id covers.
* The handoff, the one page and the operator's machine: shorter, and "two questions", not three.
* `syncrain/app.py`: its docstring called the GTK host the native wallpaper.

## Open items

* In `docs/ROADMAP.md`, "Open items": L8, L11, L12, L20, L21, a font file name that is not UTF-8,
  and one found here: the page clamps `scale` (0.25 to 3) and `fps` (1 to 240) where the command
  line takes up to 4 and 1000.
* Build 21 is the previewer page (`docs/agent/NEXT_BUILD.md`).

## What the operator does

* Nothing is needed. Installing it (`./install.sh` from `syncrain_build_20/`) changes nothing on
  screen.

## Verification

319 passed in 670.09s (0:11:10)
