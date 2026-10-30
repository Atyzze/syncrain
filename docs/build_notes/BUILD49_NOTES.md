# Build 49: a symbol keeps still once the rain has passed it

**Type: feature; the picture changes** (stream `b8c95b5e` to `1021718d`: the trails' symbols, so
machines on build 48 and 49 stop matching). Made on 2026-10-30, from the operator's request of that
day.

## The request

* "after a symbol has been locked in, we stop changing it, so that only during the rain fall does
  the actual symbol change, once its locked in, it just slow fades out as is" (2026-10-30 13:56).

## What changed (`syncrain/data/shaders/state.frag`)

* Before: a lit cell behind the head was given a resting symbol re-rolled on a timer of its own,
  every 1.5 to 6 s, and took its symbol from whichever drop lit it brightest, so it could also
  switch while fading when one trail dimmed below another.
* Now a cell's symbol belongs to the drop whose head passed it last. While that head is on the
  cell it scrambles 15 times a second, as before; once the head has moved on, the symbol is the
  one shown in the 15 Hz tick in which the head left the row, and it fades as it is. Only another
  head passing over the cell changes it. A hidden word's letters follow the same rule: a later drop
  crossing a word writes over those letters.
* The drop that passed last keeps the cell even after its own trail has gone dark and an older,
  longer trail still lights it, so the older trail never puts its symbol back.
* The tick is counted from the drop's spawn second (an integer) plus a few seconds' float, so the
  page, the GTK host and the native wallpaper agree, as the rest of the stream does.

## Measured here (the state pass alone, 10 s at 30 fps, 64 x 40 cells, both contrast modes)

* Symbols changing in lit cells behind the head: about 1% of cells a frame on build 48, 0.005% on
  build 49. Each one left is a drop that starts mid-screen and whose head crosses the row between
  two frames: the rain arriving.
* About 1 cell in 8 changes once at the moment the head steps off it (the head's last 15 Hz tick in
  that row fell between two frames), right behind the falling head.

## The review of this build

REVIEW_SUMMARY

## What the operator does

* Unpack, then `./install.sh`. The wallpaper restarts with it.
* Look at a trail as it fades: its symbols stay as the head left them; only the falling heads
  change them.

## Verification

GATE_RESULT
