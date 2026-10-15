# Build 27: the lock screen's box comes with you, the same on every screen

**Type: feature; the picture does not change** (stream `a9c058f3`). Made on 2026-10-15, as the
operator asked at 10:45: "hide the login box unless there has been recent key input or mouse
movement, hide it after a minute of inactivity again, and make sure that when typing in any box,
all login boxes update, so it never matters which screen is visible".

## The box (`syncrain/lockscreen/package/`)

* Away when the lock comes up: only the rain, and no pointer. A key or a moved mouse brings it up
  (a quarter-second fade); the first key goes into the field, not lost. KWin's own placing of the
  pointer as the lock appears does not count, as in Plasma's lock screen.
* After a minute without a key or a move it goes again and forgets what was typed, so a half-typed
  password does not wait on the screen; Escape sends it away at once. A refused password brings it
  up, with the reason.
* One box for every screen (`Shared.qml`, beside `Pam.qml`): what is typed, the eye and whether it
  shows are the same on all of them; type on either, Enter on either sends it once.
* Unlocked, the desktop is as it was: none of this is kept.

## From the review (an agent that did not write it)

* Sent away (Escape, the idle minute, a suspend), the box also forgets a password typed but not
  yet sent, which PAM would otherwise have been given at its next question. Before a suspend the
  box goes, as Plasma's own lock screen clears its field (the idle minute stops while asleep).
* A move over the box counts as one (a HoverHandler sees its children's hovers), only a move of
  more than a few pixels does (Qt reports a still pointer again when what is under it changes).
  The pointer is hidden by the same handler while the box is away; whether the field's own I-beam
  shows over the hidden box on a real screen is not yet seen.
* No password needed (a reader said yes), or a reader's own words: the box comes up to say so.
* Left as they are: the eye, on, shows the password on every screen (as asked: they all show the
  same); with an input method on, typing on one screen can move the other's cursor.

## Tests

* Two screens of the lock screen side by side, driven with real key and pointer events (Qt's
  qmltestrunner, in the `lockscreen` lane): away at first, the first pointer move ignored, a move or
  a key brings it up, the first key lands in the field, text and eye the same on both screens,
  typing goes on from either, input keeps it up, the idle time takes it away and clears both,
  Escape too, Enter sends once and clears both; a nudge does not count, a move over the box does;
  Escape and the idle time forget a password PAM has not yet asked for; "no password needed"
  brings the box up.
* The real lock in KWin still unlocks by typing, now into a box that is away when typing starts.

## What the operator does

* `./install.sh --lock-screen` from `syncrain_build_27/` (or plain `./install.sh` if build 26's lock
  screen is in: every install keeps it current), then log out and back in once. Lock (Meta+L), wait,
  then move the mouse or press a key.
* Should it ever not unlock: Ctrl+Alt+F3, log in there, `loginctl unlock-sessions`, then
  `./install.sh --lock-screen-off`.

## Verification

396 passed in 901.10s (0:15:01)
