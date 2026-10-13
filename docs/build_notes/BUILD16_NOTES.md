# Build 16: the rain as the login screen

**Type: feature; the picture does not change** (stream `def5684f`). Made on 2026-10-13.

## The login screen (`install.sh --login-screen`)

* greetd replaces SDDM at boot. greetd checks the password (PAM) and starts Plasma; syncrain only
  draws and asks.
* What shows: KWin on the screens, the rain on every one, and a small box below the logo: user,
  password, session (Plasma by default), Restart, Shut down. The last user and session are kept.
* The rain uses your wallpaper's options and symbols file, your screen layout, keyboard layout and
  Num Lock. KDE's wallet still opens with the login, as under SDDM.
* If the box never logs anyone in (KWin or the box fails, or no box within a minute), greetd's
  text login asks instead and starts Plasma; so a broken login screen still lets you in. The box's
  "Text login" goes there too.
* Back to SDDM: `./install.sh --login-screen-off`, or from a text console (Ctrl+Alt+F3)
  `sudo systemctl enable --force sddm && sudo reboot`. SDDM stays installed.
* `syncrain --diagnose` says which login screen starts at boot and what its last two starts logged
  (`/var/lib/syncrain-login/login.log`).
* A newer build's `./install.sh` updates the login screen too.

## Inside

* `syncrain/login/login.sh` (greetd's command, user `greeter`), `session.sh` (in KWin),
  `syncrain/greeter.py` (the box, GTK 4 on the overlay layer), `syncrain/greetd.py` (greetd's IPC).
* The app is copied to `/usr/local/lib/syncrain`, where the greeter user can read it, and swapped
  in whole; if it is ever missing, greetd's config starts the text login itself.
* Reviewed by an agent that did not write it: the watchdog, Text login, the swap, Restart and Shut
  down saying why they failed, and the box on the screen with the pointer came from it.

## Your Plasma wallpaper's white screen, explained

* With a Dutch locale, the C library reads `0x1.333p-3` as 1 (the comma is the decimal sign there).
  Qt sets the locale, so inside Plasma every option came out 1 or 0: all white, all hieroglyphs.
* The native wallpaper now reads numbers in the C locale whatever the machine's;
  `--selftest number` and a test under `nl_NL` hold it.

## Tests

* The whole login in headless KWin, two screens: the rain draws, a wrong password is said, the
  right one asks greetd (a stand-in) to start Plasma with SDDM's environment
  (`tests/kwin/test_a_login_in_kwin.py`).
* greetd's conversation, the sessions offered, the fall back to the text login, and the installer
  on and off against stubs (`tests/unit/test_the_login_screen.py`).
* By hand in an Arch root: the real greetd package and its greeter user, `install.sh
  --login-screen` and `--login-screen-off` with real systemctl, the login as `greeter`.
* Not here: greetd on a real console, KWin on a graphics card. Your machine is the first.

## What the operator does

* `./install.sh --login-screen` from `syncrain_build_16/`, then reboot.
* If anything looks wrong: `syncrain --diagnose` after logging in.

## Verification

234 passed in 614.62s (0:10:14)
