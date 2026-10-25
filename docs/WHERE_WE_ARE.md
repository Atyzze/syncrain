# Where we are, at build 48

The project on one page. Detail: `docs/agent/HANDOFF.md`.

## What syncrain is

syncrain backdrop: live code rain for the whole session (desktop, login screen, lock screen, a web
page, videos) that never repeats. Every frame comes from the clock and a channel name, so everyone
on a channel sees the same rain. Linux (Wayland, X11) and the browser; NixOS is the base. Boot stays
plain text by design: the text means the machine is not up yet, the rain that it is.

## Where it stands

* **Your desktop** (KDE Plasma, RTX 5090, two screens): a small C program, 123 MiB and 0.9% of a
  core at 30 fps, about 11 W; covered screens can be left undrawn (0 W, `pause_under`, off in your
  file), every frame lands on the refresh, freed memory goes back every five minutes, and what
  NVIDIA's 615 driver keeps for each frame goes back too (build 48: OpenGL made anew when the heap
  has grown 32 MiB, without a gap on screen).
* **Your config.json is the default** (build 47): in every release, beside `install.sh`, which
  reads it (and writes one with the defaults if missing); the default look is made from it. NixOS
  and Matrix are presets; your redrawn logo is a choice.
* **Try every setting on the page**: `index.html`, Settings, move anything, Save config.json into
  the folder, then `./install.sh`. Your desktop draws what the page showed.
* **Picture options**: colours, how many at once and their cycle, background, any picture as the
  logo with one colour over it, glow, bloom, speed, density, snow, your own symbol sets, hidden
  words and sentences (up to 30 characters).
* **The login screen** (optional, working on your desktop): `./install.sh --login-screen`; greetd,
  the rain and a box on every screen; `--login-screen-off` takes out only what it put in (build 36).
* **The lock screen** (optional, build 27): `./install.sh --lock-screen`, then log out and in once;
  the rain stays live at 30 fps (build 47: the rest to 10 fps is a setting, off), your box comes up
  on a key or a moved mouse and is the same on every screen.
  In use on your desktop since build 26. Build 34 fixed what the review found: a screen coming
  back after every screen went, a second factor, a prompt that wants only Enter, the hidden eye.
* **Videos** (build 29): `syncrain --video rain.mp4` or the page's Video section; every frame as
  drawn, no crossfade (build 47: it blurred the first seconds).
* **Four families** (build 31): `./install.sh` on Arch, Debian, Fedora and openSUSE, each installed
  for real in a root of its own; anything else gets the packages named, or its AI agent.
* **NixOS** (build 32): the module gives the wallpaper, the login screen and the lock screen
  (`loginScreen.enable`, `lockScreen.enable`); its login screen runs in a headless KWin here, but
  no NixOS machine has booted it yet.
* **Your NixOS flavour** (build 33): `nix flake init -t github:Atyzze/syncrain` over your own
  `/etc/nixos`, kept whole, `nixos-rebuild switch`: Plasma 6 with the rain as wallpaper, login and lock screen.
  The whole system builds here; no machine has booted it yet.
* **On GitHub**: github.com/Atyzze/syncrain, every build up to 48.

## What comes next

* **Next**: your record after a day on build 48 (`syncrain --diagnose`: the "OpenGL made anew"
  lines and what each gave back); then the roadmap's open items that can be done here.
* **Build 50**: the next consolidation (every number ending in 0).

## The decision in front of you

None open: the defaults are the operator's config.json (30 fps, no pausing, no lock screen rest).

## Words

* **build**: one numbered archive. **channel**: the name a stream shares. **stream id**: names what
  decides the picture. **consolidation**: a build with no new behaviour, every number ending in 0.
* **backdrop**: everything syncrain draws behind you: wallpaper, login screen, lock screen.
