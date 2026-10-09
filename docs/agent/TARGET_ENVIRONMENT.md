# Target environment

Where syncrain runs. The build sandbox: `docs/agent/ENVIRONMENT.md`.

## The operator's desktop

* CachyOS, KDE Plasma 6 on Wayland, Konsole with fish, two screens; Python 3.14, gtk4-layer-shell
  1.3.0. Pacman snapshots the system around every transaction.
* AMD Ryzen 9 9950X3D, about 92 GiB of RAM; NVIDIA GeForce RTX 5090 (idles at 50 W with both
  screens on).
* syncrain there (sweep of build 8, 2026-10-09): 123 MiB and 0.9% of a core at 30 fps; +11.9 W at
  30 fps, +7.3 W at 20, +3.5 W at 15; 0 W behind a covering window; 97 to 100% even and steady.
* Memory grows about 0.9 MiB a minute while drawing (btop: 154 MiB after 44 minutes, 200 after
  about 90). NVIDIA's explicit-sync leak; build 11's job. Build 7 climbed the same way (287 to 420
  MiB) and stopped overnight, when the screens were off.
* On Plasma syncrain takes the bottom layer and covers the desktop icons; "show desktop" hides it.
* Archives get unpacked under `/data/projects/...`; installed with `./install.sh`.

## NixOS

The flake's package and modules are built and evaluated every release (`tests/nix/`); no NixOS
machine has run them yet.

## What every target needs

`docs/OPERATIONS.md`, "Install".
