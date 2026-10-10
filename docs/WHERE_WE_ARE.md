# Where we are, at build 12

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
* **On GitHub**: github.com/Atyzze/syncrain, one commit per build.

## What comes next

* **Build 13**: your answers below, and the flare-up if you catch its time.
* **Then**: the KDE plugin if you want it; a NixOS image.

## The decision in front of you

1. **Default frame rate**: 30 fps (+11.9 W, now), 20 (+7.3 W) or 15 (+3.5 W). Below about 21 fps
   the fastest streams skip a row now and then. Recommended: try `syncrain --fps 20` for a day.
2. **Pause behind maximized windows too, or only full-screen ones?** Both now; behind a see-through
   window the rain then stands still. Recommended: both.
3. **Desktop icons on KDE** (syncrain covers them): (a) keep; (b) a Plasma wallpaper plugin, behind
   the icons; (c) the web page in a web-wallpaper plugin. Recommended: (b), with (c) meanwhile.

## Words

* **build**: one numbered archive. **channel**: the name a stream shares. **stream id**: names what
  decides the picture. **consolidation**: a build with no new behaviour, every number ending in 0.
