# Target environment

Where syncrain runs. The build sandbox: `docs/agent/ENVIRONMENT.md`.

## The operator's desktop

* CachyOS, KDE Plasma 6 on Wayland, Konsole with fish, two screens; Python 3.14, gtk4-layer-shell
  1.3.0. Pacman snapshots the system around every transaction.
* AMD Ryzen 9 9950X3D, about 92 GiB of RAM; NVIDIA GeForce RTX 5090 (idles at 50 W with both
  screens on).
* syncrain there (sweep of build 8, 2026-10-09): 123 MiB and 0.9% of a core at 30 fps; +11.9 W at
  30 fps, +7.3 W at 20, +3.5 W at 15; 0 W behind a covering window; 97 to 100% even and steady.
* Memory: builds 8 to 10 grew 0.9 MiB a minute (NVIDIA's explicit sync, off since build 11); build
  11 rose to 225 MiB in 18 h, then fell to 170 by itself: freed, not leaked. Build 12 and later hand
  it back every five minutes; no record from there yet.
* They started syncrain from a terminal (fish). Builds 13 and 14's Plasma wallpaper was "severely
  broken" there (2026-10-11).
* On Plasma syncrain takes the bottom layer and covers the desktop icons; "show desktop" hides it.
* Login screen: Plasma Login (`plasmalogin.service`, not SDDM). Build 16's `install.sh
  --login-screen` replaced it with greetd on 2026-10-13 (greeter UID 939); `--login-screen-off`
  goes back to it. Their locale is Dutch (nl_NL): a comma is the decimal sign.
* Archives get unpacked under `/data/projects/...`; installed with `./install.sh`.

## NixOS

The flake's package and modules are built and evaluated every release (`tests/nix/`); no NixOS
machine has run them yet.

## What every target needs

`docs/OPERATIONS.md`, "Install".
