# Build 9: the sweep warns before every screen goes black

**Type: fix; the picture does not change.** Made on 2026-10-09. The operator installed build 8 on
their desktop, ran its power sweep and wrote back at 11:36: "success, definitely less cpu and
memory used, and 122MB feels way more acceptable and natural even than 330 and 400+ thats for a
wallapper .... too heavy, 122 on the other hand feels just right for something like this, so,
update the github please, also, the power-sweep should have a warning message in it that in the
last two tests, all your screens might go black for a while". Build 8 went to GitHub as the commit
`syncrain build 8`, the archive's tree byte for byte. Build 9 adds the warning, and two small things
their sweep and the warning led to. The stream is unchanged (48e6bf9c).

## 1. Build 8 on the operator's machine

Their sweep (RTX 5090, two screens, KDE Plasma; 25 s phases, the last 17 s of each measured):

| phase | card W | above | frames/s | even | steady | cpu % | MiB | drawn by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| nothing (the desktop alone) | 50.4 | | | | | | | |
| as installed (30 fps) | 62.3 | +11.9 | 60.0 | 97% | 98% | 0.9 | 182 | native |
| the Python and GTK host | 61.1 | +10.6 | 60.0 | 100% | 100% | 4.7 | 205 | gl |
| build 4's frame timer | 59.9 | +9.5 | 60.5 | 90% | 47% | 4.7 | 200 | gl |
| --fps 20 | 57.7 | +7.3 | 40.0 | 100% | 100% | 0.8 | 123 | native |
| --fps 15 | 54.0 | +3.5 | 30.0 | 100% | 100% | 0.5 | 123 | native |
| behind a maximized window | 50.1 | -0.3 | 0.0 | | | 0.0 | 123 | native |
| behind a full-screen window | 50.3 | -0.1 | 0.0 | | | 0.0 | 123 | native |

What it says:

* **The native wallpaper runs on NVIDIA's driver**: "OpenGL ES 3.2 on NVIDIA GeForce RTX 5090/PCIe/SSE2,
  native wallpaper, 2 screens", with KWin's pause engaged ("drawing pauses on a screen under
  maximized and full-screen windows (KWin)"). Covered screens draw nothing and cost nothing.
* **Processor**: 0.9% of one core at 30 fps against 4.7% for the GTK host, five times less; 0.8 and
  0.5% at 20 and 15 fps.
* **Memory**: 123 MiB, against 205 for the GTK host (and 287 to 420 for build 7 in btop). The
  first native phase kept 182: most likely the first start of the native program on that machine,
  when NVIDIA's shader cache did not have its shaders yet (section 3).
* **Watts**: +11.9 W as installed against +10.6 W for the GTK host. Each row is one 17-second
  average, and the rows move by a watt or more from run to run: build 4's sweep had the GTK host
  at +10.6 W and 20 and 15 fps at +6.9 and +5.0 W, where the native wallpaper now has +7.3 and
  +3.5 W. Nothing here separates the two hosts' watts, which is what the shaders predict: the card
  draws the same frames. A sweep with `--sweep-seconds 60` would narrow it.
* **Timing**: "even" 97% and "steady" 98% at 30 fps on their screens; 100% at 20 and 15 fps.

## 2. The warning (`syncrain/power.py`)

Before the first phase the sweep now says, when its plan covers the screens:

    Warning: in the last two phases (behind a maximized window, behind a full-screen window) a black
    window covers every screen, so all your screens go black for about 56 s. That is the test, not a
    fault: they come back by themselves when the sweep ends. To get them back sooner, close the black
    windows (Alt+F4) or press Ctrl+C here.

and each covering phase's line ends "(every screen goes black now, for about 25 s)". A closed
terminal (SIGHUP) or `kill` (SIGTERM) now stops the sweep as Ctrl+C does, stopping its wallpaper and
its black windows on the way out; before, either ended the sweep and left the black windows, which
run in sessions of their own, on every screen (`interrupted_by_hangup`). Tests:
`tests/unit/test_the_power_sweep_parts.py` (the warning's words, and both signals), and the kwin
lane's sweep, which now looks for the warning and the phase's note in the sweep's output.

## 3. Memory handed back after the first frames (`syncrain/native/wallpaper.c`)

The first start of the native program with a cold shader cache (after an install or a driver
update) left the driver's compiler working space in the C heap until the process ended. Once every
screen shown has drawn its first two frames, after startup and again after the screens change, the
native wallpaper now hands the heap's free pages back (`malloc_trim`), as the GTK host has done
since build 8 (`settle_memory`). In the sandbox (one 640x360 screen, llvmpipe): 155 MiB with a cold
cache before, 142 now; 133 with a warm cache either way. What it does with NVIDIA's compiler only
the operator's machine can say: the sweep's first native row after a driver update will show it.
With `SYNCRAIN_DEBUG_FPS` set, both hosts say when they have done it ("memory handed back after the
first frames (123 MiB resident)"); the wayland lane checks that both do it at startup and again
after a new screen appears, and fails with the native wallpaper's re-arming undone.

## 4. What the operator does

* Nothing is required: build 9 draws exactly what build 8 does. To have the warning, unpack
  `SYNCRAIN9.tar.zst` and run `./install.sh` from `syncrain_build_9/`.
* The three questions in `docs/ROADMAP.md` are still theirs.

## Verification

184 passed in 568.96s (0:09:28)

Before the gate, by hand: the unit, native and wayland lanes; the memory of section 3 measured with
build 8's and build 9's programs side by side, twice; the wayland lane's new test, failing with the
native wallpaper's re-arming undone.
