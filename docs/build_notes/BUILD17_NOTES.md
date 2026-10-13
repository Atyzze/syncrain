# Build 17: the box on every screen, no seam after the login

**Type: feature; the picture does not change** (stream `def5684f`). Made on 2026-10-13.

## On build 16 at the operator's desktop

* It worked on the first boot: KWin, the rain on both screens, the box, Plasma after it.
* The box was on one screen only ("I want it displayed always on all screens").
* After the login: Plasma's black splash with its logo, then for a second the old wallpaper, then
  the rain.
* Their login screen before was Plasma Login (`plasmalogin.service`), not SDDM; build 16's
  installer found it and keeps it to go back to.

## The box on every screen (`syncrain/greeter.py`)

* One box per screen, all the same box: what is typed in one shows in all of them (shared entry
  buffers), and so do the session, the messages and the password's peek.
* A screen plugged in or out gets its box, or loses it, at once.

## From the login to the desktop (`syncrain/handover.py`)

* `install.sh --login-screen` makes a still frame of the rain at your largest screen's size (a
  window opens for a moment) and shows it as Plasma's splash after a login (a splash package of
  syncrain's) and as the wallpaper of every desktop. So: the login's rain, the still, the rain.
* What the splash and the wallpapers were is kept; `--login-screen-off` and `--uninstall` put them
  back. A newer build's `./install.sh` makes the still again.

## Tests

* Two screens in headless KWin: a box shown on each (`tests/kwin/test_a_login_in_kwin.py`).
* The splash file and the wallpapers on and off against a stand-in for Plasma's shell
  (`tests/unit/test_the_handover.py`).
* By hand in an Arch root, with Plasma's real shell: the still, the splash package Plasma lists,
  the wallpaper set and put back (an empty image is Plasma's default), `ksplashqml` loading it.

## What the operator does

* `./install.sh --login-screen` from `syncrain_build_17/` inside Plasma, then log out (or reboot).

## Verification

238 passed in 616.96s (0:10:16)
