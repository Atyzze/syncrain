# Build 24: your settings file of 22:33 is the default

**Type: feature; the stream changes on purpose** (stream `a9c058f3`, was `f98ef1ca`). Made on
2026-10-14, as the operator asked at 22:33: "can we push this as new default template for syncrain
on our github please", with their settings file attached.

## The syncrain preset, again from their file

* The matrix colours with a white tail and a bright glow (`#00ff51`), 64 colours in a wave across
  the screen turning every 440 s, a black background, vignette 0.66.
* The NixOS logo at 0.35, turning once in 300 s, its rainbow every 30 s, no drift, no glow.
* Bloom 5: their 2 times build 23's 2.5, so the slider's 1 is their look. Their background gain 0
  drew it black whatever its colours, so the preset's colours are black.
* Their symbols: the digits without 6 and 7, `sSs` among the symbols; their words as before.
* With nothing said, the wallpaper, the login screen and the page draw it. Their file drawn by
  build 23 and the default drawn by build 24 are the same frame, to the pixel (GTK host, Xvfb).
* Their redrawn logo stays a choice (`--logo syncrain`); NixOS and Matrix stay presets.
* The README's picture of the default is drawn again.

## Tests

* The default is their look: the preset, the logo, the wave, the bloom, the black background, the
  logo's motion; their logo is still a choice.

## What the operator does

* **First, your kept settings file**: it still wins, and over the new default its bloom 2 doubles
  the bloom. On the page pick Syncrain, Save config.json, then `./install.sh --config config.json`
  (the login screen's copy follows).
* The lock screen is still Plasma's own: the rain and syncrain's box there are build 25, the boot
  splash through the LUKS prompt build 26 (`docs/ROADMAP.md`).
* Glow and Background have nothing to scale on this default (no logo glow, a black background).

## From the review (an agent that did not write it)

* The render lane's glow and bg-gain checks run under nixos; the help says the default has none.
* Page and desktop: the bloom's 8-bit rounding differs between Chromium's and Mesa's rasterizers
  and the gain of 5 multiplies it (1.24 apart, evenly spread; 0.03 with the bloom off). The frames
  are compared at a gain of 1.25, and every other pass with the bloom off to 0.15, nixos included.
* On GitHub: pushed as `syncrain build 24` after the gate (23 was not there before).

## Verification

380 passed in 785.73s (0:13:05)
