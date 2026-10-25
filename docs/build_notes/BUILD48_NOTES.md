# Build 48: the native wallpaper gives back what NVIDIA's driver keeps

**Type: fix; the picture does not change** (stream `c5c869a0` as in build 47). Made on 2026-10-25,
from the operator's report of that day.

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
* `memory.log` gets a line for each: how long it took, the heap after, what it gave back of what
  had grown, resident before and after. A renewal that gives back less than half of 8 MiB or more
  stops renewals (the growth is then not the driver's), and the record says so. One that cannot
  build again stops the wallpaper with status 1, so its service starts it afresh, as after a lost
  compositor. A driver that frees what it makes (Mesa) never reaches 32 MiB, so never renews.
* `SYNCRAIN_RENEW_MIB`: the growth that calls for it (below 0: never; the lane uses 0).

## Measured here (Mesa llvmpipe, headless Sway, two screens)

* A renewal every 5 to 10 s: about 110 ms each (shaders compiled in software included); over 40,
  the heap stayed at 71.0 MiB and resident memory level at about 144 MiB after the first.
* With the clock still, 1,277 grabs across three renewals, every one the first to the pixel: the
  textures come back byte for byte and nothing blanks.
* Not measurable here: NVIDIA's driver and KWin. On the operator's desktop the record shows whether
  a renewal gives the driver's memory back.

## What the operator does

* Unpack, then `./install.sh`. The wallpaper restarts with it.
* After a day: `syncrain --diagnose` shows the record's end. Lines saying "OpenGL made anew" with
  most of the growth given back mean it works; resident memory should stay near its start.

## Verification

GATE_RESULT
