# The next build is 11

The first line is parsed: `# The next build is <N>`, exactly one above `BUILD_NUMBER`.

## Build 11: stop the memory creep on NVIDIA

* **Change**: set `__NV_DISABLE_EXPLICIT_SYNC=1` and `__GL_YIELD=USLEEP` in syncrain's own
  environment before GTK or the native wallpaper start (`syncrain/app.py`, beside
  `use_gl_renderer`). A value the user set wins. The native wallpaper inherits both through
  `os.execve`.
* **Why**: NVIDIA's Wayland driver keeps a fixed allocation for every frame presented while explicit
  sync is on. On the operator's desktop: +0.9 MiB a minute (two screens at 30 fps), flat while the
  screens are off. On Mesa: flat over 20,000 frames. NVIDIA's forum has the same leak with
  `eglgears_wayland` alone (May 2026), and `__NV_DISABLE_EXPLICIT_SYNC=1` stops it there.
  `__GL_YIELD=USLEEP` makes the driver sleep, not spin, while it waits in the implicit-sync path.
* **Also, from build 9's review**: the sweep should save its JSON before printing (a closed terminal
  loses both now), ignore a second signal during its cleanup, keep an inherited `SIG_IGN` (nohup),
  and advise Alt+Tab to its terminal and Ctrl+C (Alt+F4 leaves the phase measuring an uncovered
  wallpaper); the native wallpaper should not settle its memory before a new screen is configured.

**Known blockers**: the leak exists only on NVIDIA. The sandbox can check that both variables are
set before GTK starts and reach the native program; the operator's btop is the real test.

**Acceptance**: a test for each change, failing without it; every lane passes; memory flat on the
operator's desktop over an hour.

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
