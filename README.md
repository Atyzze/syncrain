# syncrain backdrop

Live code rain for your whole Linux session: your desktop wallpaper, your login screen, your lock
screen, a web page and, when you want one, a video. It never repeats and stays in sync across
machines: every frame is worked out from the UTC clock and a channel name, so everyone on the same
channel sees the same rain at the same moment. Every colour, symbol, word and motion is yours to
tune, from a page that shows the result as you go.

It runs on Wayland and X11, KDE Plasma included (GNOME only in a window or the page). NixOS is the
base it is built for; the installer covers the four big families: Arch, Debian, Fedora and openSUSE.

<p align="center">
  <img src="docs/images/syncrain.jpg" width="49%" alt="The default look: katakana, digits and Egyptian hieroglyphs falling in columns over black with snow, the columns in a rainbow wave across the screen, the NixOS snowflake in rainbow colours in the middle">
  <img src="docs/images/nixos.jpg" width="49%" alt="The nixos preset: pale blue characters and hieroglyphs falling over dark blue, with snowflakes and the NixOS snowflake in rainbow colours in the middle">
</p>
<p align="center"><sub>Left, the default; right, the nixos preset. Channel <code>public</code> at 2026-10-07
00:00:07 UTC: <code>syncrain --window --time 1791331207</code> draws that moment on any machine.</sub></p>

## What you get

* **The default look** (the `syncrain` preset): katakana, digits and hieroglyphs with white-hot
  tails, 64 colours at once in a rainbow wave across the screen that turns once every 440 s, the
  NixOS snowflake in the middle in its own turning rainbow, snow, on black. Hidden words (`AI`,
  `NEURAL`, `MATRIX` and more) fall now and then; whole sentences can too (`WAKE UP NEO`, up to 30 characters).
* **Two more presets**: `nixos` (ice blue, snow) and `matrix` (classic green). Every colour,
  speed, the logo (or a picture of your own), the symbols and the words can be changed.
* **Your desktop wallpaper**: a small native program (under 1% of a core, and about 11 W at 30 fps
  on two screens of the operator's RTX 5090, measured before the default had snow); on KDE Plasma a
  screen under a full-screen or maximized window is not drawn at all.
* **Optional**: the rain as your login screen (greetd, with a login box on every screen) and as
  KDE Plasma's lock screen (the rain stays live; the box appears when you move the mouse or press
  a key, and is the same on every screen). Without asking for them, the installer leaves both alone.
* **The web page** (`index.html`): the same rain in a browser, and a Settings panel to try every
  option live and save it as `config.json` for the desktop.
* **A video of your look**: a seamless loop as MP4, WebM or GIF, for a phone, a TV, a video
  wallpaper app or anywhere the live rain cannot run (whether playing one costs fewer watts than
  the live rain is not measured yet). The live rain stays the default: it never repeats and stays
  in sync, which a video cannot.

## Install

```sh
git clone https://github.com/Atyzze/syncrain && cd syncrain
./install.sh                 # the system's packages (asks for sudo once), then everything in ~/.local
syncrain --window            # try it in a window
./install.sh --autostart     # the wallpaper, started with every login
```

`install.sh` knows its family and asks its package tool:

| Family | Releases | Tested |
| --- | --- | --- |
| Arch (pacman) | Arch, CachyOS, EndeavourOS, Manjaro, Garuda | the operator's CachyOS desktop (every build up to 30), and an Arch root |
| Debian (apt) | Debian 13, Ubuntu 26.04, Mint, Pop!_OS | installed in a Debian 13 root: the same frame, to the pixel |
| Fedora (dnf) | Fedora 43, 44 | installed in a Fedora 44 root |
| openSUSE (zypper) | Tumbleweed | installed in a Tumbleweed root |

Each root ran the installer for real, drew the same frame as the others, built the lock screen,
and set up and undid the login screen. Only CachyOS has booted into them so far: on the others,
tell us how it goes. Ubuntu 24.04 and openSUSE
Leap 16.0 have no gtk4-layer-shell (the native wallpaper draws anyway) and no Qt new enough for the
lock screen.

**Any other Linux**: `./install.sh` names the packages to install by hand, then `./install.sh
--no-deps`. Or hand this repository to your AI agent and let it adapt `install.sh` to your system:
everything it needs to know is in these documents.

A release archive (`SYNCRAIN<N>.tar.zst`) works the same: unpack it and run `./install.sh` from the
folder. Running a newer build's `./install.sh` upgrades in place and restarts the wallpaper.

**Make it yours**: open `index.html` in a browser, press Settings, change anything and watch the
rain follow, then Save config.json and run `./install.sh --config config.json`. The desktop draws
exactly what the page showed.

**Login and lock screen** (both optional, both undone exactly):

```sh
./install.sh --login-screen      # the rain and a login box at boot (greetd); --login-screen-off undoes it
./install.sh --lock-screen       # KDE Plasma 6: the rain behind your lock screen box; --lock-screen-off undoes it
```

