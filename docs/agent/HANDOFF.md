# Handoff: the state of syncrain at build 7

This page is what is true now, written for a context that has just opened this tree and knows
nothing else. **Build 5** (2026-10-07) followed build 4's power sweep on the operator's RTX 5090,
which showed the watts following the frames (about 0.17 J a frame per screen) and a covered
wallpaper drawing at full rate under KWin: on KDE Plasma a screen under a maximized or full-screen
window is not drawn (KWin is asked through a script it runs, `syncrain/hidden.py`), and every frame
lands on a whole refresh and is drawn for the refresh it is shown on (`syncrain/pacing.py`); a
headless KWin 6.7.5 runs in the release's lanes (`tests/kwin/`). **Builds 6 and 7** (the same day)
fix what reviews of builds 5 and 6 found: the lead before each frame follows GTK's reports (on time
at 141 Hz); the KWin script survives a reused script number, a crashed syncrain and drags, and
answers during a drag, not after it. Build 6 was not delivered (its review found the last fault);
the operator has build 5, and build 7 replaces it. The picture did not change. Build 8 waits on the
operator's answers (`docs/agent/NEXT_BUILD.md`).

**Read, in this order:** this page; `docs/agent/NEXT_BUILD.md`; `docs/agent/WORKING_WITH_THE_OPERATOR.md`;
`docs/agent/ENVIRONMENT.md` (bring the sandbox up before deciding a lane cannot run); the notes in
`docs/build_notes/`; `docs/WHERE_WE_ARE.md` (the operator's page); `docs/ROADMAP.md`; then
`docs/ARCHITECTURE.md`, `docs/OPERATIONS.md`, `docs/LESSONS.md` and `docs/HISTORY.md` as needed.

## Start here, in a fresh context

1. Clone `main` from github.com/Atyzze/syncrain (without access to it, ask the operator for it
   before making a build: the archive lacks the commits after it) and bring the environment up
   (`tools/prepare_environment.sh --verify` says what is missing; `docs/agent/ENVIRONMENT.md` says
   how to get it, KWin 6 included).
2. Run `python3 tools/test_suite.py --lane all` on the untouched tree. Between releases three
   checks fail by one, correctly (`docs/agent/NEXT_BUILD.md`, "How to make a build").
3. Read what the operator sent last, before anything else, and answer it in one plain sentence first.

**Think from the code, not from this page.** Where a document and the code disagree, the code is
right and the document is fixed in the same build.

## What is true now

* **The operator's machine** (`docs/agent/TARGET_ENVIRONMENT.md`): CachyOS, KDE Plasma 6 on
  Wayland, two screens, an NVIDIA RTX 5090. Build 4 runs there; their sweep of it (12:19) is in
  `docs/build_notes/BUILD5_NOTES.md`, section 1. Build 5 was delivered, then build 7; neither has run
  there yet as far as this tree knows.
* **Power on their card**: +10.6 W at 30 fps through GTK's OpenGL renderer (the default since build
  4), +25.5 W through Vulkan; +6.9 W at 20 fps, +5.0 W at 15; resolution and snow barely matter.
* **Covered screens**: KWin keeps asking a covered wallpaper for frames (the kwin lane's first test
  shows it); build 5 asks KWin instead and stops drawing a covered screen. Sway stops asking by
  itself. Not checked against Plasma's shell (panel, effects) or a real card.
* **Frame timing**: on the kwin lane's KWin at 60 Hz, build 4's timer was "steady" for 17 to 44% of
  frames, builds 5 to 7 for 95 to 100%; at 141 Hz, build 4 about 55%, build 5 74 to 84%, builds 6 and
  7 86 to 100% (`SYNCRAIN_DEBUG_FPS` reports it, with the lead). Not checked on a real fast monitor.
* **KWin treats syncrain as an ordinary window** (its layer-shell namespace names no window type),
  so show desktop hides it. Not changed; it belongs to the KDE question in `docs/ROADMAP.md`.
* **The stream**: id `48e6bf9c`, unchanged since build 3 (`tests/fixtures/stream_freeze.json`).
* **The repository** (2026-10-08, at the operator's request): github.com/Atyzze/syncrain. `main`
  holds build 7 as delivered (the commit `syncrain build 7`), then commits that changed no
  behaviour: a README for visitors with two pictures (`docs/images/`), the repository in the
  install recipes and the package metadata, the generated pages marked as generated for GitHub
  (`web/.gitattributes`), and corrections the code showed (the sweep's length, the page's
  parameters, `MOMENT`'s date, the release log's place). Make build 8 from a clone of `main`, or
  the archive drops those commits.

## What waits on the operator

* Install build 7 and look; optionally `syncrain --power-sweep` again, and build 4's JSON if at hand.
* Three answers (`docs/ROADMAP.md`, "Questions for the operator"): the default frame rate, pausing
  behind maximized windows or only full-screen ones, and the KDE icons.

## The system, in one page

`docs/ARCHITECTURE.md`. In a sentence: six GPU passes turn (UTC seconds since 2024, the fraction,
the channel's FNV-1a hash) into a frame through integer hashes; a GTK app puts it on every screen
as a layer-shell surface (or an X11 desktop window), drawing each frame for the refresh it is shown
on and none for a screen KWin says is covered; a web page does the same in WebGL2, and both are
checked against each other every release.

## The operator's standing calls

Build numbers only, no versions; deliveries only as the release tool's archive; no long dashes;
"the operator" or "they"; consolidation at every build number ending in 0; nothing that flashes;
measured cost before gain. The full list: `docs/ROADMAP.md`, "Standing constraints".
