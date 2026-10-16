# Build 45: an SVG as the logo, the desktop's settings in the file, a seekable WebM

**Type: feature** (the stream does not change). Made on 2026-10-16, the fourth of the builds on the
roadmap's open items.

## An SVG as the desktop's logo

* The page took an SVG as the logo; `--logo FILE` took PNG, JPEG and WebP only (Pillow draws no
  SVG). An SVG, known by its name or its first bytes, is now drawn by GTK's picture loader
  (librsvg's) at the texture's size, so it is sharp, and made into the logo as any picture is.
* Where the loader is missing, syncrain says which package has it: `pacman -S librsvg`,
  `apt install librsvg2-common`, `dnf install librsvg2`, `zypper install gdk-pixbuf-loader-rsvg`.
  An SVG it cannot draw is refused at once, as any file that is no picture.

## The desktop's settings in the settings file

* `background`, `mask`, `scale` and `layer` can be in the settings file, as their options.
* A picture's path given relative (a `logo` file's too) is beside the settings file, wherever it
  is read from; it was beside wherever syncrain was started. `./install.sh --config FILE` names
  such a picture whole when it keeps the file in `~/.config/syncrain`, so it still finds it.
* The page takes these four, says they are the desktop's, keeps them across a preset and writes
  them back into the file it saves. It cannot show them.
* The login screen's copy of the settings leaves the four out: greetd's user cannot read a picture
  in the operator's home, and a scale or layer is the wallpaper's alone. A logo from a file goes along made
  into the logo's texture inside the copy, as the page keeps one; before, the login screen's rain
  could not read it. The installer names that picture, as it shows before anyone logs in.

## A SeekHead in the page's WebM

* A video the page makes now starts with a SeekHead naming where its Info, Tracks and Cues are, so a
  player finds the cues (and seeks) without reading to the end first.

## The review of this build

An agent that did not write it read it: nothing critical. Fixed above or here: a settings file
starting with a byte order mark (the installer's own reading of it refused it, and the login
screen got it whole, pictures and all); a settings file that is a link (its pictures are beside the
file itself); `.before` written over when the same file is given again; a file named as a logo
(`nixos`) taking the logo's place on the desktop only; a blank path the page and the desktop judged
apart; a picture moved after install stopping the wallpaper (it now starts without it, and says
so); the installer now names a picture it puts on the login screen; an SVG known by its first bytes
after a doctype or comment.

## What the operator does

* Nothing. To use an SVG as the logo: `syncrain --logo file.svg`, or `"logo"` in the settings file.

## Verification

569 passed in 1448.74s (0:24:08)
