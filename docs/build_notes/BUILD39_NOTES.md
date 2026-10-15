# Build 39: the native and Python hosts, what the review found in them

**Type: fix; the picture does not change** (stream `1ad0a2dd`). Made on 2026-10-15, the sixth of the
builds that fix what the review of build 33 found. This one takes the native wallpaper and the
Python host: items 14, 15, 29, 48 to 55, 57 to 64, 67 and 68.

## The native wallpaper

* **Fractional scale (48)**: a screen that went from an integer scale to a fractional one kept its
  buffer scale, so the viewport scaled the picture twice.
* **A scene it cannot read (49)**: another build's program, say, now hands over to the GTK host,
  whose command is in its environment too (`SYNCRAIN_FALLBACK_*`, which a program of an earlier
  build passes by; an option it did not know would have stopped it); before, it ended with status
  70 and nothing drew.
* **The KWin watch (50, 51)**: its match is sent without waiting on the frame loop; on Plasma it
  tries again after 5, 10 and 20 s when KWin is not on the bus yet at login (not after a call that
  timed out: each try would hold the frames); its script is written
  only in the operator's runtime folder (never `/tmp`), as a new file that cannot be a link (both
  hosts); a script KWin did not confirm unloaded keeps its file, so the next start unloads it.
* **The presentation time (52)**: GDK's corrections at the 2^31 and 2^32 ms boundaries put the time
  49.7 days off there; the signed 32-bit difference wraps by itself.
* **A failed context switch (53)** is tried again next frame instead of being taken for done, and
  the frame it could not draw is not swapped (a lenient driver would show the undrawn buffer).
* **The scene's numbers (54)**: each is all of its word (`0,44` read as 0 and `64junk` as 64), and
  a line that can be said once is refused when said twice.
* **Old headers (55)**: built against Wayland headers without version 6's events, it binds the
  compositor at 5, so no event arrives without a listener.
* **Texture units (57)**: a test holds the C tables to Python's.

## The Python host

* **A video and a screen change (14)**: plugging a screen in or out during `--video` rebuilt the
  window, lost the video's renderer, deleted the video and repeated the error every frame. One-shot
  windows (a still, frames, a video) are no longer rebuilt, and any error ends the video once.
* **`--diagnose` (15)**: a part that fails says "could not check" in its place, and the rest is
  printed.
* **`--power-sweep` (58)**: the phases get the options typed and the settings file by name (or
  `--config=none`): a picture as the logo no longer overflows the command line, and what was
  measured is reported even after an error.
* **`--check-config` (59)** counts symbols with the settings' own words, as they are drawn.
* **Videos (60, 61)**: ffmpeg is given the output as a file (`rain-12:00.mp4` was read as a
  protocol); the loop's fade rounds as the page does.
* **`--size` (62)** is checked when given, for every use (a wrong `size` in the settings file now
  stops the wallpaper too, with status 2, as a wrong preset there does); **`--scale` (63)** keeps the
  offscreen sizes last used (one per monitor a window covers, at least two), not every size a
  resized window ever had; **`--screenshot` (64)** on Wayland draws in a window of about its size
  (two screens wrote one file twice, GNOME none); on X11 it is still the whole desktop.
* **GL objects of a replaced look (67)** are freed; a hanging `nvidia-smi` no longer stops the power
  sweep's probe (68).

## The lock screen (29)

* It takes the look from the options, not `--fps`, `--scale` or `--offset`: it draws at 30 fps at
  full size. The documents said those reached it; now they say what it does.

## The review of this build

An agent that did not write it read it: nothing critical, the picture unchanged, every scene the
Python side writes still read. Its findings (the fallback an earlier program refused, the offscreen
sizes on several monitors, the failed switch, the script file kept, the retries) are fixed above.

## What the operator does

* `./install.sh` as usual.

## Verification

541 passed in 1193.83s (0:19:53)
