# Build 25: the lock screen, the rain and your box (optional)

**Type: feature; the picture does not change** (stream `a9c058f3`). Made on 2026-10-15, as the
operator asked at 22:44 the evening before: "we do want it visible as a lock screen wall paper as
well, and also thus a login box in the midde of our own".

## The lock screen (`./install.sh --lock-screen`, KDE Plasma 6 on Wayland)

* Plasma's own locker stays (KWin 6 lets no other in), and shows syncrain's screen: the rain, live
  and the desktop's frame, behind syncrain's box (your name, the password, Unlock, PAM's words, Caps
  Lock) on every screen. PAM's service `kde` still decides; a wrong password is said, cleared and the
  box shakes.
* How: a shell package `org.syncrain.lockscreen` (QML) and a QML module drawing the native passes
  (build 14's Plasma wallpaper item, without its KWin watch), named to KWin's unit alone in a
  systemd drop-in. Plasma's shell, its layout and the global theme are untouched; the module is built
  with `cmake qt6-base qt6-declarative`, all of it under your home.
* The rain draws the scene the wallpaper writes at every start (`syncrain --write-scene`), so the
  lock screen has your settings and runs no Python. Without the module the box works on black;
  a lock screen that cannot load is Plasma's built-in one.
* `--lock-screen-off` takes exactly those files away; `--uninstall` too. Every later install keeps
  the lock screen on its build.

## Tests

* A new lane, `lockscreen`: the lock screen's frame is the GTK host's beside the box; the box
  against a stand-in of the locker (wrong, then right); without the module the box still unlocks;
  and a real headless KWin, locked over D-Bus, starts Plasma's locker with syncrain's screen on both
  screens, stays locked when "wrong" is typed on its keyboard and unlocks on "right", PAM seeing
  exactly those two.
* The installer: nothing without `--lock-screen`; the variable set in KWin's drop-in and nowhere
  else; `--lock-screen-off` and `--uninstall` remove what it made and nothing more; a shell package
  named in plasmashellrc is left alone.

## What the operator does

* `./install.sh --lock-screen` from `syncrain_build_25/` (pacman adds `cmake qt6-base
  qt6-declarative`), then log out and back in once. Lock (Meta+L) and look.
* Should it ever not unlock: Ctrl+Alt+F3, log in there, `loginctl unlock-sessions`, then
  `./install.sh --lock-screen-off`.
* `journalctl --user -b | grep syncrain` says whether the rain drew on each screen.

## Verification

392 passed in 975.37s (0:16:15)
