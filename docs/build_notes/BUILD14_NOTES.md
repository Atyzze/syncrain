# Build 14: the Plasma wallpaper, reviewed

**Type: fix; the picture does not change** (stream `c18f8be2`). Made on 2026-10-10. Build 13 passed
its gate, then its review found what is below, so 13 was not delivered: this is the first Plasma
wallpaper the operator gets. Build 13's notes say what it is.

## Fixed (`syncrain/plasma/`, `syncrain/native/kwin.c`, `install.sh`)

* The render thread no longer touches the item: switching the wallpaper away mid-frame could crash
  Plasma's shell.
* A shell that quits unloads its KWin script; scripts of a shell that crashed are unloaded by the
  next one.
* A KWin that restarts (Plasma 6 restarts a crashed one) gets the script again within 30 s, so a
  screen never stays paused.
* Settings changes wait 400 ms before a scene is made, as meant; half-written scenes are cleared.
* The lock screen draws the last scene at once while its own is made; a scene removed from the
  cache is made again instead of leaving the screen blank.
* Without OpenGL in Qt Quick the item says so instead of crashing; Qt's pixel alignment is put back.
* An item not on screen looks again once a second, not at the frame rate.
* `--uninstall` without Plasma's shell keeps the wallpaper, and the app it makes scenes with, while
  the desktops still use it (a removed one leaves them black) and says so.
* A second review: one scene build at start, not two; a KWin that was restarting when asked is
  asked again; an unreadable scene says so instead of trying again every frame.

## Tests

* `tests/plasma/`: the uninstall case above. The Arch root ran it all again in a real `plasmashell`
  and `kscreenlocker_greet --testing`: both draw, and `--uninstall` puts both back.

## What the operator does

* Stop the syncrain in the terminal (Ctrl+C), then `./install.sh --plasma` from
  `syncrain_build_14/`. Right-click the desktop, Desktop and Wallpaper, for its settings.
* If the desktop stays black or says the wallpaper failed: `syncrain --diagnose`, and
  `journalctl --user -b | grep syncrain`.
* Back to before: `./install.sh --uninstall`, then `./install.sh --autostart`.

## Verification

214 passed in 631.67s (0:10:31)
