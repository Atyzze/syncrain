# Roadmap

Open questions, planned builds, the cadence and the constraints. What shipped: `docs/HISTORY.md`.

## Questions for the operator

* **Default frame rate** (asked 2026-10-07; numbers from their sweep of build 8): 30 fps +11.9 W
  (now), 20 fps +7.3 W, 15 fps +3.5 W. Below about 21 fps the fastest streams skip a row now and
  then. Recommended: `syncrain --fps 20` for a day, then judge by eye.
* **Pause behind maximized windows too, or only full-screen ones?** (2026-10-07) Both now; behind a
  see-through window the rain then stands still. Recommended: both.

## Decisions answered

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

The review of build 33 (84 items, numbered, in the operator's review document), fixed most
critical first, one area a build:

1. **35** (done): the operator's new default, `composite.frag` to its spec (69), and the values
   that passed and then broke the picture (65, 66, 76, on the desktop and the page alike): the one
   stream change.
2. **36** (done): the login screen (4 to 7, 23, 31 to 38).
3. **37** (done): the installer (8 to 11, 39 to 46).
4. **38**: Nix and the test harness (2, 12, 16 to 18, 20 to 22, 47).
5. **39**: the native host and the Python host (14, 15, 29, 48 to 55, 57 to 64, 67, 68).
6. **40**: the consolidation.
7. **41**: the page and the release tool (13, 19, 24 to 26, 70 to 75, 77 to 84).
8. **An installer ISO** of the flavour, if wanted (the operator chose the template first,
   2026-10-15): several GB to build, and tried only where a VM runs.

## Open items

What the documents and the review of build 17 leave to a build that changes code.

| Item | Where the fix goes |
| --- | --- |
| L8: KDE's wallet does not open after greetd's text login | not known yet; the wallet lines are `install.sh`'s, in greetd's PAM service |
| L11: `--scale` below about 0.4 changes the picture (the page as a wallpaper does the same, so the two agree) | the cell size in `syncrain/renderer.py` (`geometry`), `syncrain/native/timing.c` (`geometry_compute`), `index.html` |
| L20: the stream id does not cover `renderer.py`'s geometry, `native/timing.c` or `index.html` | `syncrain/build.py` (`STREAM_FILES`) |
| L21: no `flake.lock`, so a Nix build takes whatever nixpkgs is current | `flake.lock` |
| An SVG as the logo: the page takes one, the desktop's `--logo` does not (Pillow draws no SVG) | `syncrain/logo.py`, with GTK's loader (librsvg) |
| The lock screen draws at 30 fps on every screen while locked and lit (NVIDIA's explicit-sync growth is not turned off in KWin's greeter) | measure there; a lower rate after a while without input, `syncrain/lockscreen/rainitem.cpp` |
| The lock screen shows no keyboard layout (Plasma's does) | `syncrain/lockscreen/package/` |
| The lock screen's frame is about 2% darker than the desktop's in the lockscreen lane (llvmpipe), in proportion to brightness; the cause is not found | `syncrain/lockscreen/rainitem.cpp`, `tests/lockscreen/test_the_lock_screen.py` |
| Plasma still loads its lock-screen wallpaper under syncrain's, unseen | `kscreenlockerrc`, only with `--lock-screen` |
| The login and lock screens on NixOS (build 32): evaluated, built, the login screen run in a headless KWin; never booted, and no VM here (no KVM) | someone booting it, or the image's VM test |
| Debian, Fedora and openSUSE: installed in roots, never booted; Fedora's SELinux may stop greetd running the login screen from `/usr/local/lib` | someone booting one; `restorecon` or a policy note in `install.sh` |
| Ubuntu 24.04 and openSUSE Leap 16.0: no gtk4-layer-shell (the native wallpaper draws), Qt below 6.5 (no lock screen) | nothing to do until they update |
| A video's watts against the live rain's: not measured (no graphics card in the sandbox) | measure on their machine before claiming it uses less |
| The page's Video needs WebCodecs with a VP9 or VP8 encoder (Chrome, Edge, Firefox); Safari may say it cannot | `syncrain --video` instead |
| The page's WebM has no SeekHead: playing and looping are unaffected, seeking finds the cues later | `index.html` (`webm`) |
| The settings file holds no `background`, `mask`, `scale` or `layer` (the page cannot preview a picture file) | `syncrain/app.py` (`CONFIG_KEYS`) and the page, if wanted |

## Build cadence

Consolidation builds: every build number ending in 0, and no other build. Fixed: the operator's
rule, adopted at build 3. A consolidation changes no behaviour: it folds older notes into the
history, makes every document true and short again, and writes down what it finds as open items.

Next consolidation: 40

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

* A public randomness beacon (drand) in the seed: truly random, still in sync.
* Two screens in the Sway lane (the KWin lane has two).
* Pausing on wlroots compositors that keep asking a hidden wallpaper for frames, if one turns up.
