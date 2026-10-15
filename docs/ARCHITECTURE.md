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

Data: `syncrain/data/themes.json` (the presets), `syncrain/data/glyphs.png` (489 shipped glyphs: code,
katakana, hiragana, kanji, Cyrillic, Greek, Arabic, French, 125 Egyptian hieroglyphs) and the NixOS
logo (CC BY 4.0), made by `tools/build_assets.py`; syncrain's logo by `tools/build_logo.py`. The
logo turns, drifts and cycles colour, against burn-in; nothing flashes.

## Symbols (`syncrain/glyphs.py`)

* Sets of characters, each with a weight or a share: the preset's, or a symbols file's
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
  `--record`, `--video`, and the fallback. A GLArea per viewport, OpenGL through libepoxy (`syncrain/gl.py`),
  `GSK_RENDERER=gl` and `GDK_DISABLE=dmabuf`.
* **Web page** (`index.html`, at the top): WebGL2, one self-contained file; `tools/build_web.py`
  fills its data blocks (shaders, presets, images, the build) in place, and writes the live page's
  copy (`--artifact`). Its settings panel edits one settings object, drawn live, and saves it as
  the settings file the desktop reads (below). It builds the atlas as `glyphs.resolve` does (only
  the glyphs used, the words' first), copying shipped glyphs from `glyphs.png` and drawing others
  with the browser's fonts.

The lanes compare them: native and GTK host to the pixel (at whole-number scales; at 125% or 150%
GTK draws more pixels and scales them down), the page within texture filtering.

## The look (`syncrain/engine.py`, `compose`)

* A look is a preset (themes.json's `themes`: syncrain, the default, nixos, matrix) with the settings over it: the rain's
  gradient (dark, middle, bright, leading) and glow, the background gradient and vignette, the logo
  and its size and colour cycle, the rain's colour cycle and flavours, the hidden words. Every host
  draws from the composed look (the page's `composeLook` does the same).
* **Flavours** (`rain.glsl`, `flavourTurns`): each of the 64 columns turns the gradient round the
  hue wheel by k/N of a turn, k by the channel's hash or, as a wave, in order across the stream; the
  glow beside a column follows it. **Cycle** turns every flavour together (`uRainHueCph`). One
  flavour skips the turn, so a preset with one (nixos) draws the picture it always drew.
* **The logo** (`syncrain/logo.py`): syncrain's own (drawn in `logo-syncrain.svg`, its texture made
  by `tools/build_logo.py`), the NixOS snowflake, or a picture made into the same kind
  of texture (a square, the picture in its middle two thirds, its own average colour under its
  see-through pixels). The page makes it and keeps it in the settings file as a PNG, used as it is.
  One colour over it (`uLogoTint`) keeps its shape and replaces its colours, and its glow's.

## The settings file (`syncrain/app.py`, `CONFIG_KEYS`)

* `syncrain-config-1`: the picture options by name (`bg_gain` for `--bg-gain`), `null` for the
  preset's, and `glyphs`, a symbols file's sets; build 21's `theme` and `rainbow` still read. Read before the command line, as if its options were
  typed first, so they are checked the same way and the command line goes over them.
* `--config FILE`, else `~/.config/syncrain/config.json` when it is there. The page checks what it
  loads and saves the same way (`readSettings`, `checkGlyphs`), so a file it saves is one the
  desktop takes; the browser lane draws one on both and compares.
* The login screen's rain reads a copy in `/usr/local/lib/syncrain/config.json`.

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

## The lock screen (`syncrain/lockscreen/`)

* KWin 6 lets no other locker in (no ext-session-lock): Plasma's own, `kscreenlocker_greet`, which
  KWin starts, loads `lockscreen/LockScreen.qml` from the shell package plasmashellrc names, else
  the one `PLASMA_DEFAULT_SHELL` names. `install.sh --lock-screen` sets that, with
  `QML_IMPORT_PATH`, in a drop-in for KWin's unit alone: Plasma's shell keeps its layout under its
  own package's name and never sees it.
* The package `org.syncrain.lockscreen` (falling back to `org.kde.plasma.desktop`) is QML only: one
  conversation with the `authenticator` the locker gives it for all screens (`Pam.qml`, a singleton
  on the locker's one engine), by Plasma 6.7's rules (PAM restarted only after a refusal's delay),
  and on each screen the box (`Box.qml`, the login box's look), showing what `Shared.qml` (another
  singleton) holds for all of them: what is typed, the eye, and whether the box is up (a key or a
  moved pointer, then a minute); PAM decides. The rain and the Caps Lock note come through Loaders, so the box works
  without them.
* The rain is `SyncRain` (`rainitem.cpp`, the QML module `org.syncrain`): the native passes into a
  framebuffer on Qt Quick's OpenGL context, from the scene file `syncrain --write-scene` writes; the
  native wallpaper rewrites it at every start (the GTK host does not; `install.sh` writes it too),
  so the lock screen draws the desktop's settings and runs no Python.

## Video (`syncrain/video.py`, the page's `makeVideo`)

* The GTK host draws each frame off the screen at the video's size, in slices of a tenth of a second
  per frame callback, and pipes it to ffmpeg (H.264 or VP9 in BT.709, or a GIF with one palette),
  as `NAME.part.EXT`, renamed when whole. The page encodes with WebCodecs and writes the WebM itself.
* A loop's first frames (2 s, or half the video) are the moments n frames on fading into their own
  (`video.plan`): frame n-1 flows into frame 0. Python and the page do the same sums, halves
  rounded up; the browser lane compares their frames with each other and with the app's.

## When a frame is drawn (`syncrain/pacing.py`, `syncrain/native/timing.c`)

Each screen draws for the refresh it will be shown on, every Nth refresh so the rate stays at or
under `--fps`. The lead before that refresh moves half a millisecond toward whichever side the
compositor reports a miss on.

## Covered screens (`syncrain/hidden.py`, `syncrain/native/kwin.c`)

KWin asks covered wallpapers for frames anyway. On KDE syncrain loads a small KWin script that says
which screens a maximized or full-screen window covers; those stop drawing until they show again.

## Memory and power

* The measurements on the operator's machine: `docs/agent/TARGET_ENVIRONMENT.md`. The watts follow
  the frames, not the pixels or the language; syncrain's own state is a few MiB.
* NVIDIA's explicit-sync leak (`docs/LESSONS.md`) is turned off for syncrain's own process
  (`syncrain/app.py`, `avoid_the_explicit_sync_leak`).
* The C heap keeps what is freed until asked: both hosts hand it back after the first frames and
  every five minutes after. The native wallpaper keeps a record (`record_memory`).
* The picture options (`--speed`, `--glow` and the rest, `engine.LOOK`; `--bg-gain` the
  renderer's) are uniforms set once.

## Builds and the stream (`syncrain/build.py`)

* `BUILD_NUMBER` is the only identity; there are no versions.
* The stream id is the start of a SHA-256 over `STREAM_FILES` (`syncrain/engine.py`,
  `syncrain/glyphs.py`, `syncrain/data/`); `tests/fixtures/stream_freeze.json` freezes it. Not yet
  covered: the hosts' geometry and the page (open item L20, `docs/ROADMAP.md`).

## Packaging and release

* `install.sh` (Arch, Debian, Fedora, openSUSE: `set_packages`): the family's packages, the app in `~/.local`, the native wallpaper built with gcc, an
  optional systemd user service.
* `nix/package.nix`: the package (the native wallpaper in `libexec/`), with NixOS and home-manager
  modules beside it.
* `tools/package_release.py`: bump, rebuild the pages, run every lane, stamp the notes, write
  `SYNCRAIN<N>.tar.zst`.
