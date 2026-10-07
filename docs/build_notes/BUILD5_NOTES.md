# Build 5: nothing drawn that nobody sees, and every frame drawn for the moment it is shown

**Type: feature (power) and a timing fix; the picture does not change.** Made on 2026-10-07 from
the operator's message at 12:19: build 4's `syncrain --power-sweep` table from their card, with "it
definitely went down linearly together with fps". The stream is unchanged (48e6bf9c, build 3's): any
given moment draws the same frame as in build 4; what changed is which moments are drawn, and when.

## 1. What build 4's sweep said, on the operator's RTX 5090 (two screens)

| phase | card W above "nothing" | frames/s (both screens) |
| --- | --- | --- |
| nothing (Plasma alone) | 50.4 W idle, memory clock at 14001 MHz | |
| as installed: 30 fps, GTK's OpenGL renderer | +10.6 | about 60 |
| 20 fps | +6.9 | about 40 |
| 15 fps | +5.0 | about 30 |
| 10 fps | +3.0 | about 20 |
| half resolution | +9.4 | about 60 |
| GTK's Vulkan renderer (build 3's path) | +25.5 (13% busy, 1507 MHz) | about 60 |
| matrix theme (no snow, no logo) | +9.6 | about 60 |
| covered by a full-screen window | +11.0 | 60.5 |

Read row against row: the watts follow the frames in a straight line, about 0.17 J a frame per
screen, while a quarter of the pixels saves an eighth and no snow a tenth; most of a frame's cost is
the card waking for it, not the drawing, so Rust, C or fewer shader instructions would shave the
small part. Build 4's renderer change had already halved the cost (Vulkan +25.5 W, OpenGL +10.6 W).
And the waste: under a full-screen window syncrain went on drawing 60 frames a second for +11 W,
because KWin, unlike Sway, keeps asking a covered wallpaper for frames.

## 2. A covered screen is not drawn (`syncrain/hidden.py`, `syncrain/app.py`)

KWin sends every surface on a screen its frame callbacks after each frame, covered or not
(`src/scene/item.cpp`, `Item::framePainted`, KWin 6.7.5 and master), so GTK cannot tell that a
wallpaper is hidden. KWin's scripting API knows: on Wayland, when `org.kde.KWin` is on the session
bus, syncrain writes a small script into `$XDG_RUNTIME_DIR`, loads it into KWin over D-Bus
(`org.kde.kwin.Scripting.loadScript`, then `run`), and the script calls back
`org.syncrain.Watch.Covered(screen, covered)` whenever a screen's answer changes: covered when a
maximized or full-screen window is on it, on the current desktop (per screen, as KWin 6.7 allows)
and activity, not minimized, not hidden, not made see-through by KWin. Only KWin's bus name is
believed. A screen that is covered asks for no frames until it shows again, and then draws at once.
While KWin shows the desktop nothing counts as covered. The script only reads; syncrain unloads it
and deletes the file when it stops; a script that never answers (KWin 5) is dropped after 3 s and
syncrain draws as before. Once KWin has answered, the journal says "drawing pauses on a screen under
maximized and full-screen windows (KWin)"; `syncrain --diagnose` adds a "covering windows" section.

`--pause-under maximized` (the default), `fullscreen` or `never`; the NixOS and home-manager
modules have `pauseUnder`. A window that is see-through by itself (a terminal with a translucent
background) still counts as covering, so the rain stands still behind it; that is the question to
the operator in `docs/ROADMAP.md`.

Tried and dropped: KWin's `org_kde_plasma_window_management` protocol, which tells any permitted
client every window's state. KWin 6.0 to 6.7 permit it only to an executable named in a desktop
file's `X-KDE-Wayland-Interfaces`, and syncrain's executable is Python, so the grant would cover
every Python program.

Held by `tests/unit/test_the_kwin_script.py` (the script run in Node against a stand-in KWin: which
windows cover which screen, and that it reports only changes) and by the new kwin lane (section 5),
which first shows KWin still asking a covered wallpaper for frames (`--pause-under never`) and then
the pause under a full-screen window, a maximized one on one screen of two, a minimized one, KWin's
show desktop, `--pause-under fullscreen`, and the script leaving KWin with the wallpaper.

## 3. Frames on whole refreshes, each drawn for the refresh it is shown on (`syncrain/pacing.py`)

Build 4 asked every screen for a frame from one GLib timer every 33 ms and drew it for the instant
the timer fired. The screen shows a frame at its next refresh, anywhere up to a refresh later, so
the motion stepped unevenly even when the frames were evenly spaced. Now each screen asks on its own:
after a frame, the pacer takes the refresh grid GTK keeps from the compositor's presentation
feedback (`GdkFrameClock.get_refresh_info`), picks the refresh N after the last one (N the fewest
whole refreshes that keep the rate at or under `--fps`: every 2nd at 60 Hz, every 5th at 144 Hz,
28.8 fps), asks for the frame half a refresh plus 6 ms before it, and draws it for that refresh's
moment. Without a grid (X11 without a compositor, the first frame on a screen) it asks one period
later, as before. Nothing ticks between frames, so a frame asks for the next whatever happens to it:
one that raises is reported and the wallpaper goes on (`tests/render/test_the_app_draws.py`, which
fails the frame on purpose). `--pacing timer` (hidden) keeps build 4's way for the sweep's comparison.

