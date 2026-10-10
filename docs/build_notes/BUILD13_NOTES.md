# Build 13: the Plasma wallpaper

**Type: feature; the picture does not change** (stream `c18f8be2`). Made on 2026-10-10.

## What it is (`syncrain/plasma/`)

* A Plasma 6 wallpaper: pick "syncrain" in Desktop and Wallpaper, or in Screen Locking >
  Appearance. Plasma draws it behind the desktop icons; no service, no terminal.
* Inside: a QML item, `SyncRain` (C++), that draws with the native wallpaper's own passes on the
  shell's OpenGL context. Its scene comes from `syncrain --write-scene`, the code every host uses,
  cached in `~/.cache/syncrain/`.
* The settings page has every picture option, the frame rate, the pause and the resolution.
* On the desktop, a screen under a maximized or full-screen window is not drawn (KWin says which,
  through the native wallpaper's `kwin.c`). The lock screen never pauses.
* The shell hands freed memory back every five minutes; `syncrain --diagnose` lists the shell when
  it draws syncrain.

## Install (`install.sh --plasma`)

* Builds the item with CMake (pacman: `cmake qt6-base qt6-declarative`), puts it in Qt's QML
  folder (sudo), the package in `~/.local/share/plasma/wallpapers/`.
* Makes it the wallpaper of every desktop and of the lock screen; `--theme`, `--channel`,
  `--rainbow` and `--arg` become its settings. Turns the autostart service off.
* `--uninstall` puts both back on Plasma's image wallpaper.
* NixOS: the flake's `syncrain-plasma` package, next to `syncrain`.

## Also

* `syncrain/native/passes.c`: the six passes, out of `render.c`, for both programs.
* Build 12's review: `--diagnose` no longer stops on a process with an odd name, and finds the
  GTK host of the Nix package; the page reads its options once, not every frame.

## Tests (the new `plasma` lane, `tests/plasma/`)

* Built with Nix's Qt: the item draws the GTK host's frame (defaults and every option); the
  package passes its settings on; the settings page loads with Kirigami; under KWin a maximized
  window stops the drawing; `install.sh --plasma` and `--uninstall` against stubs.
* Not here: a real Plasma shell. libplasma's `WallpaperItem` is a stub, so the operator's desktop
  is the first to run the package in Plasma itself.

## What the operator does

* Stop the syncrain in the terminal (Ctrl+C), then `./install.sh --plasma` from
  `syncrain_build_13/`.
* If the desktop stays black or says the wallpaper failed: `syncrain --diagnose`, and
  `journalctl --user -b | grep syncrain`.
* Back to before: `./install.sh --uninstall`, then `./install.sh --autostart`.

## Verification

214 passed in 589.28s (0:09:49)
