# Target environment

Where syncrain runs. The build sandbox: `docs/agent/ENVIRONMENT.md`.

## The operator's desktop

* CachyOS, KDE Plasma 6 on Wayland, Konsole with fish, two screens; Python 3.14, gtk4-layer-shell
  1.3.0. Pacman snapshots the system around every transaction.
* AMD Ryzen 9 9950X3D, about 92 GiB of RAM; NVIDIA GeForce RTX 5090 (idles at 50 W with both
  screens on).
* syncrain there (sweep of build 8, 2026-10-09): the native wallpaper 123 MiB and 0.9% of a core at
  30 fps, the GTK host (`--host gtk`) 205 MiB and 4.7%; +11.9 W at 30 fps, +7.3 W at 20, +3.5 W at
  15, about 0.17 J a frame per screen; 0 W behind a covering window; 97 to 100% even and steady.
  The home of these numbers; the other documents point here.
* Memory: builds 8 to 10 grew 0.9 MiB a minute (NVIDIA's explicit sync, off since build 11); build
  11 rose to 225 MiB in 18 h, then fell to 170 by itself: freed, not leaked. Build 12 and later hand
  it back every five minutes; no record from there yet.
* They started syncrain from a terminal (fish) before the service.
* Login screen: Plasma Login (`plasmalogin.service`, not SDDM). Build 16's `install.sh
  --login-screen` replaced it with greetd on 2026-10-13 (greeter UID 939); `--login-screen-off`
  goes back to it. Their locale is Dutch (nl_NL): a comma is the decimal sign.
* Archives get unpacked under `/data/projects/...`; installed with `./install.sh`. Boot is plain text
  (Plymouth off, by choice), with a LUKS prompt.

## NixOS

The base syncrain is written for: the operator is moving there from CachyOS, and is making a NixOS
image of their own. The flake's package and modules are built and evaluated every release
(`tests/nix/`), and the NixOS module's login screen runs in a headless KWin there; no NixOS
machine has booted them yet. The NixOS module gives the wallpaper, login screen and lock screen;
the flake template's whole system (Plasma 6 with all of it) builds here.

## What every target needs

`docs/OPERATIONS.md`, "Install".
