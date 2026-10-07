# Build 2: the logo against burn-in, and an installer for Arch

**Type: feature.** Made on 2026-10-06 from the operator's message: "lets have the nix os slowly
rotate as well, and cycle through all the rainbow colors potentially as well, as to have the
screensaver als function as a basic pixel cleaner", and "have it work on arch based OSs basically,
with a simple intaller .sh script attached". These notes were written at build 3 from the record
of the conversation; build 2 had none, and was delivered as `syncrain-0.1.0.tar.gz`, the same name
as build 1, which is what build 3's numbering ends.

## What it was

* The logo turns once every 3 minutes, its colours run round a rainbow wheel every 90 seconds, and
  it drifts up to 3% of the screen height; with an image background the masked logo cycles colour
  and the image pans; `--rainbow logo|all|off`, `--spin`, `--drift`; all clock-synchronised, in
  whole cycles per hour. No flashing: a pixel cleaner's strobe is a photosensitivity risk.
* `install.sh` for Arch-based systems: pacman packages, the app in `~/.local`, a launcher that
  preloads gtk4-layer-shell, an optional systemd user service, `--uninstall`.
* The Nix modules quote `%` and `$` for systemd.

## What the operator did

Installed it on CachyOS (KDE Plasma, two screens) and ran `syncrain`: both wallpaper windows
stayed grey with "OpenGL unavailable: Unable to create a GL context" until Ctrl+C, which printed a
traceback. Build 3 explains and fixes it.

## Verification

Run by hand: `install.sh --yes --autostart` in a real Arch root (October 2026 packages, GTK 4.22)
as a user with sudo; there, the app on X11 (frame identical to the page) and live as a Sway
background layer, then `--uninstall`; `nix build` and both modules evaluated. Every OpenGL run used
Mesa, which shares contexts across OpenGL and OpenGL ES and so could not show the operator's failure.
