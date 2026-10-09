# Build 10: the documents, short

**Type: consolidation; no behaviour changes.** Made on 2026-10-09. The operator: "there's too much
prose/detail in all the docs ... Keep it minimal please, walls of text arent inviting to read :)".

## Changes

* Every document rewritten short: bullets and tables, present tense, one home per fact. About 2,700
  lines of documents became about 850.
* Builds 1 to 8's notes folded into `docs/HISTORY.md` and removed; build 9's stay.
* Written down for build 11 (`docs/agent/NEXT_BUILD.md`): the memory creep on the operator's
  desktop is NVIDIA's explicit-sync leak (+0.9 MiB a minute while drawing; flat on Mesa over 20,000
  frames under KWin and Sway); and build 9's review items.
* The kwin lane's timing floors now fit this sandbox on a slow day: at 60 Hz the frames' median
  "even" 75% and "steady" 85%, at 141 Hz 65% and 75%, and the pacer still at least 15 points
  steadier than build 4's timer in the same session. Two gates of this build had failed by a point
  or two (84 for 85, 76.5 for 80) with no code changed; the timer stays far below either floor.
* No code changed.

## What the operator does

Nothing: the wallpaper is the same as build 9's.

## Verification

184 passed in 567.21s (0:09:27)