Measured on the kwin lane's headless KWin 6.7.5 (one 320x180 screen at 60 Hz, 30 fps, two reports a
run, two runs each): build 4's timer 29.7 fps, 85 to 98% of frames shown 2 refreshes apart, 17 to 44%
"steady" (shown the usual delay after the moment drawn for, within 2 ms); build 5 30.0 fps, 90 to
100% and 95 to 100%. `SYNCRAIN_DEBUG_FPS` now prints both shares:
`syncrain: 30.0 fps at 320x180 (area 0), spacing 2 refreshes 100%, steady 100%`.

Tried and dropped: growing the lead by a refresh whenever a frame was shown late. KWin shows a
frame at the first refresh after it arrives, so every later frame was then shown a refresh early
(steady fell to 0%); a card too slow for the lead shows every frame a refresh late instead, which
keeps the steps even. Held by `tests/unit/test_the_frame_pacing.py` (whole refreshes at 60, 120,
144, 165 and 75 Hz; a late frame takes the soonest refresh it can make; a rounded refresh interval
does not drift off the screen's grid) and the kwin lane's timing test, which also checks that build
4's timer is not as steady.

## 4. The sweep, for build 5 (`syncrain/power.py`, `syncrain/cover.py`)

Seven phases, about three minutes: nothing; as installed; build 4's frame timer; 20 and 15 fps;
behind a maximized window (`python -m syncrain.cover --maximized`: one per screen, full screen on
it first, since xdg-shell lets a client choose a screen only for that); behind a full-screen window.
The rows build 4 settled (half resolution, Vulkan, the matrix theme, 10 fps) are gone. Two new
columns, "even" and "steady", from the wallpaper's own reports; the JSON (contract
`syncrain-power-sweep-1`) gains each phase's `timing` and `pause` line. `--pause-under` passes on
to every phase.

## 5. The kwin lane (`tests/kwin/`)

KWin 6.7.5 and its Qt 6 and KDE Frameworks from the nixpkgs checkout's binary cache
(`SYNCRAIN_KWIN`), started with `--virtual` (software compositing, 60 Hz screens) on a private
session bus, with two 320x180 screens for the pause and the sweep and one for the timing (small, so
the sandbox's software rendering keeps up); syncrain on its bottom layer as on the operator's
desktop (`XDG_CURRENT_DESKTOP=KDE`); `tests/kwin/window.py` for maximized, full-screen, minimized
and desktop-type windows. Ten tests, about two minutes, the last of them build 5's whole sweep with
a stand-in power reading: 0 frames behind a maximized and behind a full-screen window, and "steady"
as installed at least 20 points above build 4's timer (by hand: 100% against 27%; within the full
lane, where the sweep's own sampling shares the two processors, 68 to 97% as installed over four
runs, and 33% for the timer in the run that kept its file).
`syncrain --diagnose` there lists both screens at 60 Hz and "KWin answers". Plasma's shell (panel,
desktop, its own wallpaper) is not there. `tools/prepare_environment.sh --verify` checks for KWin,
and `docs/agent/ENVIRONMENT.md` says how to fetch it.

## 6. Found on the way

* **To KWin, syncrain is an ordinary window.** A layer-shell surface gets the window type its
  namespace names ("desktop", "dock" and a few more); "syncrain" names none. So KWin's show desktop
  hides syncrain along with every window, and Plasma's own wallpaper shows meanwhile. A "desktop"
  namespace keeps syncrain on screen during show desktop (tried in the kwin lane) but also makes it
  the desktop KWin hands the keyboard to, which on Plasma belongs to Plasma's own desktop. Not
  changed here; it is part of the KDE question in `docs/ROADMAP.md`.
* KWin's `showDesktop(true)` lasts only while its caller stays on the bus (`docs/LESSONS.md`).

## 7. What the operator does

* Install build 5 (`./install.sh` from `syncrain_build_5/`); it restarts the running wallpaper.
* Look: the rain and the snow should move at least as smoothly as before. Maximize a window over a
  screen: nothing changes on screen, and the card draws no more than with a still wallpaper.
  `syncrain --diagnose` lists "covering windows" and what KWin says right now.
* Answer, when convenient: the default frame rate, and whether maximized windows should pause it
  too (`docs/ROADMAP.md`). If still at hand, send build 4's `syncrain-power-<time>.json` (it has the
  card's clocks per row); a new `syncrain --power-sweep` (about three minutes) shows build 5 on
  their card.

## Verification

132 passed in 329.80s (0:05:29)

Before the gate, by hand: the kwin lane four times in a row (before its last two tests existed) and
again with all ten; the timing comparison above, two runs of each way; the sweep on KWin as above.
Not
measured: any real card's watts with build 5, Plasma's shell around the pause (panel, desktop
effects), KWin on X11, GTK's Vulkan renderer.
