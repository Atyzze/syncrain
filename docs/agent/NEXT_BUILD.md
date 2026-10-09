# The next build is 10

This file names the next build and says how to make it. `tests/contract/test_the_working_documents_are_current.py`
fails if the number in the first line is not exactly one above `BUILD_NUMBER`, so shipping build 10
without rewriting this page for 11 breaks the gate. The first line is parsed: it must read exactly
`# The next build is <N>`.

## Where to begin

**Build 10 is a consolidation build** (`docs/ROADMAP.md`, "Build cadence"): it changes no behaviour.
Read what the operator sent last before anything else, and answer it in one plain sentence first;
if it asks for a change, the change is build 11's (say so), unless it is a fault they meet in
everyday use, which goes first as a build of its own and moves the consolidation to the next number
that ends in 0 only if the operator agrees.

What build 10 does:

* **Fold the older notes into `docs/HISTORY.md`**: builds 1 to 8 become a paragraph each there
  (what changed, why, what was measured, what the operator said), and their notes files go. Keep
  build 9's notes (the gate wants the previous build's) and write build 10's.
* **Make every standing document true now, in the present tense**: the documents grew a build at a
  time ("build 5 asks KWin", "build 8's notes have"), and a reader wants what is, with a pointer to
  the history for when. Check each against the code: `docs/ARCHITECTURE.md` (the three hosts, the
  passes, the pacer, the memory), `docs/OPERATIONS.md` (every option against `--help`, every recipe
  run once), `README.md`, `docs/agent/ENVIRONMENT.md` (run `tools/prepare_environment.sh --verify`
  on a fresh sandbox if one is at hand), `docs/agent/TARGET_ENVIRONMENT.md`, `docs/LESSONS.md` (a
  lesson that no longer guides anything goes to the history).
* **Prune `docs/ROADMAP.md`** and rewrite this page for build 11: the operator's three questions,
  and the open items below.
* **Write down, do not make**, what is open: a sweep with longer phases (`--sweep-seconds 60`) to
  tell whether the two hosts' watts differ at all (+11.9 W and +10.6 W in one 17-second sample
  each); what build 9's settling saves after an NVIDIA driver update (the operator's first native
  row was 182 MiB, the later ones 123); a driver that fails after the first frame every time makes
  the service restart the native wallpaper every 3 s without the GTK host taking over; a sweep
  stopped by a closed terminal cannot print its table or save its JSON, since its terminal is gone.

**Known blockers.** None in the sandbox; the operator's answers are build 11's, not this one's.

**Acceptance.** No file outside `docs/`, `README.md` and the notes changes (the gate's other lanes
pass unchanged, and `git diff` shows no code); every pointer in the documents lands (the contract
lane checks it); the history holds builds 1 to 9; this page names build 11 and what it needs.

## Build 11: the operator's answers

**The three questions** in `docs/ROADMAP.md`. If they choose a default frame rate of 20 or 15, the
default lives in four places that must agree: `--fps` in `syncrain/app.py` (`parse_args`), `fps` in
`nix/options.nix`, the default in `syncrain/power.py` (`base_args`) and the options table in
`docs/OPERATIONS.md`; the native wallpaper takes `--fps` from the launcher. If only full-screen
windows should pause, the default of `--pause-under` becomes `fullscreen` in `syncrain/app.py`,
`pauseUnder` in `nix/options.nix` (and the comparison in `nix/args.nix`), `syncrain/power.py`
(`base_args`) and `docs/OPERATIONS.md`.

**A sweep, if sent** (`~/syncrain-power-<utc>.json`, contract `syncrain-power-sweep-1`), row against
row with build 8's in `docs/build_notes/BUILD9_NOTES.md`; on a screen at a fractional scale the GTK
host also draws 1.8 to 2.6 times the pixels (`docs/ARCHITECTURE.md`, "Three hosts"), so ask for the
screens' scales (`syncrain --diagnose`) before reading a difference in watts between the hosts.

