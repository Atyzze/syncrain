# Build 34: the lock screen answers PAM whatever happens to the screens

**Type: fix; the picture does not change** (stream `822ea58a`). Made on 2026-10-15, the first of
the builds that fix what the review of build 33 found, the most critical first. This one takes the
lock screen's items: 1, 3, 27, 28, 30 and 56.

## The lock screen

* **Every screen gone and one back (1)**: kscreenlocker 6.7 frees its QML engine when the last
  screen goes, so the screen that comes back starts a new `Pam.qml` while PAM's question may still
  be open. The new one reads where PAM is from the authenticator (`hadPrompt`, `state`, `busy`,
  `prompt`, `promptForSecret`): an open question is answered and its words shown; while PAM still
  checks an answer nothing is sent (6.7 would hand it to the next question, a second factor
  included); just after a refusal it waits out the delay; a yes said while no screen was there
  quits at once. Before, Enter only kept the password and nothing reached PAM again.
* **A password goes only where it was typed for (3)**: a password typed while PAM was still
  checking the last one waits for the next conversation and goes to its first secret question,
  and only when this lock screen started that conversation. A second factor (a one-time code, a
  Duo push) never gets it; the person types the code themselves.
* **A second question is said**: a secret question after an answer (a second factor) shows PAM's
  own words, so the field says what it wants now.
* **A question that wants only Enter (27)**: a visible prompt (pam_u2f's "touch the key, then press
  Enter", a one-time code) takes an empty answer and shows what is typed in clear. A password typed
  before such a question came is cleared rather than shown, and an Enter that only wakes the
  screen answers nothing (an empty answer to a one-time code counts as a refusal).
* **Empty words are no question**: kscreenlocker clears a prompt's words when a conversation ends
  (and 6.8 says them empty as it starts); that no longer counts as PAM asking.
* **Plasma 6.8's delay**: the lock screen read a `pamTimeout` that no kscreenlocker has; it reads
  `inPasswordDelay` now, and a password kept through that delay still goes only to the question it
  was typed for.
* **The hidden box takes no clicks (28)**: the eye and Unlock work only while the box is up; a
  press on the hidden box brings it up. Before, a stray click on the invisible eye showed the
  password on every screen.
* **A long delay counts once (30)**: after PAM asks for a long delay (faillock, say), the next
  refusal waits the usual 3 s again.
* **OpenGL state put back (56)**: the rain's texture uploads leave Qt's context with the unpack
  alignment it had (4), right after each upload rather than once at the end of setup.

## Tests

* The lock screen lane's stand-in greeter now keeps an answer given while PAM checks the last one
  for the next question, as 6.7's worker does, and has six new cases: a screen that comes back to a
  question already asked, after a yes, while PAM checks the password of a two-factor stack, and
  just after a refusal; a second factor (the pending password is not sent to it, its words are
  shown); a visible prompt answered with Enter alone.
* The two-screens test: the hidden eye takes no click, a long delay counts once, Enter on the
  hidden box answers nothing, a visible question clears a typed password, empty words are no
  question, and a new engine meets PAM where it is (17 cases).
* An agent that did not write the change reviewed it against kscreenlocker 6.7.5's and 6.8.0's
  sources; what it found is in this build (the busy check, the words shown, Enter, the cleared
  password, empty words, the delay's name).

## What the operator does

* `./install.sh` as usual: an installed lock screen comes along (the next lock uses it). Nothing
  else changes.

## Verification

483 passed in 1156.62s (0:19:16)
