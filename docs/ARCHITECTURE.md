# Architecture

How a frame is made and put on screen. Options and recipes: `docs/OPERATIONS.md`.

## The promise

A frame is a pure function of the UTC clock and a channel name: nothing stored, nothing loops.
Machines with synced clocks and the same stream id draw the same frame.

## Clock and channel (`syncrain/engine.py`)

* Time: whole seconds since 2024-01-01 UTC (32 bits) plus the fraction, on a millisecond grid.
* Channel: the FNV-1a hash of its name.
* All randomness is integer hashing (`lowbias32`), bit-exact on every GPU.
* Anything periodic runs whole cycles per hour, so nothing jumps when the hour restarts.

## Six passes (`syncrain/data/shaders/`)

1. **state**: 64 columns of cells; each column gets one spawn chance a second, and every drop's
   speed, trail and glyphs come from hashes of (channel, column, second).
2. **field**: a 5x5 blur of the state, for glow.
3. **glyphs**: the characters at a quarter of the resolution, the bloom source.
4. **blur**, horizontal.
5. **blur**, vertical.
6. **composite**: background, snow, glyphs, bloom, logo, front snow.

Data: `syncrain/data/themes.json`, `syncrain/data/glyphs.png` (489 shipped glyphs: code,
katakana, hiragana, kanji, Cyrillic, Greek, Arabic, French, 125 Egyptian hieroglyphs), the NixOS
logos (CC BY 4.0), all made by `tools/build_assets.py`. The logo turns, drifts and cycles colour,
against burn-in; nothing flashes.

## Symbols (`syncrain/glyphs.py`)

* Sets of characters, each with a weight or a share: the theme's, or a symbols file's
  (`~/.config/syncrain/glyphs.json`). A drop's symbol: a set by its share, then one of its
  characters, all alike (`pickGlyph` in `state.frag`).
* A wallpaper's atlas holds only the glyphs its sets use: shipped ones copied from `glyphs.png`,
  others drawn from this machine's fonts (fontconfig) and cached in `~/.cache/syncrain/`.
* The drops are the channel's on every machine; which symbol they show is the sets'.

## Three hosts

* **Native wallpaper** (`syncrain/native/`, C), on Wayland. `syncrain` (Python) prepares the scene
  (shaders, textures, fixed uniforms, the KWin script, the fallback command) in a memfd and
  `execve`s the program: same pid, no Python or GTK left. One EGL context for every screen,
  layer-shell surfaces, frames paced like GTK's (presentation feedback and frame callbacks). What a
  frame computes on the processor is ported from Python bit for bit (`tests/native/`). A failure
  before the first frame hands over to the GTK host; a lost compositor, or 5 s of frames that
  cannot be shown, exits with status 1 so the service restarts it.
* **GTK host** (`syncrain/app.py`, `syncrain/renderer.py`): X11, windows, `--screenshot`,
  `--record`, and the fallback. A GLArea per viewport, OpenGL through libepoxy (`syncrain/gl.py`),
  `GSK_RENDERER=gl` and `GDK_DISABLE=dmabuf`.
* **Web page** (`web/template.html`): WebGL2; `tools/build_web.py` generates `web/index.html` and
  `web/artifact.html`.

The lanes compare them: native and GTK host to the pixel (at whole-number scales; at 125% or 150%
GTK draws more pixels and scales them down), the page within texture filtering on screens
wider than about 900 px (open item L12).

## The login screen (`syncrain/login/`, `syncrain/greeter.py`, `syncrain/greetd.py`)

* greetd runs `login.sh` as its user `greeter`; that runs KWin, and in it the native wallpaper and a
  GTK box on the overlay layer, one per screen sharing what is typed.
* The box speaks greetd's IPC (JSON over its socket): the password to PAM's first prompt, further
  prompts shown in the box. greetd checks it and starts the session once KWin is gone.
* No login (no marker file): `login.sh` hands over to greetd's text login.
* Installed to `/usr/local/lib/syncrain` (root's files), state and logs in `/var/lib/syncrain-login`,
  the greeter's settings fresh at every start. Only greetd's `[default_session]` changes
  (`syncrain/greetdconf.py`).
* After the login, Plasma's splash and wallpaper show a still frame of the rain (`syncrain/handover.py`).
* Only `install.sh --login-screen` puts any of it there, with a record of what started at boot
  before (`/etc/greetd/display-manager.before-syncrain`) that `--login-screen-off` goes back to.

## When a frame is drawn (`syncrain/pacing.py`, `syncrain/native/timing.c`)

Each screen draws for the refresh it will be shown on, every Nth refresh so the rate stays at or
under `--fps`. The lead before that refresh moves half a millisecond toward whichever side the
compositor reports a miss on.

## Covered screens (`syncrain/hidden.py`, `syncrain/native/kwin.c`)

KWin asks covered wallpapers for frames anyway. On KDE syncrain loads a small KWin script that says
which screens a maximized or full-screen window covers; those stop drawing until they show again.

## Memory and power

* On the operator's RTX 5090: the native wallpaper 123 MiB and 0.9% of a core at 30 fps; the GTK
  host 205 MiB and 4.7%. Most of either is the driver; syncrain's own state is a few MiB.
* The watts follow the frames (about 0.17 J a frame per screen), not the pixels or the language.
* NVIDIA's Wayland driver leaks a fixed amount per frame with explicit sync on, so syncrain turns
  it off for its own process (`syncrain/app.py`, `avoid_the_explicit_sync_leak`).
* The C heap keeps what is freed until asked: both hosts hand it back after the first frames and
  every five minutes after. The native wallpaper keeps a record (`record_memory`).
* The picture options (`--speed`, `--glow` and the rest, `engine.look`) are uniforms set once.

## Builds and the stream (`syncrain/build.py`)

* `BUILD_NUMBER` is the only identity; there are no versions.
* The stream id is the start of a SHA-256 over `STREAM_FILES` (`syncrain/engine.py`,
  `syncrain/glyphs.py`, `syncrain/data/`); `tests/fixtures/stream_freeze.json` freezes it. Not yet
  covered: the hosts' geometry and the page (open item L20, `docs/ROADMAP.md`).

## Packaging and release

* `install.sh`: pacman packages, the app in `~/.local`, the native wallpaper built with gcc, an
  optional systemd user service.
* `nix/package.nix`: the package (the native wallpaper in `libexec/`), with NixOS and home-manager
  modules beside it.
* `tools/package_release.py`: bump, rebuild the pages, run every lane, stamp the notes, write
  `SYNCRAIN<N>.tar.zst`.
