# Handoff: the state of syncrain at build 8

This page is what is true now, written for a context that has just opened this tree and knows
nothing else. **Build 8** (2026-10-09) answers the operator's question about memory and languages:
on a Wayland session the wallpaper is the native wallpaper, a C program (`syncrain/native/`) that
`syncrain` replaces itself with once Python has prepared the scene (`syncrain/native.py`), drawing
the GTK host's frames to the pixel with neither Python nor GTK in memory (in the sandbox 136 MiB
for two screens, against build 7's 308); the GTK host (`syncrain/app.py`) still draws on X11, in
windows, for screenshots and recordings, and takes over wherever the native wallpaper cannot draw,
and is lighter too (no PyOpenGL, no numpy, no dmabuf round trip, nothing kept after a screen
change). It was delivered in the chat and is **not yet on GitHub**: the operator asked to try it
first (`docs/ROADMAP.md`, "Questions for the operator").

Before it: **build 5** (2026-10-07) followed build 4's power sweep on the operator's RTX 5090,
which showed the watts following the frames (about 0.17 J a frame per screen) and a covered
wallpaper drawing at full rate under KWin: on KDE Plasma a screen under a maximized or full-screen
window is not drawn (KWin is asked through a script it runs, `syncrain/hidden.py`), and every frame
lands on a whole refresh and is drawn for the refresh it is shown on (`syncrain/pacing.py`); a
headless KWin 6.7.5 runs in the release's lanes (`tests/kwin/`). **Builds 6 and 7** (the same day)
fix what reviews of builds 5 and 6 found: the lead before each frame follows GTK's reports (on time
at 141 Hz); the KWin script survives a reused script number, a crashed syncrain and drags, and
answers during a drag, not after it. Build 6 was not delivered (its review found the last fault);
the operator ran build 7 from 2026-10-08. The picture has not changed since build 3. Build 9 waits
on the operator's trial of build 8 and their answers (`docs/agent/NEXT_BUILD.md`).

