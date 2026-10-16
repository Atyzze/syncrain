# Build 41: the page and the release tool, the last of the review of build 33

**Type: fix; the picture does not change** (stream `1ad0a2dd`). Made on 2026-10-16, the last of the
builds that fix what the review of build 33 found. This one takes the web page and the release tool:
items 13, 19, 24 to 26, 70 to 75 and 77 to 84. With it, all 84 items are done.

## The page

* **No outside request (13)**: the Google Fonts stylesheet held the first frame until Google
  answered (8.5 s with a slow network) and told Google of every visit, wallpaper pages included. The
  page uses the system's fonts, as it already fell back to; the browser lane now fails any request
  the page makes beyond itself.
* **The same frame at any size (70)**: the blur passes' quarter size rounds halves to even, as the
  desktop does: at 1050 rows the page used 263 and the desktop 262.
* **Frames between milliseconds (71)**: the page draws each moment at its millisecond, as the
  desktop's clock does, and sums a video frame's time in seconds as `syncrain --video` does (the
  same double, so the same millisecond at 25 fps and after 2038 too); at 30 fps one frame in six
  showed other heads than `syncrain --video`.
* **A video is one look (72)**: while it is made every control but Stop and Close stands still, and
  a dropped file is refused, from the first moment (Stop works while its symbols are still drawn).
* **A video in a background tab (73)** goes on at full speed (the page yields through a message,
  and waits for the encoder's own event, not a timer a background tab slows to once a second).
* **Half the memory for a video (74)**: each part of the file is packed as soon as it is complete,
  and its frames let go.
* **One grammar for a settings file (75)**: a number is decimal digits, a point and an exponent on
  both sides (the page took `0x10`, Python `1_0` and full-width digits); a byte order mark first is
  read past on both, and a file the page opens is read as strict UTF-8, as the desktop reads it (the
  browser took UTF-16 and mended bad bytes); a channel is text on both (the desktop made `5` the
  channel "5.0") and never half a character. A test reads 54 such files on the page and the desktop
  and finds no difference.
* **`__proto__` in a set (77)** is one more key of the set, as in Python, not its prototype.
* **A picture too large to keep (78)** no longer brings back the one kept before on the next visit.
* **Two logo pictures in quick succession (79)**: the one chosen keeps its texture; a picture over
  4096 pixels is refused before it reaches the card, and its decoded copy is let go.
* **A wrong `t=` in the address (80)** is the clock, not an error on every frame.
* **Symbols drawn from fonts (81)** are drawn in short slices, so the tab answers while 600 CJK
  symbols are drawn (it was held for 6.6 s), and the atlas is made again from the sets they were
  drawn for; the empty-glyph probe is made once per font, and the drawn symbols kept are pruned to
  an atlas's worth.
* **Zoom and another monitor (82)**: the canvas and its cells follow the screen's scale as it changes.
* **Said as it is (83)**: a page that cannot start says why where the rain would be; a download says
  "Download started", since the browser decides the rest.
* **The keyboard (84)**: closing Settings puts the focus back on its button; every set's fields say
  which set they are in, and its note is read with its characters.

## The release tool

* **One release at a time (24)**: a lock held for the whole run; a second run stops at once, where
  it used to take the running release's journal for an interrupted one's.
* **The same bytes (25)**: every file in the archive has the commit's time, whole seconds, and the
  modes 644 or 755, whatever the checkout's times and the umask were.
* **setuptools (26)**: the licence as an SPDX expression and the data folders found as the
  namespace packages they are; setuptools 77 or newer builds the wheel.

## The cases the lanes did not try (19)

The browser lane compares frames at 1680x1050 and the 90 frames of a 30 fps second; the Wayland lane
draws on Sway at scales 1.25 and 2 (the native wallpaper to the pixel at both; the GTK host at 2,
since at 1.25 GTK's GL area draws at 2 and Sway scales it down: an open item now); a settings file
saved by the panel loads back as it was.

## The review of this build

An agent that did not write it read it: nothing critical. Its findings (a test that would have read
a promise, the wait before an export, the cell size after a zoom, a file the browser decoded its own
way, the frame times at 25 fps, the slices after the sets went wrong, shots before every symbol was
drawn, the picture limit on the shipped atlas) are fixed above.

## What the operator does

* Nothing. The page is `index.html` in the release, as before. Whoever makes releases needs
  setuptools 77 or newer, with packaging 24.2 or newer (`docs/agent/ENVIRONMENT.md`).

## Verification

549 passed in 1422.38s (0:23:42)
