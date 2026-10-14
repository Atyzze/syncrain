# The next build is 20

The first line is parsed: `# The next build is <N>`, exactly one above `BUILD_NUMBER`.

## Build 20: consolidation

* Read what the operator sent last, and answer it in one plain sentence first. A fault they find
  in 19 is written down for build 21, which comes right after; 20 changes no behaviour.
* Fold the build notes up to 18 into `docs/HISTORY.md` (19's and 20's stay in `docs/build_notes/`),
  make every document true and short again, and write down what it finds as open items.
* Then build 21: the previewer page (`docs/ROADMAP.md`, planned build 1).

**Known blockers**: watts, NVIDIA's driver and Plasma's shell exist only on the operator's machine;
a real greetd and PAM only there too (the lanes speak to a stand-in).

**Acceptance**: no change but in documents and comments; `**Type: consolidation**`; every lane passes.

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
* Touch how the machine logs in without `--login-screen`.
