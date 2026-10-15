# Build 28: your new default, the NixOS colours logo gone, the README rewritten

**Type: feature; the stream changes on purpose** (stream `85ace386`, was `a9c058f3`). Made on
2026-10-15, as the operator asked at 12:49: "this 'nixos colours' option doesnt seem to do anything
meaningful, get rid of it, also, please update our defaults to the config.json I just supplied ...
update the readme to make sure its well instructed and matches the default output".

## The default (the `syncrain` preset)

* From their settings file of 12:49: the NixOS logo at 0.44 of the screen (was 0.35), its rainbow
  turning every 40 s (was 30), and snow. The rest as build 24: white-tailed matrix colours, 64 in a
  wave turning every 440 s, bloom 5, a black background (their file's background colours sit at gain
  0, so black is what it draws), their symbols and words. Their file drawn by build 27 and the
  default drawn by build 28 are the same frame, to the pixel.

## The NixOS colours logo, gone

* The logo's rainbow paints the white NixOS logo the same, so the coloured one went: from the page's
  Logo choices, the options, the Nix options, the shipped files and the stream. A settings file or
  command line that still says `nixos-colours` draws the NixOS logo instead of failing.

## The README

* Rewritten for someone who has just found it: what syncrain is, what the default looks like (the
  picture drawn again, snow and all), what you get, how to install, make it yours, add the login and
  lock screens and undo them, what to do when it does not draw, and how to remove it.

## From the review (an agent that did not write it)

* `nixos-colours` stays a word the Nix modules take (drawing the NixOS logo), so a NixOS
  configuration that names it still builds. The code says the NixOS logo is drawn instead, not the
  same picture: the coloured one was darker under the rainbow.
* A settings file saved with the syncrain preset leaves its preset's values unsaid, so files from
  before build 28 now snow too: `--snow off` (or snow Off on the page) turns it off.
* The README says where covered screens stop drawing (KDE Plasma), that GNOME has no wallpaper
  layer, and where the power figure comes from; the page against the app is compared with the snow
  off now that the default snows.

## Tests

* The default is the new look; the snow option is tested turned off, since the default now snows.

## What the operator does

* `./install.sh` from `syncrain_build_28/`. Your saved settings file is this default already, so
  nothing changes on screen; the page's Logo choices lose "NixOS colours".

## Verification

397 passed in 1049.87s (0:17:29)
