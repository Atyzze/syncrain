# Build 22: your own colours, many at once, any logo; one page at the top

**Type: feature; the stream changes on purpose** (stream `25b02556`, was `def5684f`). Made on
2026-10-14, as the operator asked at 18:25: a colour gradient for the rain so the themes can go,
any logo with the NixOS one the default, no CachyOS remnants, colours that cycle and "how many
color flavors at the same time", one static colour still there, and one html file next to
`install.sh` with the `web` and `extras` folders gone.

## The look

* **No themes**: nixos and matrix are presets, where the look starts. Every setting goes over the
  preset (`engine.compose`, the page's `composeLook`): `--preset` (`--theme` still works).
* **Rain colours**: the gradient (dark, middle, bright, leading symbol) and the glow:
  `--rain-colors`, `--glow-color`, `#rrggbb` each.
* **Colours at once** (`--flavours N`, 1 to 64): each column of rain one of N hues, the gradient
  turned round the colour wheel; `--flavour-layout random` by the channel (the same columns on every
  machine) or `wave`, in order across the screen.
* **Colour cycle** (`--cycle S`): every flavour turns round the wheel together, an RGB keyboard's
  rainbow; 0 keeps them still. `--rainbow` still reads (`all` is `--cycle 600`).
* **One colour and no cycle is the picture as it was**: the nixos frame is the same as build 21's to
  the pixel.
* **Background**: `--background-colors` (top, bottom, centre glow), `--vignette`.
* **Logo**: `nixos` (the default), `nixos-colours`, `none`, or any picture (`--logo FILE`; on the page,
  Your picture). It is made into the logo's texture (a square, the picture in its middle two
  thirds), which the page keeps in the settings file, so the desktop draws the very pixels.
  `--logo-size`, `--logo-cycle` (its rainbow; 0 = its own colours).
* **Hidden words**: `--words`, or on the page under Symbols.
* **Snow** for every preset (off by default for matrix).
* **CachyOS gone**: its word from the matrix words, its logo mask and the recipe for it.

## The page

* `index.html` at the top, next to `install.sh`: the one page. `tools/build_web.py` fills its data
  in place; `--strip` empties it for editing; `--artifact FILE` writes the live page's copy.
* What `web/` held: `template.html` (the page's source), `index.html` (it filled in, to open) and
  `artifact.html` (for the live page). What `extras/` held: the CachyOS logo mask.
* Settings: start from a preset; rain colours with a strip of the flavours; how many, colour cycle,
  spread; background colours, vignette, snow; logo (a picture of your own), size, rainbow, turn,
  drift; hidden words. The panel's accent follows the rain's colours.

## Also

* Nix modules: `settings` (a `config.json`), `rainColors`, `glowColor`, `backgroundColors`,
  `vignette`, `flavours`, `flavourLayout`, `cycle`, `logo` (a name or a picture), `logoSize`,
  `logoCycle`, `words`; `snow` follows the preset when unset.
* A font file whose name is not UTF-8 no longer makes a symbols file fall back (open item).
* Messages say preset where they said theme.

## From the review (an agent that did not write it)

* The hidden words hold at most 254 different characters (a word's slot is a byte): more crashed
  the wallpaper and drew the wrong symbols on the page, and a page left with such a draft stayed
  black. A draft whose symbols cannot be drawn now starts from the defaults.
* `--rainbow` is read where it stands among the options, so on the command line it goes over a
  settings file again (`./install.sh --config ... --rainbow off`).
* Build 21's matrix files (which said `"snow": true` for every theme) still draw without snow.
* `--logo FILE` refuses what is no picture (an SVG) at once, with status 2, not at the first frame
  (status 1, restarted for good); a phone's photo comes out upright; a large one decodes small.
* `--check-config` makes the words and the logo as the wallpaper will.
* The Nix module leaves the preset, the channel and the frame rate to its `settings` file when they
  are not set; colours and words are checked when the configuration is built.
* The page: a null in a file is no value, as on the desktop; `rainbow` read where it stands; words
  read as the desktop reads them; a picture that cannot be drawn is not saved; one picture's
  texture at a time; the last picture comes back under Your picture; the snowflake's rainbow comes
  back with it; the picture is kept apart from the draft, which says so when the browser keeps
  nothing.

## Tests

* The browser lane draws a settings file with colours of its own, seven flavours cycling, both
  spreads, another background, a picture as the logo and words of its own on the page and the
  desktop, and compares the frames; one flavour is the old picture; a picture picked on the page
  lands in the settings file as the texture.
* The wayland lane draws such a look with the native wallpaper and the GTK host: the same to the
  pixel. Unit tests for the options, the settings keys, the logo and the presets.

## What the operator does

* Open `index.html` in the `syncrain_build_22/` folder, press Settings: try Colours at once with
  Wave and a Colour cycle of 20 s, or Your picture under Logo. Save config.json, then
  `./install.sh --config ~/Downloads/config.json`.
* A build 21 settings file still works as it is.

## Verification

375 passed in 841.52s (0:14:01)
