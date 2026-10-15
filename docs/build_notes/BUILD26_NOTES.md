# Build 26: the lock screen, reviewed

**Type: fix; the picture does not change** (stream `a9c058f3`). Made on 2026-10-15. Build 25 passed
its gate, then its review found what is below, so 25 was not delivered: this is the first lock
screen the operator gets. Build 25's notes say what it is.

## Fixed (`syncrain/lockscreen/`, `install.sh`)

* PAM is asked again only after a refusal's delay (3 s, or longer if PAM asks, as Plasma 6.7's own
  lock screen waits): started sooner, kscreenlocker refuses at once, and build 25's box looped,
  wiping what was typed. A password typed while PAM is not asking is kept for its next question;
  Plasma 6.8's `pamTimeout` is waited for.
* A second review: the conversation with PAM is one for all screens (`Pam.qml`), so a screen
  plugged in again while locked (monitors that sleep do) still unlocks; a question whose answer
  shows (a one-time code) is answered too; a password typed while the last was checked is kept;
  PAM's own reason (faillock's minutes) stays beside "Unlocking failed".
* PAM's own prompt ("Wachtwoord:" in Dutch) no longer replaces "Unlocking failed"; fingerprint and
  smartcard messages are shown; an account PAM lets in without a password unlocks on a click, as
  Plasma's does.
* The rain loads only after the lock screen's first frame, so the box (and KWin's keyboard focus)
  always comes first; without OpenGL (Plasma's software retry after a crash, which Qt still calls
  OpenGL, so the backend is asked too) it says so and stops asking for frames.
* The installer stops at a failed copy instead of reporting success, gives the scene the
  installer's options and sets the lock screen up before restarting the wallpaper (which then
  writes the scene with the service's own), and shows why a refresh failed; the tests no longer
  touch a real lock scene.
* Native nits: `c_strtod`'s locale is made once across threads (each screen loads at once), and a
  failed scene load frees all it took.

## Tests

* The stand-in for Plasma's locker now behaves as kscreenlocker 6.7 does: PAM asks later and in
  Dutch, a response with no question waiting is lost, a start inside the 2 s delay is refused.
  The right password typed at once after a wrong one arrives; the refusal stays said; a screen made
  anew while PAM asks still unlocks; a one-time-code question is answered.
* The real lock in KWin: PAM asks for a 2 s delay after a refusal (pam_faildelay, as Arch's
  pam_unix), and the right password typed a second after a wrong one unlocks; kscreenlocker never
  says "too soon".
* Open, in `docs/ROADMAP.md`: the frame rate while locked, a keyboard layout indicator and shared
  text between screens, Plasma's hidden lock-screen wallpaper.

## What the operator does

* `./install.sh --lock-screen` from `syncrain_build_26/` (pacman adds `cmake qt6-base
  qt6-declarative`), then log out and back in once. Lock (Meta+L) and look.
* Should it ever not unlock: Ctrl+Alt+F3, log in there, `loginctl unlock-sessions`, then
  `./install.sh --lock-screen-off`.
* `journalctl --user -b | grep syncrain` says whether the rain drew on each screen.

## Verification

395 passed in 987.73s (0:16:27)
