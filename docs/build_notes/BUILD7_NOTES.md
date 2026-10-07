# Build 7: what the review of build 6 found, fixed

**Type: fix; the picture does not change.** Made on 2026-10-07. Build 6 passed its gate (139 tests)
and was reviewed, as every build that changes what runs on the operator's desktop now is
(`docs/agent/NEXT_BUILD.md`), by an agent that had not written it. The review found one fault an
everyday action shows, so build 6 was not delivered; build 7 is build 6 with three fixes, each held
by a test that fails without it (checked by undoing each fix in turn). The operator has build 5;
build 7 replaces it. The stream is unchanged (48e6bf9c).

## 1. A screen uncovered by a drag draws again during the drag (`syncrain/hidden.py`, the script)

Build 6's script answered bursts of window changes through a single-shot `QTimer` it started on
every change. `QTimer.start()` restarts a running timer, so while a window moved (a drag moves it
every few milliseconds) the answer was put off until the pointer rested. Dragging a maximized window
off a screen (KWin un-maximizes it as the drag starts) left that screen's rain standing still until
the drag stopped. The timer is now started only when it is not running: the answer comes at most
50 ms after a change. On the kwin lane, a window un-maximized and moved every 5 ms for 1.5 s by a
KWin script: with build 6, syncrain drew that screen again 1.58 s after the drag began; with build
7, within 0.6 s, during the drag. `tests/unit/test_the_kwin_script.py` now runs the script's timer
on a clock the test moves, restarting as Qt's does, and drags a window for a second: the screen
shows again within 60 ms, and the script looks at the windows 15 to 25 times, not 200.

## 2. A locked screen no longer moves the lead (`syncrain/pacing.py`)

While a screen is locked, KWin asks the wallpaper for nothing, and the frame committed just before
the lock is reported shown when the screen comes back, minutes after its refresh. Build 6 counted
that as a frame shown late and moved the lead half a millisecond earlier at every unlock. Frames
shown more than two refreshes off their refresh are not counted now (`MAX_MISS`).

## 3. A leftover script's process is recognised by its command (`syncrain/hidden.py`)

Build 6 took a pid as a living syncrain when its command line contained "syncrain", which
`journalctl --user -fu syncrain` or an editor open on `syncrain/app.py` also does, if one of them
took over a crashed syncrain's pid. The check now reads the command as the power sweep does
(`python -m syncrain`, or the Nix package's wrapper).

## 4. What the operator does

* Install build 7 (`./install.sh` from `syncrain_build_7/`); it replaces build 5 and restarts the
  wallpaper. Nothing looks different, except that a screen shows the rain moving again as soon as a
  dragged window leaves it.
* The questions in `docs/ROADMAP.md` are still theirs.

## Verification

141 passed in 364.73s (0:06:04)

Before the gate, by hand: the new drag test on the kwin lane with build 6's timer (fails, 1.58 s)
and with build 7's (passes); the unit tests for each of the three fixes, each failing with its fix
undone.
