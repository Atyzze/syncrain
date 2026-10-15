# Build 37: the installer checks before it keeps, and never empties a folder that is not its own

**Type: fix; the picture does not change** (stream `1ad0a2dd`). Made on 2026-10-15, the fourth of the
builds that fix what the review of build 33 found. This one takes the installer's items: 8 to 11
and 39 to 46.

## The service

* **Options are checked first (8)**: `./install.sh --autostart --preset matirx` used to print Done
  and write the misspelling into the service, which then stopped at every login. Options and the
  settings file are read as the new app reads them before it is swapped in, and a wrong one ends
  the install there, with the installed app, its service and the login screen as they were.
* **Written again at every install (9)**: where the service is, each install writes it again, so a
  fix to it reaches an upgrade. Options given now go into it (and it says which ones from before
  go); with none given, it keeps its own, after this install's launcher (a service another prefix
  wrote no longer goes on starting that install's build). Lines added to it by hand are kept in
  `syncrain.service.before`; lasting changes go in a drop-in (`systemctl --user edit syncrain`).
* **Restarted on the new build**: a running service restarts wherever it was started; a failed one
  starts again (its cause may be mended) only while it is enabled, so one turned off stays off.
* **A start limit (44)**: the restarts slow down from every 3 s to one in two minutes, and stop
  after 30 tries in ten minutes, instead of every 3 s for good: a compositor or GPU that comes back
  after minutes still gets its wallpaper. Also in the NixOS and home-manager modules. `--host
  native` with an option it cannot use, or on a desktop without a wallpaper layer, ends with status
  2, which the service does not restart on.

## The app

* **Never a checkout (11)**: the installer refuses to run from the folder the app goes into, and
  replaces or removes only its own install (it now leaves a marker; an install from before the
  marker is known by having no `install.sh` or `.git`; an empty folder is taken). A clone kept at
  `~/.local/share/syncrain` was emptied before. `--uninstall` checks this before it takes anything.
* **Swapped in whole (45)**: the new app is made beside the installed one and swapped in, so an
  upgrade that stops half way leaves the installed one as it was (and puts it back if the swap
  itself fails).
* **No stale native program (41)**: one built by hand in the release folder is not installed when
  this build's fails.
* **One Python (10)**: the system's (`/usr/bin/python3`, where the family's packages go) when it
  has GTK 4's bindings, cairo and Pillow, else the first on PATH that has them; the launcher runs that one, so pyenv,
  conda or a venv first on PATH no longer breaks the wallpaper. `SYNCRAIN_PYTHON` still decides.
* **The prefix (40)**: made a whole path (links kept as written), refused with a character the launcher or systemd would
  read as its own, and taken from `SYNCRAIN_PREFIX` (or `--prefix`), not a `PREFIX` left in the
  environment by a build of something else.

## Smaller

* `--uninstall` with `--lock-screen-off` or `--login-screen-off` runs all of them; the first used to
  end the script (39).
* `--uninstall` removes the cache and state too, says the settings are kept, and names only what it
  removed (43). A record a way back kept because it could not finish (Plasma's shell did not
  answer) stays, with the state folder.
* Debian: the native build gets `libc6-dev` (42).
* `--config` gives the login screen the options of this run too, so its old ones no longer go over
  the new settings file there (46).

## The review of this build

An agent that did not write it read it: 14 rare findings (a kept launcher from another prefix, the
check after the swap, the uninstall's order and records, the restarts), all fixed above, and the
tests it found missing (a user systemd's answers, an install from before the marker) added.

## What the operator does

* `./install.sh` as usual (with `--autostart` only the first time). Nothing else changes.

## Verification

534 passed in 1243.55s (0:20:43)
