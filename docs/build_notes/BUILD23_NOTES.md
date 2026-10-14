# Build 23: your look is the default, your logo as an SVG, a colour over any logo

**Type: feature; the stream changes on purpose** (stream `f98ef1ca`, was `25b02556`). Made on
2026-10-14, as the operator asked at 19:53: their settings file as a preset and the default, the
NixOS logo still a choice; their logo cleaned up, "perhaps turn it into a svg"; "a color slider for
the potential logo in the middle, as an overide color channel on a user chosen png".

## The syncrain preset, the default

* Made from their settings file: the matrix colours and symbols, 64 colours at once by the channel
  turning every 55 s, bloom 2.5 (their 2 times matrix's 1.25, so the slider's 1 is their look), no
  snow, their words (with `sSs`), their logo in its own colours at the size it had on screen.
* With nothing said, the wallpaper, the login screen and the page draw it. `--preset nixos` (or the
  page's NixOS snow) is the look of before; the NixOS logo is a choice under any preset.

## The logo as an SVG

* `syncrain/data/logo-syncrain.svg`: the ring, the head, the arms in a V, the spine and the two
  lobes as circles, lines and rounded shapes, fitted to their picture (laid over it, the two share
  95% of their ink), the strokes one width but the spine's.
* `tools/build_logo.py` makes the texture from it (`logo-syncrain.png`, as the NixOS ones are made).

## One colour over a logo

* `--logo-color C`, the settings' `logo_color`, the page's Logo, Colour: one colour over the
  logo's shape, any logo or a picture of one's own; its glow takes the colour too. `own` (or Its
  own) for its own colours again. The logo's rainbow, when on, turns over that colour.
* The Nix modules: `logoColor`; the presets and logos include `syncrain`.

## From the review (an agent that did not write it)

* One colour picked on the page stills the logo's rainbow (which would turn its hue away), and Its
  own brings the rainbow back; a black logo shows the rainbow in full when it is on.
* Tests that the new default made pass without testing anything (snow off, the logo's rainbow off)
  test with snow on, or under nixos. The help, the installer's and the Nix options' texts say the
  preset's where they said nixos's values; the licence names the NixOS logo files only.

## Tests

* The default draws their look on the page, the GTK host and the native wallpaper alike; NixOS
  draws as before; a coloured picture draws the same on the page and the desktop and on both hosts.

## What the operator does

* Install it as usual: the default is now your look. A settings file you saved still wins; to see
  the new default, `./install.sh --config` a file saved after picking Syncrain on the page, or move
  `~/.config/syncrain/config.json` away.
* On the page: Logo, Colour, One colour, and pick it.

## Verification

377 passed in 712.20s (0:11:52)