**Known blockers.** Watts, NVIDIA's driver and Plasma's shell exist only on the operator's machine.
The sandbox measures memory and processor time on llvmpipe, where the driver itself is most of the
native wallpaper's memory and most of each frame's processor time; say which machine every number
comes from.

**Acceptance.** The chosen defaults in every place that holds them, with a test that reads each
default from where it is set; every lane passes; a sweep's numbers, if sent, in the notes, row by
row.

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

Start from a clone of `main` (github.com/Atyzze/syncrain); without access to the repository, ask
for it first (a session attaches it with push access before it can push). Bring the
sandbox up (`docs/agent/ENVIRONMENT.md`); `tools/prepare_environment.sh --verify` lists what is
missing, KWin 6 and the native wallpaper's build tools included. Then run the full lane once on the
untouched tree.

## How to make a build

1. Make the change. Comments say why, not when; tests assert behaviour; a guard that fires is
   usually right. A change to what a frame computes is made in both Linux hosts (`syncrain/` and
   `syncrain/native/`) and in the page, or the lanes that compare them fail.
2. If a stream file changed (a shader, `themes.json`, the atlas, a logo, `syncrain/engine.py`),
   decide whether the picture is meant to change. If it is: `python3 tools/stream_freeze.py --write`,
   say in the notes that machines on build 9 and build 10 no longer match, and make the README's
   pictures again (`docs/OPERATIONS.md`, "Recipes"). If not, undo it.
3. Write the notes for build 10 under `docs/build_notes/`, named for its number like the others:
   a title line `# Build 10: <what it does>`, a `**Type: ...**` line (it says "consolidation"
   exactly when the number ends in 0), the changes with the files and tests that hold them, what
   the operator does, and a `## Verification` section whose result line is the bare token
   GATE_RESULT; the release writes the gate's summary in its place.
4. Update `docs/ROADMAP.md` ("Where things stand", the questions, the decisions, the planned builds),
   rewrite `docs/agent/HANDOFF.md` and `docs/WHERE_WE_ARE.md` for build 10, and fold anything new
   into `docs/LESSONS.md` and `docs/HISTORY.md`.
5. **Rewrite this file for build 11**, keeping the first line exactly `# The next build is 11`.
6. Run the release detached (the gate takes about ten minutes on two cores; the browser lane is the
   slowest, the kwin lane next):

```
setsid nohup python3 tools/package_release.py --output <dir> > ../release.log 2>&1 < /dev/null &
```

7. The release refuses on any failing test and puts `BUILD_NUMBER` back. Read the failure, fix the
   cause rather than the test, and run it again. A killed release is undone by the next run from
   its journal; never edit `BUILD_NUMBER` by hand.
8. **Have the change reviewed by an agent that did not write it** when it changes what runs on the
   operator's desktop (a consolidation does not, but its documents can be checked the same way): point it at the tree and at the previous build's, ask for concrete faults
   with a failure scenario each, and turn each real one into a test that fails without its fix
   (builds 6 and 7 are what the reviews of builds 5 and 6 found). Read-only; the release does not
   wait for it, but nothing is delivered before it reports: a fault the operator would meet in
   everyday use makes the next build first (build 6 was not delivered for one), anything rarer goes
   into the delivery message and the next build.
9. Deliver the archive it wrote, `SYNCRAIN10.tar.zst`, and nothing else. Republish the live page
   from `web/artifact.html` (it carries the build number) and say what the operator does.
10. Commit the tree the release left to `main` as one commit, `syncrain build 10`, and push it. A
    build that changes what runs on their desktop as much as build 8 did goes to `main` only once
    the operator has tried it (they asked for that with build 8). With `<dir>` and the log outside
    the tree it is the archive's, byte for byte; `git status` shows only the build's own changes. The commit's name marks the build, since a
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
