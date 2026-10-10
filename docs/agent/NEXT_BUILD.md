# The next build is 15

The first line is parsed: `# The next build is <N>`, exactly one above `BUILD_NUMBER`.

## Build 15: their trial, then the login screen

* Read what the operator sent last, and answer it in one plain sentence first. Builds 13 and 14 go
  to GitHub (committed, not pushed) only once they say the Plasma wallpaper works; what they report
  about it comes first.
* **The login screen**: an SDDM theme that keeps Breeze's login form (`/usr/share/sddm/themes/breeze`)
  with the `SyncRain` item behind it (the module is in Qt's QML folder already; SDDM runs as its
  own user, so its scene goes somewhere it can read). Test it with `sddm-greeter-qt6 --test-mode`
  in the Arch root.
* **The glow flare-up**, with the time they saw it: draw that moment and look.
* **The two questions** in `docs/ROADMAP.md` (default frame rate, what pauses).

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
