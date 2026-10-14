# Build 18: the review's first fixes; the login screen stays optional

**Type: fixes; the picture does not change** (stream `def5684f`). Made on 2026-10-14.

## Why

* A review of build 17, asked for on 2026-10-14, found nine faults of middling weight (M1 to M9) and
  21 small ones (L1 to L21). The operator chose M1 to M3 and the one-line fixes (M8, L1 to L4),
  and for GitHub: "makes sure that the login screen replacement remains fully optional, and that
  those who just want the wallpaper that their existing login method isn't touched".

## The login screen stays optional (`install.sh`)

* Only `--login-screen` changes how the machine logs in. Installing, upgrading and removing the
  wallpaper leave greetd, SDDM or Plasma Login, what starts at boot and their files as they were.
  A test runs each of these as a user who is not root, on a machine with a login screen of its
  own, and finds nothing done as root.
* `--login-screen-off` puts back exactly what started at boot before: SDDM, Plasma Login, greetd's
  own login, or none (M2). Build 17 switched to SDDM when it had no record, and a second run (as the
  hand-over asks when Plasma's shell does not answer) had none. Without syncrain's login screen
  it now changes nothing and says so.
* A display manager picked since `--login-screen` stays. One removed since no longer stops the way
  back (or `--uninstall`): greetd stays then, with its own config. When systemctl fails for another
  reason (sudo refused, say), the record stays and running it again finishes.
* The record is `/etc/greetd/display-manager.before-syncrain`: written by `--login-screen` before
  anything changes, deleted last, and it counts only while greetd starts at boot. Builds 16 and 17
  kept it inside the app copy, and none for greetd itself or no display manager; an upgrade moves
  theirs out, and where they kept none it says "unknown" (greetd then stays, with its own config).
* On a machine with more users, only the one who set the login screen up changes it with their
  installs, upgrades and removals of the wallpaper.

## Root copies only what the operator could read (M1, `install.sh`)

* Build 17 copied the screen, keyboard and Num Lock settings as root, then made the copies readable
  by everyone: a link among them to a file of root's put that file where any user reads it. Now
  the user reads and root only writes; a file the user cannot read stays out, and is named. An
  upgrade copies them again this way, so a copy build 17 made through a link goes, from the app
  copy and from the login screen's state folder; each start of the login screen takes them as
  installed now.
* The app goes over as it is, links as links, and `chmod -R` is never given a link by name (an
  upgrade gave it one: what that pointed at became readable by everyone).

## The login screen itself

* **The last login** (`last.json`) is read only on the login screen, and gives only the user and
  the session (M3). Drawing the symbols at install, as the operator, read one from `/tmp`, where
  any user can leave one.
* **A session's command** goes to greetd as one line quoted for sh (L2). greetd joins the words it
  gets with spaces and has sh run them, so an Exec line's quoted word arrived split.
* **When greetd stops the login screen** (a session due, greetd restarting), `login.sh` stops its
  KWin too, and leaves only once KWin has gone, killing a KWin that hangs after 3 s (L3). It kept
  the screens before.
* **No shared folder for the login screen's state**: where `/var/lib/syncrain-login` cannot be
  written, `login.sh` uses one of the greeter's own, never a fixed one in `/tmp`.
* **"Text login" waits** while greetd checks a password (L4): leaving then left greetd holding a
  half-made session, and the text login's first attempt failed on it.

## Smaller

* The service does not restart after status 2 (no wallpaper layer, an unknown option) or 70 (a
  native wallpaper from another build), as after 69 (no OpenGL): each started the same failure
  every 3 s, for good (M8). The NixOS and home-manager services too.
* Python 3.10 and 3.11 can import syncrain again (L1): an f-string held a backslash, which only
  3.12 and later read. A test reads every file of the app for such f-strings, and compiles the app
  with an older Python where one is installed (3.11 in the lanes' sandbox).
* `syncrain --diagnose` names what started at boot before the login screen.

## Still open from the review

* M4: `--login-screen` writes greetd's whole config and the PAM file greetd uses by default.
* M5: the box answers every PAM prompt with the password (no second factor through the box).
* M6: a missing `--background` or `--mask` file leaves a black screen that never exits.
* M7: the page and the desktop round some `--spin` values differently.
* M9: one screen that never draws stops the memory trim for all.
* L5 to L21: in the review; the hand-over's (L6, L7) go with M4 and M5.
* From this build's own review (rare): root still copies the app from the operator's folder, so
  code already running as the operator could swap a folder for a link mid-copy. The user should
  read it and root only write, as for the other files.

## Tests

* `tests/unit/test_the_login_screen_is_optional.py`: the wallpaper alone (install, autostart,
  upgrade, uninstall, `--login-screen-off` without one) leaves the login side as it was; off after
  Plasma Login, greetd itself and no display manager; build 17's record, or none; a display
  manager picked or removed since; systemctl refusing once; another user's login screen. Its
  systemctl stand-in moves the display-manager link as systemd does.
* `tests/unit/test_the_login_screen.py`: a link to a file of root's stays out; a linked app keeps
  what it points at; `last.json`; a quoted session word through sh as greetd runs it; KWin, quick
  or hanging, gone before `login.sh` is when greetd stops it.
* `tests/kwin/test_a_login_in_kwin.py`: "Text login" during a slow password check waits; the
  login still starts Plasma.
* `tests/unit/test_the_oldest_python.py`; the services' statuses read from `syncrain/app.py`.
* The fixes' tests fail on build 17's code; the wallpaper-alone ones hold every build to the
  promise. A reviewer who did not write the change ran the cases by hand too, as an ordinary user
  and as `nobody`; what it found is fixed or listed above.
* By hand in an Arch root, with real sudo, pacman's greetd and systemctl: the wallpaper alone (and
  its removal) ran nothing as root and left the login as it was. Build 17's login screen, set up
  there, copied `/etc/shadow` through a link; this build's upgrade removed that copy and moved the
  record, and `--uninstall` put the display manager back with greetd's files as packaged. With the
  display manager removed in between, greetd stayed with its own config.

## What the operator does

* `./install.sh` from `syncrain_build_18/`, as usual. The login screen follows, and its record of
  Plasma Login moves beside greetd's config; `syncrain --diagnose` shows it.

## Verification

279 passed in 571.26s (0:09:31)
