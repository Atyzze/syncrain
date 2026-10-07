# The next build is 8

This file names the next build and says how to make it. `tests/contract/test_the_working_documents_are_current.py`
fails if the number in the first line is not exactly one above `BUILD_NUMBER`, so shipping build 8
without rewriting this page for 9 breaks the gate. The first line is parsed: it must read exactly
`# The next build is <N>`.

## Where to begin

Build 8 is made from the operator's answers to the three questions in `docs/ROADMAP.md` ("Questions
for the operator") and, if they ran it, a `syncrain --power-sweep` of build 5 or 7 on their card. Read what
they sent before anything else and answer it in one plain sentence first.

**The default frame rate.** If they choose 20 or 15, the default lives in four places that must
agree: `--fps` in `syncrain/app.py` (`parse_args`), `fps` in `nix/options.nix`, the default in
`syncrain/power.py` (`base_args`) and the options table in `docs/OPERATIONS.md`. The sweep's "as
installed" phase then measures the new default; keep a "30 fps" phase so the table still shows
the difference. Smoothness at the new rate is the pacer's: at 60 Hz, 20 fps is every 3rd refresh.

**Maximized or only full-screen.** If only full-screen, the default of `--pause-under` becomes
`fullscreen` in `syncrain/app.py`, `pauseUnder` in `nix/options.nix` (and the comparison in
`nix/args.nix`, which leaves the default out of the command line), `syncrain/power.py` (`base_args`)
and `docs/OPERATIONS.md`; the kwin lane's tests name the policy they test, so only the startup-line
test changes.

**A sweep of build 5 or 7, if sent** (`~/syncrain-power-<utc>.json`, contract
`syncrain-power-sweep-1`; build 7's rows also carry `lead_ms`), row against row ("above" is the power
above "nothing"):

* **Behind a maximized window, behind a full-screen window.** Expected: 0 frames a second and
  "above" near zero. Frames still drawn mean the pause did not engage on their Plasma: the JSON's
  `pause` field says whether KWin answered at all; `syncrain --diagnose` there says what KWin
  reports per screen. Plasma's shell (its panel, its effects) is the part the kwin lane cannot run.
* **As installed against build 4's frame timer.** Watts about equal (the frame counts are); "steady"
  near 100% as installed and lower with the timer, as on the kwin lane. If "steady" is low as
  installed, ask for `syncrain --diagnose` (its "screens" section has each screen's refresh rate);
  a lead pinned at 2 ms or at two refreshes plus 6 ms says the window was never found
  (`syncrain/pacing.py`, `Pacer.shown`).
* **20 and 15 fps.** Watts should follow build 4's line (+6.9 W, +5.0 W); "even" and "steady"
  near 100% at those rates too.

**Known blockers.** Watts and Plasma's shell exist only on the operator's machine. A sweep taken
with the GIF still as Plasma's wallpaper measures syncrain against a desktop that already costs
about 20 W; if their "nothing" is far above 50 W, ask for a run with a still wallpaper.

**Acceptance.** The chosen defaults in every place that holds them, with a test that reads each
default from where it is set; every lane passes; if they sent a sweep, its numbers in the notes of
build 8, row by row, with what each says.

## The Plasma wallpaper plugin, if chosen

A Plasma 6 wallpaper package (`metadata.json` with `KPackageStructure: Plasma/Wallpaper`,
`contents/ui/main.qml`) that draws syncrain behind the desktop icons, chosen in Plasma's own
wallpaper settings, installed by `install.sh --plasma` into `~/.local/share/plasma/wallpapers/`.
Two ways to draw: the web page in a `WebEngineView` (needs qt6-webengine; simplest, and the page is
already checked against the app), or the shaders in a QML `ShaderEffect` (no browser engine, but
Qt's shader pipeline needs the shaders rewritten for it and a second host implementation). Since the
watts follow the frames, the plugin must keep build 5's two savings: no frames for a covered screen
(Plasma knows its windows; KWin's script is not needed inside the shell) and frames on the refresh.
As part of Plasma's own desktop it also stays on screen during show desktop, which the layer-shell
wallpaper does not (KWin treats that one as an ordinary window).

**Known blockers.** Plasma's shell cannot run in the build sandbox (KWin can: `tests/kwin/`), so
nothing there can show the plugin working; the operator's machine is its first test, and the notes
must say so. qt6-webengine is a large package (CachyOS has it in `extra`), so `install.sh` should
ask before adding it.

**Acceptance.** The operator picks "syncrain" in Plasma's wallpaper dialog on both screens; the
icons are on top; the frame matches `syncrain --window` on the same channel and second; the sweep
shows its cost next to the layer-shell wallpaper's.

## Before anything

Bring the sandbox up (`docs/agent/ENVIRONMENT.md`); `tools/prepare_environment.sh --verify` lists
what is missing, KWin 6 included. Then run the full lane once on the untouched tree.

## How to make a build

1. Make the change. Comments say why, not when; tests assert behaviour; a guard that fires is
   usually right.
2. If a stream file changed (a shader, `themes.json`, the atlas, a logo, `syncrain/engine.py`),
   decide whether the picture is meant to change. If it is: `python3 tools/stream_freeze.py --write`
   and say in the notes that machines on build 7 and build 8 no longer match. If not, undo it.
3. Write the notes for build 8 under `docs/build_notes/`, named for its number like the others:
   a title line `# Build 8: <what it does>`, a `**Type: ...**` line (it says "consolidation"
   exactly when the number ends in 0), the changes with the files and tests that hold them, what
   the operator does, and a `## Verification` section whose result line is the bare token
   GATE_RESULT; the release writes the gate's summary in its place.
4. Update `docs/ROADMAP.md` ("Where things stand", the questions, the decisions, the planned builds),
   rewrite `docs/agent/HANDOFF.md` and `docs/WHERE_WE_ARE.md` for build 8, and fold anything new
   into `docs/LESSONS.md` and `docs/HISTORY.md`.
5. **Rewrite this file for build 9**, keeping the first line exactly `# The next build is 9`.
6. Run the release detached (the gate takes about seven minutes; the browser lane is the slowest,
   the kwin lane next):

```
setsid nohup python3 tools/package_release.py --output <dir> > release.log 2>&1 < /dev/null &
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
9. Deliver the archive it wrote, `SYNCRAIN8.tar.zst`, and nothing else. Republish the live page
   from `web/artifact.html` (it carries the build number) and say what the operator does.

**Three checks fail by one between releases**, once the documents are rewritten for the build
being made: this page's first line, the one page's first line and the handoff's first line all
name a number the tree does not carry yet. The release writes `BUILD_NUMBER` before it runs the
gate, so they pass inside it, and only there. That is correct; any other failure is not.

## What not to do

* Do not ask GTK for an OpenGL version, and do not trust a sandbox result about OpenGL that Mesa
  could be hiding: force the API in the lanes.
* Do not claim watts from the sandbox: it has no graphics card. Watts come from the operator's sweep.
* Do not ask for a frame earlier than about a refresh before it is meant to be shown: the
  compositor shows it at the next refresh, early (`docs/LESSONS.md`).
* Do not change the stream in a build about something else.
* Do not hand over a patch, a hand-made tar, or a build whose gate skipped a lane.
* Do not use long dashes, in the tree or in replies.
