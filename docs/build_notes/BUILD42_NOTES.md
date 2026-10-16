# Build 42: the lock screen rests when nobody is there, and names the keyboard layout

**Type: feature; the picture does not change** (stream `1ad0a2dd`). Made on 2026-10-16, as the
operator asked after build 41: the roadmap's open items next, the most useful first (and no installer
image for now). This one takes the lock screen's three.

## The lock screen

* **It rests**: after five minutes without a key or a moved pointer the rain draws 10 frames a
  second instead of 30, and the first key or move (Escape too) brings 30 back. A locked screen nobody looks at
  cost every frame in power, and on NVIDIA in memory in KWin's greeter.
* **The keyboard layout**: with more than one layout set up, the box names the one in use under
  Unlock, from Plasma's own keyboard layout module as Plasma's lock screen asks it; a click takes
  the next one, on every screen. A password typed in another layout than the one thought is the
  commonest wrong one. Where the module is missing the box just does not say it.
* **Plasma's unseen wallpaper**: Plasma's locker loaded the lock-screen wallpaper `kscreenlockerrc`
  names (an image, decoded at the screen's size) under syncrain's screen, where nothing shows it.
  With the lock screen, the next install (or `--lock-screen`) names Plasma's plain colour there, in
  black, once: a wallpaper chosen in Plasma's settings afterwards stays. `--lock-screen-off` and
  `--uninstall` put back what was named before (even after an earlier way back stopped half way).

## Tests

* The two-screen lock screen test (real key and pointer events) has a stand-in for Plasma's keyboard
  layout module: one layout names none; two name the one in use on both screens, and a click on
  either takes the next. The rain's rate drops after the rest time and comes back with a key.
* The installer's lock screen tests: the wallpaper line set (also by a plain install over a lock
  screen from before), kept on a second run, put back, deleted when none was named, left as the
  operator changed it since, and put back by an uninstall after a way back that stopped half way.

## The review of this build

An agent that did not write it read it: nothing critical. Its findings (an upgrade that never got
the wallpaper line, the blue of Plasma's plain colour, Escape left at the rest rate, a record an
uninstall missed, the answered questions still asked in two documents) are fixed above.

## The roadmap

* The two questions asked on 2026-10-07 are answered by the default the operator chose in build 35
  (30 fps; pausing behind maximized windows too). The planned builds are now 42 to 46, the open
  items that can be done here; the installer image is not scheduled.

## What the operator does

* `./install.sh` as usual. The lock screen picks the change up at its next lock.

## Verification

552 passed in 1405.76s (0:23:25)
