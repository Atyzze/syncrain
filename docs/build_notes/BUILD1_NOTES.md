# Build 1: the live wallpaper, synchronised by the clock

**Type: feature.** Made on 2026-10-06 from the operator's message after the GIFs: "could we not
make a dynamically real time generated one? where we based it off some genuine random process so
that there is never a repeat and then also make it possible so others can sync into the same
stream, say base it on the UTC clock", for Linux, perhaps as part of a NixOS image, with a NixOS
theme and the NixOS logo in place of the CachyOS C. These notes were written at build 3 from the
record of the conversation; build 1 itself had none, and was delivered as `syncrain-0.1.0.tar.gz`.

## What it was

* A frame as a pure function of (UTC seconds since 2024, the fraction, the channel's FNV-1a hash),
  through integer hashes, in six GPU passes: state, field, glyphs, two blurs, composite.
* Two themes: nixos (blue rain of Nix store-hash characters, lambda and snowflakes, hidden words,
  four depths of falling ice crystals, the official NixOS snowflake, CC BY 4.0) and matrix (green
  katakana; with `--background` and `--mask`, the darkened CachyOS look).
* The native app: GTK 4, a GLArea per viewport, PyOpenGL; Wayland layer-shell (bottom layer on KDE),
  X11 desktop window, `--window`, `--screenshot`, `--record`, `--scale`.
* The web page: one self-contained file, the same shaders in WebGL2, a control strip.
* Nix: a flake with the package, the web bundle, a NixOS module and a home-manager module.

## What the operator did

Unpacked it; tried it once build 2 brought an installer (build 1 had none for Arch).

## Verification

Run by hand, before this project had a gate: the page in headless Chromium (identical rain grids at
1280x720 and 1920x1080); the app on X11 (Xvfb, Mesa llvmpipe) and as a Sway background layer; web
against native, 0.16 of 255 on average; `nix build` against nixos-unstable 151fa4e8; the NixOS
module evaluated in a full system, the home-manager module evaluated.
