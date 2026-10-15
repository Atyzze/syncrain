# Build 30: consolidation

**Type: consolidation; nothing changes on screen** (stream `822ea58a`). Made on 2026-10-15.

## Folded

* Builds 19 to 28's notes folded into `docs/HISTORY.md` and removed: a few lines a build with its
  gate's count, and the operator's words from 2026-10-14 18:25 to 2026-10-15 13:37.
* `docs/ROADMAP.md` keeps the decisions since build 28; the earlier ones are in the history.
* `docs/LESSONS.md`: the lessons of builds 21 to 29 (Plasma's locker and its PAM delay, what lock
  screens share, two rasterizers' 8-bit blur, BT.709, a limit that has to fit the screen, a new
  default hiding old tests); the sandbox's traps moved to `docs/agent/ENVIRONMENT.md`.

## Made true

* `README.md`: **syncrain backdrop**, the operator's name for it: live code rain for the whole
  session (desktop, login screen, lock screen, the page, videos), NixOS the base; why boot stays
  plain text (the text means the machine is not up yet, the rain that it is); the NixOS modules
  start the wallpaper only.
* `docs/agent/HANDOFF.md`: short again, pointing to each fact's home; three presets, not two.
* `docs/ARCHITECTURE.md`: a Video section; one NixOS logo, made by `build_assets.py`, syncrain's by
  `build_logo.py`; only the native wallpaper rewrites the lock screen's scene; the measurements'
  home is `docs/agent/TARGET_ENVIRONMENT.md`, which now has the GTK host's numbers and the plain-text
  boot.
* `docs/OPERATIONS.md`: what `--preset` and the others go into (the lock screen's scene; the login
  screen's rain only with `--login-screen`); the service written with that run's options; what
  `--lock-screen` does to plasmashellrc and `--lock-screen-off` puts back; the Nix options left to
  `nix/options.nix`; `--logo` takes what Pillow reads; a symbols file is used only when the
  settings file names no sets; +11.9 W; the Arabic font in the credits and the asset recipe; video
  said once.
* Help texts: `--words` up to 30 characters (it said 40), `--logo` formats, `--list-themes`,
  `--record-seconds` and `--record-fps`; the installer says what `--login-screen` writes outside
  your home; the Nix options' texts (the syncrain preset, the logo's older names, bgGain,
  hieroglyphs); the test runner names the native lane.

## Open items

* In `docs/ROADMAP.md`, "Open items": L8, L11, L20, L21, an SVG as the desktop's logo, the lock
  screen's frame rate and keyboard layout, Plasma's hidden lock-screen wallpaper, the login and lock
  screens on NixOS, a video's watts, Safari's video, the WebM's SeekHead, the settings file without
  `background`, `mask`, `scale` and `layer`.
* Build 31 is the installer for Debian, Fedora and openSUSE (`docs/agent/NEXT_BUILD.md`).

## What the operator does

* Nothing is needed. Installing it (`./install.sh` from `syncrain_build_30/`) changes nothing on
  screen; the README on GitHub reads as syncrain backdrop.

## Verification

432 passed in 1165.59s (0:19:25)
