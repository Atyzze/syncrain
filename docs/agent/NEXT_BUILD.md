# The next build is 30

The first line is parsed: `# The next build is <N>`, exactly one above `BUILD_NUMBER`.

## Build 30: the consolidation

* Read what the operator sent last, and answer it in one plain sentence first.
* No behaviour changes (every number ending in 0): fold builds 21 to 29's notes into
  `docs/HISTORY.md`, make every document true and short again, list what it finds as open items.
* The README says what syncrain is now, in the operator's word: **syncrain backdrop**, the rain for
  the whole session (desktop, login screen, lock screen, videos), NixOS the base; and the design
  choice that boot stays plain text: the text says the machine is not up yet, the rain that it is
  (2026-10-15 13:30 and 13:37, `docs/ROADMAP.md`).
* Then build 31: `install.sh` for Debian, Fedora and openSUSE beside Arch, and the README's
  invitation to hand the repository to an AI agent for anything else.
* No boot splash: never touch the bootloader, initramfs or Plymouth.

**Known blockers**: watts, NVIDIA's driver and Plasma's shell exist only on the operator's machine;
a real greetd and PAM only there too (the lanes speak to a stand-in). The page's Save inside the
claude.ai viewer needs the `downloads` capability on the artifact (publish with it).

**Acceptance**: what the operator asked works on the lanes that can show it; every lane passes.

## How to make a build

1. Make the change. Comments say why, not when; tests assert behaviour. To edit `index.html`,
   `python3 tools/build_web.py --strip` first (its data out of the way), then fill it again.
2. A stream file changes (shader, theme, atlas, logo, `syncrain/engine.py`, `syncrain/glyphs.py`)
   only on purpose: `python3 tools/stream_freeze.py --write`, and the notes say machines stop
   matching.
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
8. Deliver only the archive; republish the live page from `python3 tools/build_web.py --artifact <file>`
   (the page without its document), with the `downloads` capability.
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
