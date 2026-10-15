# Roadmap

Open questions, planned builds, the cadence and the constraints. What shipped: `docs/HISTORY.md`.

## Questions for the operator

* **Default frame rate** (asked 2026-10-07; numbers from their sweep of build 8): 30 fps +11.9 W
  (now), 20 fps +7.3 W, 15 fps +3.5 W. Below about 21 fps the fastest streams skip a row now and
  then. Recommended: `syncrain --fps 20` for a day, then judge by eye.
* **Pause behind maximized windows too, or only full-screen ones?** (2026-10-07) Both now; behind a
  see-through window the rain then stands still. Recommended: both.

## Decisions answered

* **2026-10-15 13:37**: the name: "syncrain backdrop", "since ye its more than jsut a wallapepr, its
  also a lockscreen, a screensaver". NixOS is "the 5th paradigm of course, the default/base"; they
  run CachyOS now and will move to NixOS, where syncrain should come along as it is. Build 30
  (the documents) and 31 (the installer).
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
  how to install. Build 29 (below); the README rewritten in 28.
* **2026-10-15 12:49**: "this 'nixos colours' option doesnt seem to do anything meaningful, get rid
  of it"; their new settings file as the default; the README "well instructed" and matching it;
  "any other issues". Build 28.
* **2026-10-15 10:45**: on the lock screen, the box hidden until "recent key input or mouse
  movement", gone again "after a minute of inactivity", and typing in any box updates all of them,
  "so it never matters which screen is visible". Build 27.
* **2026-10-15 10:16**: no boot splash: "I think I want to keep it out of boot then. Current boot is
  raw text, I disabled Plymouth since I wanted to be able to see everything". syncrain starts at the
  login screen; nothing touches the bootloader, the initramfs or Plymouth.
* **2026-10-14 22:44**: the lock screen too, "a login box in the midde of our own", and "booted up
  as soon as possible, even before LUKS pwd is asked". Builds 25 and 26 (the lock screen); the
  boot part dropped on 2026-10-15 (above).
* **2026-10-14 22:33**: "can we push this as new default template for syncrain on our github
  please", their settings file attached; the lock screen "still goes back to plasma thing" (Plasma's
  kscreenlocker; syncrain has not drawn it since build 15). Build 24.
* **2026-10-14 19:53**: their settings file as a preset and the default, "nixos logo remains
  selectable"; their logo cleaned up, "perhaps turn it into a svg"; "a color slider for the
  potential logo in the middle, as an overide color channel on a user chosen png". Build 23.

* **2026-10-14 18:25**: build 21 "working beautifully"; then a colour gradient for the rain so the
  nixos and matrix themes can go and the look is general; any logo, the NixOS one the default; no
  CachyOS remnants; colours that cycle and "how many color flavors at the same time ... every ray
  for example having its own uniqe color, and then it pulses", with one static colour still there;
  "1 html file in the root next to .install.sh", the `web` and `extras` folders gone. Build 22.

* **2026-10-14 15:26**: "continue as recommended" (the review first, build 19); then the page "a
  live previewer that lets you directly see what it'll look like, and then lets you export/save
  the json config file, if then applied with that exported json, it should look exactly like it
  did in the html previewer"; "fix the bugs first of course". Builds 19 and 21 (20 is the
  consolidation).
* **2026-10-14 12:10**: a full review of build 17; "Yes, make build 18 please" with M1 to M3 and
  the one-line fixes; on GitHub, "makes sure that the login screen replacement remains fully
  optional, and that those who just want the wallpaper that their existing login method isn't
  touched". Build 18.
* **2026-10-13 15:29**: build 16 works; the box on all screens, always; no Plasma logo or old
  wallpaper between the login and the rain. Build 17.
* Earlier answers, dated: `docs/HISTORY.md`, "The operator's words".

## Planned builds

1. **Consolidation** (30): the documents true and short again, the README says what syncrain is
   now (syncrain backdrop: the rain as your desktop, login screen, lock screen and video) and why the
   boot stays plain text (the text means the machine is not up yet, the rain that it is).
2. **The installer for four families** (31): `install.sh` with apt (Debian, Ubuntu, Mint), dnf
   (Fedora) and zypper (openSUSE) beside pacman; Debian tested in the sandbox, the others against
   stand-ins and said to be untested until someone runs them. The README invites anyone else to
   hand the repository to their AI agent to adapt.
3. **A NixOS image** (32 or later) with syncrain as its wallpaper, login screen and lock screen,
   the base the others are written against.

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
| Plasma still loads its lock-screen wallpaper under syncrain's, unseen | `kscreenlockerrc`, only with `--lock-screen` |
| The lock screen on NixOS: `nix/lockscreen.nix` builds it; nothing points KWin at it yet | `nix/nixos-module.nix` |
| A video's watts against the live rain's: not measured (no graphics card in the sandbox) | measure on their machine before claiming it uses less |
| The page's Video needs WebCodecs with a VP9 or VP8 encoder (Chrome, Edge, Firefox); Safari may say it cannot | `syncrain --video` instead |
| The settings file holds no `background`, `mask`, `scale` or `layer` (the page cannot preview a picture file) | `syncrain/app.py` (`CONFIG_KEYS`) and the page, if wanted |

## Build cadence

Consolidation builds: every build number ending in 0, and no other build. Fixed: the operator's
rule, adopted at build 3. A consolidation changes no behaviour: it folds older notes into the
history, makes every document true and short again, and writes down what it finds as open items.

Next consolidation: 30

`tests/contract/test_the_working_documents_are_current.py` reads the two lines above.

## Standing constraints

* **Release**: only `tools/package_release.py` makes an archive and writes `BUILD_NUMBER`; notes in
  the same pass, ending in GATE_RESULT; the gate runs every lane; generated pages are regenerated
  and compared.
* **Picture**: the stream changes only on purpose; the hosts draw the same frame; nothing
  flashes (the fastest colour cycle is 90 s).
* **OpenGL**: never ask GTK for a version; take what it hands out and check it.
* **Writing**: short and plain; no long dashes; "the operator" or "they"; comments say why, not
  when; one home per fact.

## Not scheduled

* A public randomness beacon (drand) in the seed: truly random, still in sync.
* Two screens in the Sway lane (the KWin lane has two).
* Pausing on wlroots compositors that keep asking a hidden wallpaper for frames, if one turns up.
