# syncrain roadmap

What is open, in order; how builds are paced; and the constraints every build keeps. What shipped
is in `docs/build_notes/` and `docs/HISTORY.md`.

## Where things stand

Build 9 (2026-10-09) makes the power sweep warn that every screen goes black in its last two phases,
as the operator asked, and lets the native wallpaper hand back what a cold shader cache left in its
heap. Build 8 (the same day) answered the operator's memory and language question: on Wayland the
wallpaper is a C program with neither Python nor GTK in memory (`syncrain/native/`), drawing the
GTK host's frames to the pixel; on the operator's RTX 5090 it runs at 123 MiB and 0.9% of a core at
30 fps, against 205 MiB and 4.7% for the Python and GTK host, which still draws on X11, in windows
and wherever the native wallpaper cannot. Build 7 (2026-10-07) fixed what reviews of builds 5 and 6
found (frames on time on fast screens, the KWin script's starts and drags); build 5 stopped drawing
covered screens on KDE Plasma and timed every frame to the refresh. The picture is build 3's. Build
8 runs on the operator's desktop; builds 8 and 9 are on GitHub.

## What is open

Two lists: questions for the operator and builds planned in order. A question is written here the
turn it is asked, in plain words with its options and a recommendation, and leaves when it is
answered, with the answer under "Decisions answered".

### Questions for the operator

* **The default frame rate** (asked 2026-10-07 12:25 with build 4's numbers; these are their sweep of
  build 8, 2026-10-09, two screens): (1) 30 fps, +11.9 W, as now; (2) 20 fps, +7.3 W; (3) 15 fps,
  +3.5 W, each with the frames 97 to 100% even and steady. The fastest rain streams move about 21
  rows a second, so below about 21 fps some skip a row now and then. Recommended: judge by eye,
  with `syncrain --fps 20` for a day; keep 30 if the snow and the trails look worse.
* **Pause behind maximized windows too, or only full-screen ones?** (asked 12:25.) Build 5 pauses
  behind both (`--pause-under maximized`, the default); the catch is a window that is see-through by
  itself, behind which the rain would stand still. Recommended: both.
* **The desktop icons on KDE Plasma** (asked with build 3; still open). syncrain takes Plasma's bottom
  layer, above Plasma's own desktop surface, so it covers the desktop icons and widgets; clicks pass
  through. To KWin it is also an ordinary window (its layer-shell namespace names no type), so
  "show desktop" hides it. Options: (a) keep it; (b) a Plasma wallpaper plugin, so syncrain is
  chosen in Plasma's wallpaper settings and draws behind the icons, as part of Plasma's desktop
  (the web page in a QML WebEngine view, or the shaders in a QML shader effect); a build of its own,
  and Plasma cannot run in the build sandbox, so the operator's machine is its first test; (c) the
  web page in an existing Plasma web-wallpaper plugin, today, with no build. Recommended: (b), with
  (c) meanwhile.

### Decisions answered

* **2026-10-09 11:36, after build 8**: "success, definitely less cpu and memory used, and 122MB feels
  way more acceptable ... update the github please, also, the power-sweep should have a warning
  message in it that in the last two tests, all your screens might go black for a while". Build 8
  went to `main`; build 9 carries the warning.
* **2026-10-09 07:05, before build 8**: "drop the memory leak assumption and instead optimize around
  minimal memory footprint without sacrificing actual fps/watt ratio, because even more important is
  power usage down", and whether "a full rust, c, asm, cpp or any other languages has anything to
  offer here". Carried out by build 8: the native wallpaper in C (memory and processor time; the
  card's watts follow the frames in any language), the GTK host lightened, the sweep measuring
  processor time and memory beside the watts.
* **2026-10-09 00:02, during build 8**: "do not push to github when done, instead, just deliver the
  new build here in chat so I can try it out myself before we commit it". Build 8 is delivered in
  the chat and waits (above).
* **2026-10-08, after build 7**: "can you create a new github depository for this and make sure its
  properly documented?" The operator created github.com/Atyzze/syncrain; `main` holds build 7 as
  delivered, then commits that changed no behaviour (a README for visitors with a picture of each
  theme, the repository in the install recipes, corrections). Each build from 8 on goes to `main`
  as one commit (`docs/agent/NEXT_BUILD.md`, "How to make a build").
* **2026-10-07 12:19, before build 5**: build 4's sweep on their card, "it definitely went down
  linearly together with fps". Build 5 stops drawing what nobody sees and times every frame to the
  refresh; the frame rate itself stays theirs to choose (above).
* **2026-10-07 03:02, before build 4**: power first. "the gif actually takes just as much extra
  power but from the gpu instead, a little more even 20W ... perhaps we can reduce it even further?
  so that we can justify it as an actual wallpaper not being too power hungry ... could we reduce
  wattage needed without gimping the smoothness/fps too much?" Carried out by build 4 (measure on
  their card, cut what keeps the picture); build 5 follows the sweep's numbers.