After `--lock-screen`, log out and back in once. Should the lock screen ever not unlock:
Ctrl+Alt+F3, log in, `loginctl unlock-sessions`, then `./install.sh --lock-screen-off`.

**Make a video**: `syncrain --video rain.mp4` (30 s at 1920x1080 with your settings, ending
where it begins; needs ffmpeg). `--seconds 60 --size 3840x2160 --video-fps 60` for more, `rain.gif`
for a GIF (10 s at 640x360 and 15 fps: a GIF of rain is large), `--loop off` for one that does not
loop. In the browser, the page's Settings has a **Video** section that saves the same as WebM.

**Why boot stays plain text**: syncrain never touches the bootloader, the initramfs or a boot
splash. The plain text while the machine starts says it is not up yet; the moment the rain appears,
on the login screen or the desktop, it is. That clear cut is by design.

**When it does not draw**: `syncrain --diagnose` says what this machine offers and why.
**Remove it**: `./install.sh --uninstall` (the system's packages stay).

**Elsewhere**: on NixOS, `nix run github:Atyzze/syncrain -- --window`, and the flake has NixOS and
home-manager modules for the wallpaper (the login and lock screens there are the next steps, see
[`docs/ROADMAP.md`](docs/ROADMAP.md)). In a browser, `index.html` alone; as a web wallpaper its URL takes the options
(`hud=0` hides the controls). Every option, other desktops, power and recipes:
[`docs/OPERATIONS.md`](docs/OPERATIONS.md).

## Working on syncrain

Made in numbered builds by AI agents for one person, the operator ("they"). Read in this order:

1. [`docs/WHERE_WE_ARE.md`](docs/WHERE_WE_ARE.md): the project on one page
2. [`docs/agent/HANDOFF.md`](docs/agent/HANDOFF.md): what is true now
3. [`docs/agent/NEXT_BUILD.md`](docs/agent/NEXT_BUILD.md): the next build, and how to release one
4. [`docs/agent/WORKING_WITH_THE_OPERATOR.md`](docs/agent/WORKING_WITH_THE_OPERATOR.md)
5. [`docs/agent/ENVIRONMENT.md`](docs/agent/ENVIRONMENT.md): the sandbox and the test lanes
6. [`docs/agent/TARGET_ENVIRONMENT.md`](docs/agent/TARGET_ENVIRONMENT.md): the operator's machine
7. [`docs/ROADMAP.md`](docs/ROADMAP.md): questions, plans, cadence, constraints
8. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): how it works
9. [`docs/LESSONS.md`](docs/LESSONS.md), [`docs/HISTORY.md`](docs/HISTORY.md), [`docs/build_notes/`](docs/build_notes/)

```sh
python3 tools/test_suite.py --lane quick     # unit and contract lanes, seconds
python3 tools/test_suite.py                  # every lane this machine can run
```

Lanes: unit, contract, native, render (Xvfb), wayland (headless Sway), kwin (headless KWin 6),
browser (Chromium), nix, lockscreen (Plasma's locker in a headless KWin). What each needs:
`docs/agent/ENVIRONMENT.md`.

**What costs you if you get it wrong**

* Only `tools/package_release.py` makes an archive and writes `BUILD_NUMBER`. No version strings.
* The stream is frozen: a change to a shader, a preset, the atlas, a logo, `syncrain/engine.py` or
  `syncrain/glyphs.py` changes every machine's picture; `tools/stream_freeze.py --write` re-takes
  it, on purpose only.
* Three hosts draw the same frame: the page (JavaScript), the GTK host (Python) and the native
  wallpaper (C). Change one, change all; the lanes compare them.
* Never ask GTK for an OpenGL version (build 2 drew nothing on NVIDIA).
* systemd unescapes inside single quotes; every service line goes through one quoting function.

### Layout

    syncrain/          app.py (options, GTK host), native.py (starts the native wallpaper), renderer.py,
                       gl.py, pacing.py, hidden.py (KWin), engine.py, glyphs.py (symbols), build.py,
                       diagnose.py, bench.py, power.py, cover.py, logo.py, video.py, data/ (shaders, presets, atlas, logos and
                       syncrain's logo drawing)
    syncrain/          the login screen: greeter.py (the box), greetd.py, greetdconf.py, handover.py,
                       login/ (greetd's command)
    syncrain/native/   the native wallpaper in C
    syncrain/lockscreen/  the lock screen: the QML item drawing the native passes, and the shell package
    nix/               package, web bundle, NixOS and home-manager modules and their options
    tools/             package_release.py, test_suite.py, stream_freeze.py, build_web.py, build_assets.py, build_logo.py,
                       prepare_environment.sh
    tests/             one folder per lane; fixtures/stream_freeze.json
    index.html         the web page: open it, try every setting, save them (its data filled in by tools/build_web.py)
    install.sh         the installer: Arch, Debian, Fedora and openSUSE

## Licence

MIT ([`LICENSE`](LICENSE)). The NixOS snowflake is CC BY 4.0; credits in
[`docs/OPERATIONS.md`](docs/OPERATIONS.md).
