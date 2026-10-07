# Build 6: what a review of build 5 found, fixed

**Type: fix; the picture does not change.** Made on 2026-10-07, right after build 5 was delivered.
Build 5 passed its gate (132 tests); then an agent that had not written it reviewed its code against
KWin 6.7.5's and GTK 4.22.5's sources. It found no way for the frame loop to stall or spin, and four
faults, each now held by a test that fails without its fix (checked by undoing each fix in turn).
Such a review is now a step of every build that changes what runs on the operator's desktop
(`docs/agent/NEXT_BUILD.md`). The stream is unchanged (48e6bf9c).

## 1. Frames stay on time above 60 Hz (`syncrain/pacing.py`)

A frame has to reach KWin within one refresh before the refresh it is drawn for: after KWin's
deadline for the refresh before, or it is shown a refresh early, and before the deadline of its own,
or a refresh late. At 60 Hz that window is 16.7 ms wide; at 144 Hz, 7 ms. Build 5 asked for each
frame half a refresh plus 6 ms ahead, a guess at where the window lies that held at 60 Hz. Now the
lead moves by half a millisecond whenever GTK's frame timings report a frame shown a refresh early
(later next time) or late (earlier), within 2 ms and two refreshes plus 6 ms, and frames asked for
before a move are not counted again, so one slow moment moves it once.

Measured on the kwin lane's new 141.33 Hz screen (one 320x180 screen, 30 fps, so every 5th refresh;
reports every 2 s once the lead has settled): build 4's timer 49 to 60% of frames steady; build 5
74 to 84% (spacing 63 to 74%); build 6 86 to 100% (spacing 78 to 100%), the lead settling near 13 ms
here, where software rendering takes about 6 ms a frame. At 60 Hz, as before: 93 to 100%.
`tests/unit/test_the_frame_pacing.py` runs the pacer against a model compositor at 144 and 240 Hz
for drawing times of 1 to 9 ms and KWin margins of 1 to 5 ms, with jitter: at least 95% of frames on
time, where the fixed lead fell to between 0 and 16% in some of them. The debug line and the sweep's
JSON now carry the lead: `..., steady 98%, lead 13.0 ms`.

## 2. The KWin script starts when KWin reuses its number (`syncrain/hidden.py`)

KWin numbers a loaded script by how many scripts it holds (`Scripting::loadScript` returns
`scripts.size()`), so after an earlier script was unloaded the number can be one a running script
already has; asking `/Scripting/Script<n>` to run then reaches the old script, and build 5's never
ran: it said "KWin 5?" and drew under covering windows. When the script has not answered after
1.5 s, syncrain now asks `org.kde.kwin.Scripting.start`, which runs every loaded script that is not
running, and gives up only after 3 s. `syncrain --diagnose` does the same. The kwin lane loads two
scripts, unloads the first and starts syncrain, which then pauses under a maximized window as usual.

## 3. Scripts left by a crashed syncrain are unloaded (`syncrain/hidden.py`)

A syncrain killed before it could unload its script (a crash, SIGKILL) left it running in KWin until
logout, one more for each restart. Its file stays in `$XDG_RUNTIME_DIR` as
`syncrain-watch-<pid>.js`; at start, syncrain unloads the scripts whose process is gone (a pid that
another program took over counts as gone) and deletes their files. The kwin lane kills a syncrain
with SIGKILL and checks that the next one removes what it left.

## 4. Less work on KWin's main thread (`syncrain/hidden.py`, the script)

The script looked at every window against every screen on each change of any window, including each
step of a dragged window. It now reads whether a window is full-screen or maximized before anything
else (most windows are neither; 0.10 to 0.04 ms a pass with 13 windows, timed inside the sandbox's
KWin), and answers a burst of changes once, 50 ms after it ends, through a single-shot `QTimer`. In
`tests/unit/test_the_kwin_script.py` a drag of 200 steps makes the script look at the windows once.

## 5. The kwin lane, thirteen tests

New: a 141 Hz screen, from a `kwinoutputconfig.json` written before KWin starts (`FAST_SCREEN`, the
file KWin writes after `kscreen-doctor output.Virtual-0.addCustomMode.320.180.144000.full`); the
reused script number; the killed syncrain. About two and a half minutes.

## 6. What the operator does

* Install build 6 (`./install.sh` from `syncrain_build_6/`); it replaces build 5 or 4 and restarts the
  wallpaper. Nothing looks different; on screens faster than 60 Hz the motion should be at least as
  steady as with build 5.
* The questions in `docs/ROADMAP.md` are still theirs: the default frame rate, pausing behind
  maximized windows too, the desktop icons. A sweep from build 5 or 6 shows the pause on their card.

## Verification

139 passed in 348.04s (0:05:48)

Before the gate, by hand: the kwin lane twice in a row, thirteen tests each time; each new test run
once with its fix undone, and failing; the timing measured on the 141 Hz screen, two runs of build 6,
one of build 4's timer, as above. Not measured: their card, a real 144 Hz monitor (the lane's fast
screen is a virtual one with software compositing), Plasma's shell.
