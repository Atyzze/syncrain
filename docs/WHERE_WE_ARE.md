# Where we are, at build 25

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
* **Memory**: freed memory goes back every five minutes, with a record; `syncrain --diagnose`
  shows it.
* **Your picture options**: `--glow`, `--bloom`, `--bg-gain` (darker), `--speed`, `--density`,
  `--snow off`, `--hieroglyphs` (0.15 by default).
* **The glow flare-up**: not in the frames syncrain computes (two hours checked). Note the time
  when you see it, and that moment can be drawn again.
* **Your own symbols**: `syncrain --write-glyphs`, then edit `~/.config/syncrain/glyphs.json`: sets
  of characters (any language, your favourites), each with a weight or a share.
* **The login screen** (working on your desktop): `./install.sh --login-screen`; greetd, the rain
  and a login box on every screen (a second factor asked there too), then Plasma, its splash and
  wallpaper a still of the rain. A failure falls back to a text login. Optional: without it the
  installer never touches your login, and `--login-screen-off` puts back what started at boot.
* **The lock screen** (build 25, optional): `./install.sh --lock-screen`, then log out and in once;
  Plasma's locker shows the rain and your box. `--lock-screen-off` gives Plasma's back.
* **Try every setting on the page**: open `index.html` (next to `install.sh`, or the live page),
  press Settings, move anything, watch the rain change, Save config.json, then `./install.sh
  --config config.json`. Your desktop draws what the page showed.
* **Your own look** (build 22): the rain's colours, how many at once (each column its own, by the
  channel or as a wave), a colour cycle like an RGB keyboard's, the background, any picture as the
  logo, the hidden words. Presets to start from: **Syncrain** (your look, the default: your settings file of
  2026-10-14 22:33, build 24), NixOS and Matrix; your redrawn logo stays a choice (`--logo syncrain`).
  One colour over any logo (build 23).
* **A review of build 17**: builds 18 and 19 fixed what matters now; a few small items are open
  (`docs/ROADMAP.md`, "Open items").
* **On GitHub**: github.com/Atyzze/syncrain, every build up to 25.

## What comes next

* **Next**: the boot splash through the LUKS prompt (26), then a NixOS image.
* **Build 30**: the next consolidation (every number ending in 0).

## The decision in front of you

1. **Default frame rate**: 30 fps (+11.9 W, now), 20 (+7.3 W) or 15 (+3.5 W). Below about 21 fps
   the fastest streams skip a row now and then. Recommended: try `syncrain --fps 20` for a day.
2. **Pause behind maximized windows too, or only full-screen ones?** Both now; behind a see-through
   window the rain then stands still. Recommended: both.

## Words

* **build**: one numbered archive. **channel**: the name a stream shares. **stream id**: names what
  decides the picture. **consolidation**: a build with no new behaviour, every number ending in 0.
