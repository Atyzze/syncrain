# Build 33: syncrain backdrop as a NixOS flavour, one flake template away

**Type: feature; the picture does not change** (stream `822ea58a`). Made on 2026-10-15, as the
operator chose after build 32: the NixOS image as a flake template ("1-click apply"), not an
installer ISO for now.

## The template

* `nix flake init -t github:Atyzze/syncrain` makes a flake (`nix/template/`): `flake.nix` with this
  repository as an input (following the system's nixpkgs), `configuration.nix` with the lines to
  change marked (boot loader, name, user, time zone; the look as `settings = ./config.json`), and a
  README with the five steps, ending in `sudo nixos-rebuild switch --flake .#backdrop`.
* Boot stays as the machine has it: the template asks for the boot loader it uses now, and nothing
  adds a splash (NixOS has no Plymouth unless asked).

## The flavour

* `syncrain.nixosModules.backdrop` (`nix/backdrop.nix`): KDE Plasma 6, the rain as wallpaper,
  login screen and lock screen, SDDM off, a network, sound and the clock in sync, each a default a
  configuration can change.
* The flake's modules are keyed, so a configuration that imports both `backdrop` and `default`
  gets the module once.

## Tried

* The template's whole system, with a stand-in for the hardware, built here: Plasma 6, greetd with
  syncrain's login screen, KWin's drop-in for the lock screen, every derivation (about 500 MB from
  the binary cache, the rest built). No machine or VM has booted it (no KVM here).

## Tests

* The nix lane evaluates the template's system: no failed assertion, Plasma 6 on, SDDM off, greetd
  with the login screen, the lock screen's drop-in, no Plymouth; the flake names the template, the
  template's files and what to change.

## What the operator does

* On NixOS: the five steps in the README ("On NixOS"). On CachyOS: nothing.

## Verification

477 passed in 1137.22s (0:18:57)