* **2026-10-07, before build 3**: "can you adopt the good architecture/code-base management
  practices from this codebase, such as a clear build number (instead of these versionings ....
  stop, no 'versions', only build numbers)", with GSD592 attached. Carried out by build 3.
* **2026-10-06, before build 2**: the NixOS logo turns slowly and cycles through the rainbow, so the
  wallpaper also works against burn-in; an installer for Arch-based systems, so it can be tried
  without a NixOS image. Carried out by build 2.
* **2026-10-06, before build 1**: a real-time, never-repeating wallpaper instead of a looping GIF,
  synchronised by the UTC clock so others can join the same stream; Linux first, NixOS-ready; a
  NixOS theme (snow, blue, grey and white, the NixOS logo instead of the CachyOS C). Build 1.

### Planned builds, in order

1. **Build 10: consolidation** (fixed; `docs/agent/NEXT_BUILD.md`): build 8 and 9's notes folded
   into the history, every standing document checked against the code.
2. **Build 11: from the operator's answers**: the default frame rate they choose; the pause as they
   want it; anything a sweep shows.
3. **The Plasma wallpaper plugin**, if the operator chooses it.
4. **NixOS image**: syncrain as the default wallpaper of a NixOS image: a module option that turns
   it on for every graphical user, and a flake template for an image that has it.

## Build cadence

Two kinds of build alternate.

* **Feature and fix builds** change what syncrain does or shows, from the operator's messages and
  this roadmap. Most builds are these.
* **Consolidation builds** change no behaviour. They fold the older notes into `docs/HISTORY.md`,
  rewrite every standing document to say what is true now and delete what is not, check the
  documents against each other and against the code, prune this roadmap, and leave `docs/agent/`
  so that a new context knows exactly what the next build is. A feature or fix found on the way is
  written down as an open item, not made.

Consolidation builds: every build number ending in 0, and no other build. Fixed: the operator's rule for GSD (set at its build 527), adopted here at build 3.

Next consolidation: 10

`tests/contract/test_the_working_documents_are_current.py` reads the two lines above and checks
that a build's notes say "Type: consolidation" exactly when its number ends in 0.

## Standing constraints

Not to be argued again. A build that breaks one says why in its notes.

**Code and release**

* **Every archive that leaves this machine bumps the build number**, and only
  `tools/package_release.py` makes one. Never a patch, never a hand-made tar, never `BUILD_NUMBER`
  edited by hand. No version strings anywhere.
* **A build's notes are written in the same pass as the build**, ending in "## Verification" with
  the token GATE_RESULT, which the release replaces with the gate's own summary.
* **The release runs every lane, with every environment required.** A lane that skips on the
  release machine never ran; if one cannot run, fix the environment (`docs/agent/ENVIRONMENT.md`).
* **The stream changes only on purpose**: `python3 tools/stream_freeze.py --write`, and the notes
  say the picture changed and that machines on the previous build stop matching.
* **The page, the GTK host and the native wallpaper draw the same frame**; the browser lane holds
  the page to the GTK host, the wayland lane the native wallpaper to it, to the pixel.
* **Never ask GTK for an OpenGL version**; take what it hands out and check it.
* **Nothing flashes.** Every motion is slow (the fastest colour cycle is a minute and a half), for
  photosensitivity; a "pixel cleaner" that strobes is out.
* **Generated files are regenerated by the release and checked by the gate** (`web/index.html`,
  `web/artifact.html`).

**Writing**

* No long dashes, anywhere; a hyphen, a comma, a semicolon or a full stop.
* The operator is "the operator" or "they".
* Comments say why, not when; the history is in the notes.
* One home per fact; a document points at the file that holds it.

## Nice to have, not scheduled

* A public randomness beacon (drand) mixed into the seed: truly random, still in sync.
* Two virtual screens in the Sway lane as well (the kwin lane has two).
* Pausing behind windows on wlroots compositors that keep asking a hidden wallpaper for frames, if
  one turns up (Sway does not; it stops asking by itself).