**Read, in this order:** this page; `docs/agent/NEXT_BUILD.md`; `docs/agent/WORKING_WITH_THE_OPERATOR.md`;
`docs/agent/ENVIRONMENT.md` (bring the sandbox up before deciding a lane cannot run); the notes in
`docs/build_notes/`; `docs/WHERE_WE_ARE.md` (the operator's page); `docs/ROADMAP.md`; then
`docs/ARCHITECTURE.md`, `docs/OPERATIONS.md`, `docs/LESSONS.md` and `docs/HISTORY.md` as needed.

## Start here, in a fresh context

1. Clone `main` from github.com/Atyzze/syncrain (without access to it, ask the operator for it
   before making a build: the archive lacks the commits after it). Until the operator approves
   build 8, `main` holds build 7: build 8's tree is its archive, `SYNCRAIN8.tar.zst`, which the
   operator has; commit it to `main` as `syncrain build 8` once they say so, before anything else
   (`docs/agent/NEXT_BUILD.md`). Bring the environment up
   (`tools/prepare_environment.sh --verify` says what is missing; `docs/agent/ENVIRONMENT.md` says
   how to get it, KWin 6 included).
2. Run `python3 tools/test_suite.py --lane all` on the untouched tree. Between releases three
   checks fail by one, correctly (`docs/agent/NEXT_BUILD.md`, "How to make a build").
3. Read what the operator sent last, before anything else, and answer it in one plain sentence first.

**Think from the code, not from this page.** Where a document and the code disagree, the code is
right and the document is fixed in the same build.

## What is true now

* **The operator's machine** (`docs/agent/TARGET_ENVIRONMENT.md`): CachyOS, KDE Plasma 6 on
  Wayland, two screens, an NVIDIA RTX 5090. Build 7 runs there (btop: 287 MiB at boot, 420 after a
  night, which the operator judged the garbage collector's ebb and flow, not a leak); their sweep
  of build 4 (12:19) is in `docs/build_notes/BUILD5_NOTES.md`, section 1. Build 8 has not run there
  as far as this tree knows.
* **The native wallpaper** (`docs/ARCHITECTURE.md`, "Three hosts over the same shaders"): on
  Wayland, when built (`install.sh` builds it with gcc; the Nix package too), `syncrain` execs it
  with the scene in a memfd. It ports what a frame computes on the processor from Python operation
  for operation (`tests/native/` compares the two bit for bit) and makes the same OpenGL calls as
  `renderer.py`. It has run on Mesa only (llvmpipe, in the sandbox): NVIDIA's EGL meets it first on
  the operator's machine. Anything that fails before the first frame hands over to the GTK host
  (the journal says "the GTK host takes over"); after it, frames that cannot be shown for 5 s, or
  a compositor that goes away, stop it with status 1 and the service starts it again (build 8's
  review found both; section 7 of its notes). `syncrain --diagnose` has a "native wallpaper"
  section with what it finds.
* **Memory, in the sandbox** (two 640x360 screens on a headless Sway, llvmpipe): build 7 308 MiB,
  build 8's GTK host 263, the native wallpaper 136, of which llvmpipe about 130 and
  syncrain's own code and data a few MiB (`docs/build_notes/BUILD8_NOTES.md`). On a graphics card
  the driver's share is different and unmeasured; the sweep's "MiB" column will say.
* **Power on their card**: +10.6 W at 30 fps through GTK's OpenGL renderer (the default since build
  4), +25.5 W through Vulkan; +6.9 W at 20 fps, +5.0 W at 15; resolution and snow barely matter.
* **Covered screens**: KWin keeps asking a covered wallpaper for frames (the kwin lane's first test
  shows it); build 5 asks KWin instead and stops drawing a covered screen. Sway stops asking by
  itself. Not checked against Plasma's shell (panel, effects) or a real card.
* **Frame timing**: on the kwin lane's KWin at 60 Hz, build 4's timer was "steady" for 17 to 44% of
  frames, builds 5 to 7 for 95 to 100%; at 141 Hz, build 4 about 55%, build 5 74 to 84%, builds 6 and
  7 86 to 100% (`SYNCRAIN_DEBUG_FPS` reports it, with the lead). On 2026-10-09 the sandbox was slower
  (render spikes to three times the usual frame), and build 8's native wallpaper came out ahead of
  the GTK host and of build 7 on the same lane (build 8's notes); the lane judges the median of six
  reports since. Not checked on a real fast monitor.
* **KWin treats syncrain as an ordinary window** (its layer-shell namespace names no window type),
  so show desktop hides it. Not changed; it belongs to the KDE question in `docs/ROADMAP.md`.
* **The stream**: id `48e6bf9c`, unchanged since build 3 (`tests/fixtures/stream_freeze.json`).
* **The repository** (2026-10-08, at the operator's request): github.com/Atyzze/syncrain. `main`
  holds build 7 as delivered (the commit `syncrain build 7`), then commits that changed no
  behaviour: a README for visitors with two pictures (`docs/images/`), the repository in the
  install recipes and the package metadata, the generated pages marked as generated for GitHub
  (`web/.gitattributes`), and corrections the code showed. Build 8 was made from that `main`
  (627a9e2) and waits for the operator before it is committed there.

## What waits on the operator

* Try build 8 and say whether it goes to `main`; optionally `syncrain --power-sweep`, whose table
  now has the native wallpaper and the GTK host side by side with processor time and memory.
* Three answers (`docs/ROADMAP.md`, "Questions for the operator"): the default frame rate, pausing
  behind maximized windows or only full-screen ones, and the KDE icons.

## The system, in one page

`docs/ARCHITECTURE.md`. In a sentence: six GPU passes turn (UTC seconds since 2024, the fraction,
the channel's FNV-1a hash) into a frame through integer hashes; on Wayland a C program puts it on
every screen as a layer-shell surface, elsewhere a GTK app (in an X11 desktop window, or a
window), each drawing every frame for the refresh it is shown on and none for a screen KWin says is
covered; a web page does the same in WebGL2, and all three are checked against each other every
release.

## The operator's standing calls

Build numbers only, no versions; deliveries only as the release tool's archive; no long dashes;
"the operator" or "they"; consolidation at every build number ending in 0; nothing that flashes;
measured cost before gain. The full list: `docs/ROADMAP.md`, "Standing constraints".
