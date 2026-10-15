# Handoff: the state of syncrain at build 27

What is true now, for a context that has just opened this tree. Where this page and the code
disagree, the code is right; fix the page in the same build.

## Read first

This page, `docs/agent/NEXT_BUILD.md`, `docs/agent/WORKING_WITH_THE_OPERATOR.md`,
`docs/agent/ENVIRONMENT.md`, `docs/ROADMAP.md`; the rest when needed.

## Start here

1. Clone `main` from github.com/Atyzze/syncrain. Attach the repository with push access before
   pushing (`docs/agent/ENVIRONMENT.md`).
2. `tools/prepare_environment.sh --verify`, then `python3 tools/test_suite.py --lane all`. Between
   releases three checks fail by one (`docs/agent/NEXT_BUILD.md`).
3. Read what the operator sent last, and answer it in one plain sentence first.

## What is true now

* **The operator's machine**: CachyOS, KDE Plasma 6 on Wayland, two screens, RTX 5090
  (`docs/agent/TARGET_ENVIRONMENT.md`). It runs build 16 or later (its login screen worked there on
  2026-10-13).
* **Hosts**: on Wayland the native wallpaper (C, `syncrain/native/`, the passes in `passes.c`); on
  X11, in windows and as fallback the GTK host (`syncrain/app.py`); in browsers the page
  (`index.html` at the top, its data filled in by `tools/build_web.py`). Builds 13 and 14's Plasma wallpaper broke there; build 15 removed it
  (`install.sh` cleans it up).
* **Login screen** (`install.sh --login-screen`): greetd runs `syncrain/login/login.sh`; KWin, the
  rain, a GTK box on every screen (`syncrain/greeter.py`) speaking greetd's IPC, PAM's further
  prompts asked in the box; text login as fallback. After the login Plasma's splash and wallpaper
  are a still of the rain (`syncrain/handover.py`).
* **The login screen is optional** (the operator, 2026-10-14): nothing but `--login-screen` touches
  how the machine logs in; `--login-screen-off` goes back to the record of what started at boot
  (`/etc/greetd/display-manager.before-syncrain`); greetd's config changes only in
  `[default_session]` (`syncrain/greetdconf.py`); only the user who set it up changes it. Root
  reads nothing of the user's. `tests/unit/test_the_login_screen_is_optional.py` holds every build
  to it.
* **The review of build 17**: builds 18 and 19 fixed every M and most L (`docs/HISTORY.md`); what
  is open is in `docs/ROADMAP.md`, "Open items".
* **Memory**: 123 MiB at start on their card; handed back every five minutes, with a record in
  `~/.local/state/syncrain/memory.log` that `--diagnose` shows.
* **Picture options**: `--glow`, `--bloom`, `--bg-gain`, `--speed`, `--density`, `--snow`,
  `--hieroglyphs` (`engine.look`); uniforms set once, in every host.
* **Power**: about 11 W at 30 fps there; the watts follow the frames. Covered screens: not drawn
  on KDE (a KWin script); 0 W there.
* **Timing**: every frame on the refresh; 97 to 100% even and steady on their screens.
* **Symbols**: sets with weights or shares (`syncrain/glyphs.py`); the themes' own, or the
  operator's `~/.config/syncrain/glyphs.json`. 489 shipped glyphs; others from the machine's fonts.
* **The look** (build 22): no themes; two presets (nixos, matrix) that the settings go over
  (`engine.compose`, the page's `composeLook`): the rain's gradient and glow, the background and
  vignette, flavours (each column one of N hues, by the channel or as a wave) and a colour cycle,
  any picture as the logo (`syncrain/logo.py`; the page puts the texture in the settings file), its
  size and rainbow, the hidden words. One flavour and no cycle is the picture as it was.
* **The default is the operator's own look** (build 24): the `syncrain` preset is their settings
  file of 2026-10-14 22:33 (white-tailed matrix colours, 64 in a wave turning every 440 s, the NixOS
  logo's rainbow every 30 s, black background, bloom 5); drawn by build 23, that file is the same
  frame. Their redrawn logo (`syncrain/data/logo-syncrain.svg`, build 23) stays a choice. One colour
  over any logo: `--logo-color`, `logo_color`.
* **The lock screen** (builds 25 to 27, optional, `install.sh --lock-screen`): Plasma's own locker loads
  the shell package `org.syncrain.lockscreen` (`syncrain/lockscreen/`), named by
  `PLASMA_DEFAULT_SHELL` in a drop-in for KWin's unit alone; the rain is a QML item drawing the
  native passes from the scene file the wallpaper writes at each start; the box drives PAM as
  Plasma 6.7's does (PAM restarted only after its delay; build 26). The box is away until a key or
  a moved pointer, goes after a minute without either (forgetting what was typed), and every screen
  shows the same text and eye (`Shared.qml`; build 27). Tested in a real headless KWin, locked and
  unlocked by typing, and on two screens with real key and pointer events (lane `lockscreen`).
  Not yet seen on the operator's machine.
* **The settings file** (build 21): the page's Settings panel tries every option and symbol set
  live and saves `config.json` (`syncrain-config-1`); `./install.sh --config config.json` keeps it
  as `~/.config/syncrain/config.json`, read under the command line (`syncrain/app.py`,
  `CONFIG_KEYS`); the login screen's rain reads a copy. The browser lane draws one file on the page
  and the desktop and compares the frames. `--theme` refuses an unknown theme with status 2.
* **Stream**: `a9c058f3` since build 24 (the syncrain preset); `f98ef1ca` in 23; `25b02556` in 22; `def5684f` 15 to 21; `c18f8be2` in 12 to 14; `48e6bf9c` 3 to 11.
* **GitHub**: `main` holds builds 7 to 27, one commit each (`syncrain build <N>`).

## Waits on the operator

* How build 17's hand-over looks there; how fast the login screen came up (`--diagnose`); that
  build 18's `./install.sh` moved the record of Plasma Login beside greetd's config.
* The memory record after a few hours of build 12 or later.
* The time of the next glow flare-up: two hours of frames show none (`docs/HISTORY.md`, build 12).
* The two questions in `docs/ROADMAP.md`.
* Whether build 27's lock screen comes up and unlocks on their desktop (two screens, NVIDIA), and
  how it looks.
* How build 24's default looks on their desktop once their kept settings file is saved again from
  the page (over the new default, its bloom 2 doubles the bloom).

## Their standing calls

Build numbers only; deliveries only from the release tool; short documents; no long dashes; "the
operator" or "they"; consolidation at every number ending in 0; nothing that flashes; measure
before claiming; the login screen stays optional.
