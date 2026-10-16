# Build 44: the stream id is what the code computes, and --scale keeps the grid

**Type: feature; the stream id changes on purpose, the picture only at a low --scale** (stream
`0aa22037`, was `1ad0a2dd`). Made on 2026-10-16, the third of the builds on the roadmap's open items:
L20 and L11.

## What the stream id covers (L20)

* It was a hash of files: the data (presets, pictures, shaders) and two source files,
  `engine.py` and `glyphs.py`. A comment in either changed it; the grid's code
  (`renderer.py`, `native/timing.c`, the page) did not count at all.
* Now it is the data files and what the code computes (`syncrain/stream.py`): for every preset,
  with its own settings and with ten that change it (colours, cycles, flavours, the logo, motion,
  the look at both ends, words), the scene the native wallpaper is given (the shaders as assembled,
  every texture, every fixed uniform, the logo's place: what all three hosts draw from); the grid
  at twelve screen sizes and four scales; the clock up to 2038 and after; channel seeds; a
  picture's fit. A comment changes none of it.
* That takes seconds, so it is written down on purpose (`tools/stream_freeze.py --write`) into
  `syncrain/data/stream-reference.json`, one of the stream's files: every start still only hashes
  files. The gate computes it again and names the part that moved.

## --scale below 1 (L11)

* The grid's smallest cell (12 pixels) was taken in the pixels drawn, not the screen's, so where a
  low `--scale` made a column narrower than that (below 0.4 on a 1920 screen, 0.56 on a 1366 one,
  any scale under 1 below 768 pixels wide) it showed only the middle of the stream, larger. The
  smallest cell is now the screen's 12 pixels at any scale, on the desktop (GTK and native) and on
  the page (`scale=` in its address): a low scale draws the same rain, softer. A video, a still or
  a record made with `--scale` keeps the screen's grid too.

## Machines on build 43 and 44

* At a scale of 1 they draw the same frame; the stream id they show differs (the id now names more).
  Where a low `--scale` made columns narrower than 12 pixels, they differ.

## The review of this build

An agent that did not write it read it: nothing critical. Its findings (the first reference sampled
too little of what decides a frame, a video or record at `--scale` drew another grid, the page's
threshold, sizes no host draws, a value json might write differently per machine, the wording of
where the picture changed) are fixed above.

## What the operator does

* Nothing (their settings have no `--scale`).

## Verification

558 passed in 1418.45s (0:23:38)
