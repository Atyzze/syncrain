# The next build is 13

The first line is parsed: `# The next build is <N>`, exactly one above `BUILD_NUMBER`.

## Build 13: the operator's answers

* Read what the operator sent last, and answer it in one plain sentence first. If memory still
  grows with build 12, that comes first: their `syncrain --diagnose` shows the memory record and
  the environment the running wallpaper got.
* **The glow flare-up**: with the time they saw it, draw that moment (`--time`, their options, both
  screens' sizes) and look at the frames around it.
* **The three questions** in `docs/ROADMAP.md`. A default frame rate of 20 or 15 lives in four
  places: `--fps` in `syncrain/app.py`, `fps` in `nix/options.nix`, `base_args` in
  `syncrain/power.py` and the options table in `docs/OPERATIONS.md`. Pausing only under full-screen
  windows: `--pause-under` in `syncrain/app.py`, `pauseUnder` in `nix/options.nix` and
  `nix/args.nix`, `syncrain/power.py`, `docs/OPERATIONS.md`.
* **The Plasma wallpaper plugin**, if chosen: a Plasma 6 wallpaper package drawing the web page or
  the shaders behind the icons, installed by `install.sh`; it keeps both power savings (no frames
  for covered screens, frames on the refresh).

**Known blockers**: watts, NVIDIA's driver and Plasma's shell exist only on the operator's machine.

**Acceptance**: the chosen defaults everywhere they live, each read by a test; every lane passes.

## How to make a build

1. Make the change. Comments say why, not when; tests assert behaviour.
2. A stream file changes (shader, theme, atlas, logo, `syncrain/engine.py`) only on purpose:
   `python3 tools/stream_freeze.py --write`, and the notes say machines stop matching.
3. Notes in `docs/build_notes/BUILD<N>_NOTES.md`: `# Build <N>: <what>`, a `**Type: ...**` line
   (consolidation exactly at numbers ending in 0), the changes, what the operator does, and
   `## Verification` with the bare token GATE_RESULT.
4. Update `docs/ROADMAP.md`, `docs/agent/HANDOFF.md`, `docs/WHERE_WE_ARE.md`, and this page for
   the number after. Keep them short.
5. Release, detached (about ten minutes):
   `setsid nohup python3 tools/package_release.py --output <dir> > ../release.log 2>&1 < /dev/null &`
6. A failing gate puts `BUILD_NUMBER` back: fix the cause, run it again. Never edit the number.
7. Have an agent that did not write it review any change that runs on the operator's desktop;
   an everyday fault it finds goes first, anything rarer into the message and the next build.
8. Deliver only the archive; republish the live page from `web/artifact.html`.
9. Commit the tree as `syncrain build <N>` on `main` and push. A change as big as build 8 waits for
   the operator's trial first.

Three checks fail by one between releases (this page, `docs/WHERE_WE_ARE.md` and the handoff name
the build being made); they pass inside the gate.

## What not to do

* Ask GTK for an OpenGL version.
* Claim watts from the sandbox (no graphics card there).
* Change the stream in a build about something else.
* Hand over a patch or a hand-made tar.
* Use long dashes.
