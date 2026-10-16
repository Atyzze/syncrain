# Roadmap

Open questions, planned builds, the cadence and the constraints. What shipped: `docs/HISTORY.md`.

## Questions for the operator

None open.

## Decisions answered

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

1. **42**: the lock screen: the rain rests when nobody is there, the keyboard layout, Plasma's
   unseen lock wallpaper.
2. **43**: the login screen: KDE's wallet after greetd's text login (L8), Fedora's SELinux labels.
3. **44**: the stream id covers what decides the picture (L20), and `--scale` below 0.4 (L11): a
   stream change, on purpose.
4. **45**: an SVG as the desktop's logo; `scale`, `layer`, `background` and `mask` in the settings
   file; a SeekHead in the page's WebM.
5. **46**: the lock screen's 2% darker frame; the GTK host at a fractional scale.

What only the operator's machine can show (booting the flavours, watts, Safari) stays below.

## Open items

What the documents and the review of build 17 leave to a build that changes code.

| Item | Where the fix goes |
| --- | --- |
| L8: KDE's wallet does not open after greetd's text login | not known yet; the wallet lines are `install.sh`'s, in greetd's PAM service |
| L11: `--scale` below about 0.4 changes the picture (the page as a wallpaper does the same, so the two agree) | the cell size in `syncrain/renderer.py` (`geometry`), `syncrain/native/timing.c` (`geometry_compute`), `index.html` |
| L20: the stream id does not cover `renderer.py`'s geometry, `native/timing.c` or `index.html` | `syncrain/build.py` (`STREAM_FILES`) |
| The GTK host at a fractional scale (1.25) draws at the next whole scale and the compositor scales it down (GTK 4.14's GtkGLArea framebuffer), so it is a little softer than the native wallpaper, Wayland's default, which draws at the screen's pixels | GTK's own, or the GTK host drawing its own surface; `tests/wayland/test_the_wallpaper_layer.py` compares it at whole scales only |
| An SVG as the logo: the page takes one, the desktop's `--logo` does not (Pillow draws no SVG) | `syncrain/logo.py`, with GTK's loader (librsvg) |
| The lock screen's frame is about 2% darker than the desktop's in the lockscreen lane (llvmpipe), in proportion to brightness; the cause is not found | `syncrain/lockscreen/rainitem.cpp`, `tests/lockscreen/test_the_lock_screen.py` |
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
