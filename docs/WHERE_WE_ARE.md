# Where we are, at build 31

The project on one page. Detail: `docs/agent/HANDOFF.md`.

## What syncrain is

syncrain backdrop: live code rain for the whole session (desktop, login screen, lock screen, a web
page, videos) that never repeats. Every frame comes from the clock and a channel name, so everyone
on a channel sees the same rain. Linux (Wayland, X11) and the browser; NixOS is the base. Boot stays
plain text by design: the text means the machine is not up yet, the rain that it is.

## Where it stands

* **Your desktop** (KDE Plasma, RTX 5090, two screens): a small C program, 123 MiB and 0.9% of a
  core at 30 fps, about 11 W; covered screens are not drawn (0 W), every frame lands on the
  refresh, freed memory goes back every five minutes.
* **Your look is the default** (builds 24 and 28): your settings file of 2026-10-15 12:49, snow and
  the NixOS logo at 0.44 included. NixOS and Matrix are presets; your redrawn logo is a choice.
* **Try every setting on the page**: `index.html`, Settings, move anything, Save config.json, then
  `./install.sh --config config.json`. Your desktop draws what the page showed.
* **Picture options**: colours, how many at once and their cycle, background, any picture as the
  logo with one colour over it, glow, bloom, speed, density, snow, your own symbol sets, hidden
  words and sentences (up to 30 characters).
* **The login screen** (optional, working on your desktop): `./install.sh --login-screen`; greetd,
  the rain and a box on every screen; `--login-screen-off` puts back what was there.
* **The lock screen** (optional, build 27): `./install.sh --lock-screen`, then log out and in once;
  the rain stays live, your box comes up on a key or a moved mouse and is the same on every screen.
  Not yet seen on your machine.
* **Videos** (build 29): `syncrain --video rain.mp4` or the page's Video section, a seamless loop.
* **Four families** (build 31): `./install.sh` on Arch, Debian, Fedora and openSUSE, each installed
  for real in a root of its own; anything else gets the packages named, or its AI agent.
* **On GitHub**: github.com/Atyzze/syncrain, every build up to 31.

## What comes next

* **Next**: a NixOS image with the wallpaper, login screen and lock screen, the base the others
  follow; or what you find on the lock screen.
* **Build 40**: the next consolidation (every number ending in 0).

## The decision in front of you

1. **Default frame rate**: 30 fps (+11.9 W, now), 20 (+7.3 W) or 15 (+3.5 W). Below about 21 fps
   the fastest streams skip a row now and then. Recommended: try `syncrain --fps 20` for a day.
2. **Pause behind maximized windows too, or only full-screen ones?** Both now; behind a see-through
   window the rain then stands still. Recommended: both.

## Words

* **build**: one numbered archive. **channel**: the name a stream shares. **stream id**: names what
  decides the picture. **consolidation**: a build with no new behaviour, every number ending in 0.
* **backdrop**: everything syncrain draws behind you: wallpaper, login screen, lock screen.
