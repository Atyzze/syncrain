# Build 48: the native wallpaper gives back what NVIDIA's driver keeps; the operator's config.json of 2026-10-21

**Type: fix; the picture changes** (stream `c5c869a0` to `b8c95b5e`: the default is the
config.json the operator put on GitHub on 2026-10-21, so machines on build 47 and 48 stop
matching). Made on 2026-10-25, from the operator's report of that day.

## The report

* The native wallpaper grew from 120 MiB at start to 401 MiB after 2 days (btop, both screens at
  30 fps, `--pause-under never`). Their `memory.log` (2026-10-23 to 25) and `nvidia-smi`: driver
  615.78.08.
* The record: resident memory up about 6 MiB an hour while about 215,000 frames an hour were drawn
  (about 28 bytes a frame); "malloc in use" up in steps of 27.1, 40.5 and 60.8 MiB, each 1.5 times
  the last: one array, regrown whenever it fills. Overnight, with the screens asleep, both stood
  still. Handing freed memory back (every five minutes) gave nothing: it is held, not free.
* Not syncrain's: on Mesa (headless Sway, two screens, 30 fps each) 12,800 frames left the heap and
  resident memory flat to 0.1 MiB, and 30 screens plugged in and out the same. syncrain makes no
  sync objects; its only growing array doubles, is capped and exists only with `--debug-fps`.
* NVIDIA's driver: on 615.71.09 and 615.78.08 every OpenGL sync object keeps about 16 bytes in
  `libnvidia-eglcore`, freed by nothing but `eglTerminate` (NVIDIA's forum, "615.78.08: glFenceSync
  leaks host memory, never freed", 2026-10-13; niri's tracking issue). Its `eglSwapBuffers` makes
  them itself, whether explicit sync is on or off (`__NV_DISABLE_EXPLICIT_SYNC=1` stays set; it
  stops build 11's larger leak).

## OpenGL made anew

* Every five minutes, after handing freed memory back, the native wallpaper compares the C heap
  with what it held once the screens had drawn. 32 MiB more (on the operator's desktop about every
  six hours of drawing) and, between two frames, it gives back everything EGL holds and makes it
  anew (`render_renew`): the textures read back from the card, the programs, every screen's EGL
  surface, the context, then `eglTerminate`; then EGL started again with the same API, the shaders
  compiled from their kept sources (tens of KiB; the 17 MiB of pixels still go after the first
  upload), the textures uploaded again, a new EGL surface on each screen's same Wayland surface.
* The screens keep their Wayland surfaces throughout, so the compositor keeps showing the last
  frame until the next one comes from the new context.
* `memory.log` gets two lines for each: the renewal (how long it took, the heap after it, how much
  had grown, resident before and after), and, once the new context has drawn, the heap then beside
  what it held when the screens first drew. That level is the new baseline, and the verdict: back
  near the start, the growth was the driver's. Still 32 MiB above it after three renewals in a row,
  renewals stop (the growth is then not what a renewal gives back) and the record says so. It is
  judged by the level after, not by how much fell at once: a driver may keep a table's room after
  emptying it.
* A renewal that cannot start (a passing failure after a resume, say) touches nothing and is tried
  again at the next round; three in a row and renewals stop. One that tears down and cannot build
  again stops the wallpaper with status 1, so its service starts it afresh (about 3 s of Plasma's
  own wallpaper), as after a lost compositor. A driver that frees what it makes (Mesa) never reaches
  32 MiB, so never renews.
* `SYNCRAIN_RENEW_MIB`: the growth that calls for it (below 0: never; 0: every round, never judged,
  for the lane; anything not a number: the default).

## Measured here (Mesa llvmpipe, headless Sway, two screens)

* A renewal every 5 to 10 s: about 110 ms each (shaders compiled in software included); over 40,
  the heap stayed at 71.0 MiB and resident memory level at about 144 MiB after the first.
* With the clock still, 1,277 grabs across three renewals, every one the first to the pixel: the
  textures come back byte for byte and nothing blanks. The lane does the same on two screens, then
  plugs a third in and the renewals go on.
* Not measurable here: NVIDIA's driver and KWin. On the operator's desktop the record shows whether
  a renewal gives the driver's memory back.

## The operator's config.json of 2026-10-21

* The operator uploaded the tree to GitHub on 2026-10-21 with their own config.json at the top:
  the words without `AI` and `AGENT`, `WAKE UP` for `WAKEUP`, the `symbols` set gone, fewer
  hieroglyphs. The gate held build 47's copy (`syncrain/data/config.json`, the preset, the page)
  to it and refused.
* config.json is the one home of the defaults (build 47), and `./install.sh` installs the file
  beside it: shipping build 47's would have put the removed words and symbols back on their
  desktop. So it is the default now: `tools/build_assets.py --themes-only`, the stream re-taken.

## The review of this build

An agent that did not write it read the change, and egl-wayland and egl-wayland2's sources. It
confirmed the cause there: egl-wayland2 makes and destroys a native fence sync on every swap, even
with `__NV_DISABLE_EXPLICIT_SYNC=1`, and `eglTerminate` reaches the driver's display once no
surface holds it. Terminate then initialize on the same display, and a new window on the same
`wl_surface`, are what both libraries support; the frame callbacks and presentation feedback
syncrain asked for are untouched; a destroyed buffer does not unmap a layer surface, so KWin keeps
the last frame (a still picture of 0.1 to 0.5 s at each renewal, about every six hours). Its
everyday findings are fixed above: renewals were judged by what fell at once (could stop after one
that worked), the baseline was taken before the new context drew, and covered screens were asked
for a frame. Its rarer ones fixed too: screens beyond 64, a word in `SYNCRAIN_RENEW_MIB` meaning
every round, one passing failure ending renewals for good, an unbounded wait on old OpenGL errors.
Left for later: a screen that first draws resets the baseline (it delays a renewal, no more);
egl-wayland 1.x frees its format list without forgetting it, which a renewal would reach only on a
compositor with linux-dmabuf 3 (KWin 6 offers 4 or later); a large background picture is read back
whole for a moment (an 8K one about 130 MiB).

## What the operator does

* Unpack, then `./install.sh`. The wallpaper restarts with it.
* After a day: `syncrain --diagnose` shows the record's end. "after renewal N, drawing again"
  lines with the heap back near its first value mean it works; resident memory should stay near
  its start. Each renewal is a still picture for a fraction of a second.

## Verification

574 passed, 1 skipped in 1571.43s (0:26:11)
