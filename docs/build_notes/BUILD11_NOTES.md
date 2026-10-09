# Build 11: no memory creep on NVIDIA

**Type: fix; the picture does not change.** Made on 2026-10-09.

## The creep

* On the operator's desktop the native wallpaper grew about 0.9 MiB a minute while it drew (btop:
  123 MiB at start, 154 after 44 minutes, 200 after about 90). The C program has no garbage
  collector, so nothing would have come back.
* Not syncrain's own: on Mesa it stays flat (55,000 frames each under KWin and under Sway).
* NVIDIA's Wayland driver keeps a small allocation for every frame presented while explicit sync is
  on. NVIDIA's forum has it with Mesa's `eglgears_wayland` alone (RTX 5080, driver 610.43.02,
  egl-wayland2 1.0.2, May 2026): +2 MiB a minute, flat with `__NV_DISABLE_EXPLICIT_SYNC=1`.

## The fix (`syncrain/app.py`, `avoid_the_explicit_sync_leak`)

* syncrain sets `__NV_DISABLE_EXPLICIT_SYNC=1` and `__GL_YIELD=USLEEP` for its own process before
  GTK starts; the native wallpaper inherits both. Values the user set win; other drivers ignore
  them; other programs keep explicit sync.
* With explicit sync off, NVIDIA's driver syncs implicitly; `__GL_YIELD=USLEEP` lets it sleep, not
  spin, while it waits for a frame.
* Tests: `tests/unit/test_the_environment_gtk_starts_in.py` (set before GTK is imported, handed to
  the native program, the user's values kept).

## Build 9's review, fixed

* The sweep saves its JSON before it prints: a closed terminal no longer loses it.
* A second Ctrl+C, hang-up or kill no longer cuts the sweep's cleanup short.
* `nohup syncrain --power-sweep` survives its terminal again.
* The warning says Alt+Tab to the terminal and Ctrl+C (Alt+F4 left a phase measuring an uncovered
  wallpaper), and "about 25 s in each".
* The native wallpaper waits for a new screen's first frames before settling its memory.
* Tests: `tests/unit/test_the_power_sweep_parts.py`.

## What the operator does

* Install it (`./install.sh` from `syncrain_build_11/`); btop should stay near 123 MiB for hours.

## Verification

189 passed in 533.26s (0:08:53)
