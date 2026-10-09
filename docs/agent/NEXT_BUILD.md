# The next build is 9

This file names the next build and says how to make it. `tests/contract/test_the_working_documents_are_current.py`
fails if the number in the first line is not exactly one above `BUILD_NUMBER`, so shipping build 9
without rewriting this page for 10 breaks the gate. The first line is parsed: it must read exactly
`# The next build is <N>`.

## Where to begin

Build 8 went to the operator in the chat, not to GitHub: they asked to try it first ("do not push
to github when done, instead, just deliver the new build here in chat so I can try it out myself
before we commit it", 2026-10-09). So first read what they sent about it, and answer it in one
plain sentence first.

* **They approve it**: commit build 8's tree to `main` as one commit, `syncrain build 8`, and push
  (step 10 below). The tree is the archive `SYNCRAIN8.tar.zst` byte for byte; if the sandbox that
  made it is gone, unpack the archive over a clone of `main` (627a9e2, build 7 plus documentation)
  and commit that. Ask whether build 9 should wait for their word the same way.
* **The native wallpaper did not draw on their machine**: the GTK host takes over by itself before
  the first frame, and the journal (or the terminal) says "the native wallpaper cannot draw here
  (...); the GTK host takes over". Ask for `syncrain --diagnose`: its "native wallpaper" section
  names what the program found (layer-shell, presentation-time, the screens, the OpenGL it got,
  whether the shaders compiled). NVIDIA's EGL is the part the sandbox never ran: one context made
  current on each screen's window surface in turn, `eglSwapInterval(0)`, OpenGL ES unless GTK's
  switches say otherwise (`syncrain/native/render.c`).
* **It drew, but something looks or moves differently**: `syncrain --host gtk` draws the same
  frames through Python and GTK, as build 7 did; ask which one looks right. Frame timing:
  `SYNCRAIN_DEBUG_FPS=2 syncrain` prints "even" and "steady" for either host.
* **A sweep, if sent** (`~/syncrain-power-<utc>.json`, contract `syncrain-power-sweep-1`; build 8's
  rows add `cpu_percent`, `resident_mib` and the startup line that says what drew them), row
  against row ("above" is the power above "nothing"):
  * **As installed against the Python and GTK host**: the watts about equal (same frames, one
    full-screen copy fewer per frame and screen for the native wallpaper), the processor time and
    the memory lower as installed. On a screen at a fractional scale the GTK host also draws 1.8 to
    2.6 times the pixels (`docs/ARCHITECTURE.md`, "Three hosts"), so ask for the screens' scales
    (`syncrain --diagnose`) before reading a difference in watts. If the watts differ by more than
    that explains, it is news: write it into the notes of build 9.
  * **Behind a maximized window, behind a full-screen window**: 0 frames a second and "above" near
    zero, now with the native wallpaper's own KWin watch (`syncrain/native/kwin.c`). Frames drawn
    there mean the pause did not engage: the row's `pause` field says whether KWin answered.
  * **20 and 15 fps**: watts on build 4's line (+6.9 W, +5.0 W); "even" and "steady" near 100%.

**The three questions** in `docs/ROADMAP.md` are still open. If they choose a default frame rate of
20 or 15, the default lives in four places that must agree: `--fps` in `syncrain/app.py`
(`parse_args`), `fps` in `nix/options.nix`, the default in `syncrain/power.py` (`base_args`) and the
options table in `docs/OPERATIONS.md`; the native wallpaper takes `--fps` from the launcher. If only
full-screen windows should pause, the default of `--pause-under` becomes `fullscreen` in
`syncrain/app.py`, `pauseUnder` in `nix/options.nix` (and the comparison in `nix/args.nix`),
`syncrain/power.py` (`base_args`) and `docs/OPERATIONS.md`.

**Known blockers.** Watts, NVIDIA's driver and Plasma's shell exist only on the operator's machine.
The sandbox measures memory and processor time on llvmpipe, where the driver itself is a third of
the native wallpaper's memory and most of each frame's processor time; say which machine every
number comes from.

**Acceptance.** Whatever the operator reports about build 8, reproduced where the sandbox can
(the lanes run both hosts) and fixed with a test that fails without the fix; their chosen defaults
in every place that holds them; every lane passes; a sweep's numbers, if sent, in the notes of
build 9, row by row.

## The Plasma wallpaper plugin, if chosen

A Plasma 6 wallpaper package (`metadata.json` with `KPackageStructure: Plasma/Wallpaper`,
`contents/ui/main.qml`) that draws syncrain behind the desktop icons, chosen in Plasma's own
wallpaper settings, installed by `install.sh --plasma` into `~/.local/share/plasma/wallpapers/`.
Two ways to draw: the web page in a `WebEngineView` (needs qt6-webengine; simplest, and the page is
already checked against the GTK host), or the shaders in a QML `ShaderEffect` (no browser engine,
but Qt's shader pipeline needs the shaders rewritten for it and a fourth host implementation).
Since the watts follow the frames, the plugin must keep build 5's two savings: no frames for a
covered screen (Plasma knows its windows; KWin's script is not needed inside the shell) and frames
on the refresh. As part of Plasma's own desktop it also stays on screen during show desktop, which
the layer-shell wallpaper does not (KWin treats that one as an ordinary window).

**Known blockers.** Plasma's shell cannot run in the build sandbox (KWin can: `tests/kwin/`), so
nothing there can show the plugin working; the operator's machine is its first test, and the notes
must say so. qt6-webengine is a large package (CachyOS has it in `extra`), so `install.sh` should
ask before adding it.

**Acceptance.** The operator picks "syncrain" in Plasma's wallpaper dialog on both screens; the
icons are on top; the frame matches `syncrain --window` on the same channel and second; the sweep
shows its cost next to the layer-shell wallpaper's.

## Before anything

Start from a clone of `main` (github.com/Atyzze/syncrain), with build 8 committed to it once the
operator has approved it (above); without access to the repository, ask for it first. Bring the
sandbox up (`docs/agent/ENVIRONMENT.md`); `tools/prepare_environment.sh --verify` lists what is
missing, KWin 6 and the native wallpaper's build tools included. Then run the full lane once on the
untouched tree.

## How to make a build

1. Make the change. Comments say why, not when; tests assert behaviour; a guard that fires is
   usually right. A change to what a frame computes is made in both Linux hosts (`syncrain/` and
   `syncrain/native/`) and in the page, or the lanes that compare them fail.
2. If a stream file changed (a shader, `themes.json`, the atlas, a logo, `syncrain/engine.py`),
   decide whether the picture is meant to change. If it is: `python3 tools/stream_freeze.py --write`,
   say in the notes that machines on build 8 and build 9 no longer match, and make the README's
   pictures again (`docs/OPERATIONS.md`, "Recipes"). If not, undo it.
3. Write the notes for build 9 under `docs/build_notes/`, named for its number like the others:
   a title line `# Build 9: <what it does>`, a `**Type: ...**` line (it says "consolidation"
   exactly when the number ends in 0), the changes with the files and tests that hold them, what
   the operator does, and a `## Verification` section whose result line is the bare token
   GATE_RESULT; the release writes the gate's summary in its place.
4. Update `docs/ROADMAP.md` ("Where things stand", the questions, the decisions, the planned builds),
   rewrite `docs/agent/HANDOFF.md` and `docs/WHERE_WE_ARE.md` for build 9, and fold anything new
   into `docs/LESSONS.md` and `docs/HISTORY.md`.
5. **Rewrite this file for build 10**, keeping the first line exactly `# The next build is 10`.
   Build 10 is a consolidation build (`docs/ROADMAP.md`, "Build cadence").
6. Run the release detached (the gate takes about ten minutes on two cores; the browser lane is the
   slowest, the kwin lane next):

```
setsid nohup python3 tools/package_release.py --output <dir> > ../release.log 2>&1 < /dev/null &
```

7. The release refuses on any failing test and puts `BUILD_NUMBER` back. Read the failure, fix the
   cause rather than the test, and run it again. A killed release is undone by the next run from
   its journal; never edit `BUILD_NUMBER` by hand.
8. **Have the change reviewed by an agent that did not write it** when it changes what runs on the
   operator's desktop: point it at the tree and at the previous build's, ask for concrete faults
   with a failure scenario each, and turn each real one into a test that fails without its fix
   (builds 6 and 7 are what the reviews of builds 5 and 6 found). Read-only; the release does not
   wait for it, but nothing is delivered before it reports: a fault the operator would meet in
   everyday use makes the next build first (build 6 was not delivered for one), anything rarer goes
   into the delivery message and the next build.
9. Deliver the archive it wrote, `SYNCRAIN9.tar.zst`, and nothing else. Republish the live page
   from `web/artifact.html` (it carries the build number) and say what the operator does.
10. Commit the tree the release left to `main` as one commit, `syncrain build 9`, and push it, once
    the operator has said it may go (they asked to try build 8 before it was committed; ask whether
    that holds for build 9). With `<dir>` and the log outside the tree it is the archive's, byte for
    byte; `git status` shows only the build's own changes. The commit's name marks the build, since a
    session cannot push a tag (`docs/agent/ENVIRONMENT.md`, "What the sandbox gets wrong").

**Three checks fail by one between releases**, once the documents are rewritten for the build
being made: this page's first line, the one page's first line and the handoff's first line all
name a number the tree does not carry yet. The release writes `BUILD_NUMBER` before it runs the
gate, so they pass inside it, and only there. That is correct; any other failure is not.

## What not to do

* Do not ask GTK for an OpenGL version, and do not trust a sandbox result about OpenGL that Mesa
  could be hiding: force the API in the lanes (the native wallpaper follows the same switches).
* Do not claim watts from the sandbox: it has no graphics card. Watts come from the operator's sweep.
  Memory and processor time measured there include llvmpipe; say so beside every such number.
* Do not ask for a frame earlier than about a refresh before it is meant to be shown: the
  compositor shows it at the next refresh, early (`docs/LESSONS.md`).
* Do not change the stream in a build about something else.
* Do not compute in C what Python already prepares: the scene carries everything that never
  changes (`syncrain/native.py`), so there is one source of truth for it.
* Do not hand over a patch, a hand-made tar, or a build whose gate skipped a lane.
* Do not use long dashes, in the tree or in replies.
