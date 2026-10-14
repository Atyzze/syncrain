# Where we are, at build 18

The project on one page. Detail: `docs/agent/HANDOFF.md`.

## What syncrain is

A wallpaper of falling code that never repeats. Every frame comes from the clock and a channel
name, so everyone on a channel sees the same rain. Linux (Wayland, X11) and the browser.

## Where it stands

* **Runs on your desktop** (KDE Plasma, RTX 5090, two screens) as a small C program: 123 MiB at
  start and 0.9% of a core at 30 fps (Python and GTK took 205 MiB and 4.7%).
* **Power**: about 11 W at 30 fps; the watts follow the frames, not the language.
* **Covered screens are not drawn** (0 W behind a full-screen window), and every frame lands on
  the refresh.
* **Memory**: build 11 grew from 110 to 225 MiB in 18 h, slowing, then fell to 170 by itself: freed
  memory not yet handed back, not a leak. Build 12 hands it back every five minutes and keeps a
  record; `syncrain --diagnose` shows it.
* **Your picture options** (build 12): `--glow`, `--bloom`, `--bg-gain` (darker), `--speed`,
  `--density`, `--snow off`, `--hieroglyphs` (0.15 by default).
* **The glow flare-up**: not in the frames syncrain computes (two hours checked). Note the time
  when you see it, and that moment can be drawn again.
* **The Plasma wallpaper** (builds 13 and 14) broke on your desktop; build 15 removes it.
* **Your own symbols** (build 15): `syncrain --write-glyphs`, then edit
  `~/.config/syncrain/glyphs.json`: sets of characters (any language, your favourites), each with
  a weight or a share.
* **The login screen** (build 16, working on your desktop): `./install.sh --login-screen`; greetd,
  the rain and a login box on every screen (17), then Plasma, its splash and wallpaper a still of
  the rain (17). A failure falls back to a text login. Optional: without it the installer never
  touches your login, and `--login-screen-off` puts back what started at boot before (18).
* **A review of build 17**: build 18 fixes eight of its findings; five middling ones are open.
* **Why the Plasma wallpaper went white**: Dutch number format inside Plasma; fixed in build 16.
* **On GitHub**: github.com/Atyzze/syncrain, every build up to 18.

## What comes next

* **Build 19**: what you find in 18; then the rest of the review or the boot splash (a still frame
  of the rain before the login), your pick.
* **Then**: a NixOS image.

## The decision in front of you

1. **Default frame rate**: 30 fps (+11.9 W, now), 20 (+7.3 W) or 15 (+3.5 W). Below about 21 fps
   the fastest streams skip a row now and then. Recommended: try `syncrain --fps 20` for a day.
2. **Pause behind maximized windows too, or only full-screen ones?** Both now; behind a see-through
   window the rain then stands still. Recommended: both.
3. **Build 19: the rest of the review, or the boot splash first?** Recommended: the review (it
   decides whether the login screen works on machines set up unlike yours).

## Words

* **build**: one numbered archive. **channel**: the name a stream shares. **stream id**: names what
  decides the picture. **consolidation**: a build with no new behaviour, every number ending in 0.
