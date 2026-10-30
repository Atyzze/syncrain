# Roadmap

Open questions, planned builds, the cadence and the constraints. What shipped: `docs/HISTORY.md`.

## Questions for the operator

None open.

## Decisions answered

* **2026-10-30**: a symbol changes only while the falling head is on it; once locked in, it
  fades as it is (no re-roll behind the head). Build 49, a stream change.
* **2026-10-20**: the video's loop crossfade blurs its first seconds and goes; the lock screen's
  rest stays but off by default, as a setting on the page; config.json is the default settings
  file, in every build, what `install.sh` reads (generated when missing) and where the defaults are
  kept; their file of that day is it (`pause_under` never). Build 47.
* **2026-10-16**: the roadmap's open items next, the most useful first; no installer image of the
  NixOS flavour for now. Builds 42 and on.
* **2026-10-15, their settings file**: 30 frames a second, and pausing behind maximized windows as
  well as full-screen ones (`"fps": 30`, `"pause_under": "maximized"`): the two questions asked on
  2026-10-07, answered by the default they chose. Build 35.
* **2026-10-15, after build 33's review**: "fix all the found issues", split over several builds,
  the most critical first; and their new settings file as the default. Builds 34 and on.
* **2026-10-15, after build 32**: the NixOS image as a flake template ("1-click apply": `nix flake init -t`,
  the machine's hardware, `nixos-rebuild switch`), not an installer ISO for now. Build 33.

* **2026-10-15 13:37**: the name: "syncrain backdrop", "since ye its more than jsut a wallapepr, its
  also a lockscreen, a screensaver". NixOS is "the 5th paradigm of course, the default/base"; they
  run CachyOS now and will move to NixOS, where syncrain should come along as it is. Build 30
  (the README) and 31 (the installer); the NixOS image next.
* **2026-10-15 13:30**: the installer for "the top 4": Arch, Debian, Fedora and openSUSE, and for
  the rest the invitation to "copy/hand this repo to your ai-agent and let it build/adapt the script
  for your specific environment"; no boot splash as a design choice: boot stays "pure text based"
  so the text says the OS is not fully up, and "the moment our rain is up we know w'ere in". They
  are making a NixOS flavour "anyone can 1 click image apply to their box". Builds 30 to 32.
* **2026-10-15 13:18**: the open lists' white background (light text on white), and "hidden
  sentences as well, not just words". Build 29.
* **2026-10-15 12:52**: "the functionality where the user can generate a .gif or .mp4 as
  recorded/set by their index.html preferences", "a loop, a static one ... just displayed as a
  video", keeping "the native real dynamic channel"; and GitHub explaining the main functionality and
  how to install. Build 29.
* **2026-10-15 12:49**: "this 'nixos colours' option doesnt seem to do anything meaningful, get rid
  of it"; their new settings file as the default; the README "well instructed". Build 28.
* Earlier answers, dated: `docs/HISTORY.md`, "The operator's words".

## Planned builds

The review of build 33 is done (all 84 items, builds 34 to 41: `docs/HISTORY.md`). Next, the open
items below that can be done here, the most useful first, one area a build:

1. **42** (done): the lock screen: the rain rests when nobody is there, the keyboard layout, Plasma's
   unseen lock wallpaper.
2. **43** (done): the login screen: KDE's wallet after greetd's text login (L8), Fedora's SELinux labels.
3. **44** (done): the stream id covers what decides the picture (L20), and `--scale` below 0.4 (L11): a
   stream change, on purpose.
4. **45** (done): an SVG as the desktop's logo; `scale`, `layer`, `background` and `mask` in the settings
   file; a SeekHead in the page's WebM.
5. **46** (done): the lock screen's frame (the same as the desktop's to the pixel: the 2% was two
   Mesa versions); the GTK host at a fractional scale draws the screen's own pixels; the page keeps
   a logo given as a picture file's path.

What only the operator's machine can show (booting the flavours, watts, Safari) stays below.

## Open items

What the documents and the review of build 17 leave to a build that changes code.

| Item | Where the fix goes |
| --- | --- |
| The login and lock screens on NixOS (build 32): evaluated, built, the login screen run in a headless KWin; never booted, and no VM here (no KVM) | someone booting it, or the image's VM test |
| Debian, Fedora and openSUSE: installed in roots, never booted; on Fedora, SELinux may still refuse greetd's domain the login screen (its files are labeled at install, `--diagnose` names the refusals, the text login asks meanwhile) | someone booting one, and the refusals `--diagnose` shows |
| Build 49's lock tick is a float decision: two GPUs can lock a different symbol in a cell when the head leaves within a few ULP of a tick's edge (about one cell in 10 to 30 minutes, held for its fade) | an integer lock (`pickGlyph(H(cu, ru, k, 21u))`), if the cost (every cell changes once as the head leaves, not 1 in 8) is worth it |
| Build 49: a slow head overtaken in its row, or a drop starting mid-row, can sit up to about 1/7 s on a still symbol; the symbol is picked for dark cells too | `state.frag`: a live head takes the cell; pick once after the loop, only for a lit cell |
| Ubuntu 24.04 and openSUSE Leap 16.0: no gtk4-layer-shell (the native wallpaper draws), Qt below 6.5 (no lock screen) | nothing to do until they update |
| A video's watts against the live rain's: not measured (no graphics card in the sandbox) | measure on their machine before claiming it uses less |
| NVIDIA's 615 driver keeps about 16 bytes per sync object until `eglTerminate` (build 48 makes OpenGL anew at 32 MiB of growth); unseen on KWin and NVIDIA here | the operator's record after a day, and a driver release that fixes it (then the renewals stop coming by themselves) |
| The page's Video needs WebCodecs with a VP9 or VP8 encoder (Chrome, Edge, Firefox); Safari may say it cannot | `syncrain --video` instead |

## Build cadence

Consolidation builds: every build number ending in 0, and no other build. Fixed: the operator's
rule, adopted at build 3. A consolidation changes no behaviour: it folds older notes into the
history, makes every document true and short again, and writes down what it finds as open items.

Next consolidation: 50

`tests/contract/test_the_working_documents_are_current.py` reads the two lines above.

## Standing constraints

* **Release**: only `tools/package_release.py` makes an archive and writes `BUILD_NUMBER`; notes in
  the same pass, ending in GATE_RESULT; the gate runs every lane; generated pages are regenerated
  and compared.
* **Picture**: the stream changes only on purpose; the hosts draw the same frame; nothing
  flashes (the fastest colour cycle is 90 s).
* **OpenGL**: never ask GTK for a version; take what it hands out and check it.
* **The machine**: the login and lock screens stay optional (only `--login-screen` and
  `--lock-screen` touch them); boot stays plain text: never the bootloader, the initramfs or a
  boot splash.
* **Writing**: short and plain; no long dashes; "the operator" or "they"; comments say why, not
  when; one home per fact.

## Not scheduled

* An installer image (ISO) of the NixOS flavour: not for now (2026-10-16); the template stays.
* A public randomness beacon (drand) in the seed: truly random, still in sync.
* Two screens in the Sway lane (the KWin lane has two).
* Pausing on wlroots compositors that keep asking a hidden wallpaper for frames, if one turns up.
