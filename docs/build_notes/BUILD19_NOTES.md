# Build 19: the rest of the review's fixes

**Type: fixes; the picture does not change** (stream `def5684f`). Made on 2026-10-14.

## Why

* "continue as recommended": the review of build 17's other middling findings (M4 to M7, M9) and
  the small ones worth doing now, before the previewer page the operator asked for (build 21, after
  the consolidation at 20).

## The login screen

* **greetd's own settings stay (M4)**: `--login-screen` changes only `[default_session]` in
  greetd's config (`syncrain/greetdconf.py`); a PAM service of its own, an automatic login, the
  terminal and greetd's comments stay. The wallet lines go into the PAM service that config names.
* **The greeter itself runs without the wallet lines (L5)**: a `greetd-greeter` PAM file (the
  service greetd runs its greeter under where it exists), so no wallet daemon starts for the user
  `greeter` at every boot. `--login-screen-off` takes it out again.
* A plain `./install.sh` of this build puts both right on a login screen set up by builds 16 to 18.
* **A second factor in the box (M5)**: the password answers only the first password prompt. What
  PAM asks after it (a code, a PIN, a new password) shows in the box's password field with PAM's
  own words, and what PAM says comes as it comes. A wrong code reads "Not accepted", not "Wrong
  password". "Text login" while PAM asks gives that login up first.
* **The greeter's settings, data and state start afresh at every boot (L9)**: nothing left there
  since (a KWin input method someone put there would see every password typed) counts. Its cache of
  compiled shaders stays.
* **Root reads nothing in the operator's folder**: the app goes over as a stream the operator's
  own `tar` reads and root unpacks (the rare race build 18's review left open); its files are
  root's, and nothing but files, folders and links is kept.

## The hand-over after a login (L6, L7)

* A plain `./install.sh` of a newer build makes the still frame again and nothing else: a
  wallpaper or splash chosen since stays.
* `--login-screen-off` puts back the wallpaper only where the still is, and the splash only if it
  is still syncrain's.
* A run that broke off no longer records syncrain's own splash as the one to go back to.

## The wallpaper

* **An option it cannot use ends at once (M6)**: a number that is not one (`--spin nan`), one out
  of range, a `--background` or `--mask` that is not there: said, status 2. A picture or font it
  cannot use once drawing starts: said, status 78. No more black window that runs on; the
  services do not restart on 78 either.
* **A symbols file it cannot draw** falls back to the theme's symbols, said (L13).
* **One screen that never draws** (off, or covered where the compositor stops asking) no longer
  stops the memory trim for the others (M9).
* **KWin's covered-screen watch starts after the first frame (L14)**: a session bus slow to answer
  no longer keeps the wallpaper off the screens.
* **The GTK host rebuilds once per burst of screen changes (L10)**, even while frames keep it busy.
* `--screenshot` and `--record` that cannot save end with status 1 (L15).
* The channel is named as the page names it: spaces around it are no part of it (L19).
* NixOS: the service finds `fc-list`, so symbols not shipped are drawn there too (L16).

## The page

* The logo turns as on the desktop for every `--spin`: halves are rounded to the even neighbour
  in both (M7). A test compares every period from 0.5 s to 2 h.
* `?theme=constructor` and the like give NixOS snow (L17); a lost WebGL context reloads the page;
  with `hud=0` it never pauses for reduced motion, as there is no Play button (L18).

## Still open

* L8 (the wallet after greetd's text login), L11 and L12 (the picture at `--scale` below 0.4 and on
  screens under about 900 px wide), L20 (what the stream id covers), L21 (a `flake.lock`). L11,
  L12 and L20 go with the previewer, which needs the page and the desktop to agree everywhere.
* A font file name that is not UTF-8 makes a symbols file fall back to the theme's symbols; the fix
  is in `syncrain/glyphs.py`, a stream file, so it waits for a build that changes the stream.

## Tests

* `tests/unit/test_the_greetd_config.py`; greetd's own settings and a second-factor PAM service
  through `--login-screen` and back (`tests/unit/test_the_login_screen_is_optional.py`).
* A second factor with the greetd stand-in, alone and in the box in headless KWin; "Text login"
  while PAM asks.
* `tests/unit/test_the_options.py`; a picture that is no picture under Xvfb ends with 78.
* A screen powered off in headless Sway: trims go on. The page's cycles per hour against Python's.
* The hand-over keeps a wallpaper and splash chosen since.
* By hand in the Arch root: greetd's packaged config and PAM files changed only where they should
  and back as packaged; the app's files root's.

## What the operator does

* `./install.sh` from `syncrain_build_19/`, as usual. Nothing changes on screen; after that, a
  wallpaper or splash picked in Plasma stays picked.

## Verification

319 passed in 670.95s (0:11:10)
