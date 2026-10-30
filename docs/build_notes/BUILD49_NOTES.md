# Build 49: a symbol keeps still once the rain has passed it

**Type: feature; the picture changes** (stream `b8c95b5e` to `dc1b15b8`: the trails' symbols, so
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
  crossing a word writes over those letters, and a cell written over is drawn as rain, not lit
  whiter as a letter is.
* The drop that passed last keeps the cell even after its own trail has gone dark and an older,
  longer trail still lights it, so the older trail never puts its symbol back.
* The tick is counted from the drop's spawn second (an integer) plus a few seconds' float, so
  every frame on a machine agrees with the last. Across two GPUs, a head that leaves a row within
  a few ULP of a tick's edge can lock a different symbol: about one cell in 10 to 30 minutes,
  held for its fade (an open item).

## Measured here (the state pass alone, 10 s at 30 fps, 64 x 40 cells, both contrast modes)

* Symbols changing in lit cells behind the head: about 1% of cells a frame on build 48, 0.005% on
  build 49. Each one left is a drop that starts mid-screen and whose head crosses the row between
  two frames: the rain arriving.
* About 1 cell in 8 changes once at the moment the head steps off it (the head's last 15 Hz tick in
  that row fell between two frames), right behind the falling head.

## The review of this build

An agent that did not write it read the change, compiled it as every host assembles it, and ran
a port of the drop loop over 10 columns for 90 s at 30 fps: no symbol changed in a lit cell without
a head arriving. Drops that stop early, starts mid-screen, sentences' gaps, glints, the logo's cells
and the look-back window all hold; the integer ticks wrap together past 2033. No everyday fault.
Fixed in this build: a word's brighter, whiter letter style stayed on a cell a later drop had
written over (about 13% of such cells), and a comment called the lock exact on every GPU. Left for
later (open items): the lock's few-ULP tie across GPUs; a slow head overtaken in its row, or a
start mid-row, can sit on a still symbol for up to about 1/7 s; the symbol is now picked for dark
cells too (twice the picks, on a pass of about 2,500 cells).

## What the operator does

* Unpack, then `./install.sh`. The wallpaper restarts with it.
* Look at a trail as it fades: its symbols stay as the head left them; only the falling heads
  change them.

## Verification

GATE_RESULT
