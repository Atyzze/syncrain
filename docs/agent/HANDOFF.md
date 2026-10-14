# Handoff: the state of syncrain at build 19

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
  (`docs/agent/TARGET_ENVIRONMENT.md`). It runs build 8 or later.
* **Hosts**: on Wayland the native wallpaper (C, `syncrain/native/`, the passes in `passes.c`); on
  X11, in windows and as fallback the GTK host (`syncrain/app.py`); in browsers the page
  (`web/template.html`). Builds 13 and 14 had a Plasma wallpaper (a Qt item in plasmashell); it
  broke on the operator's desktop and build 15 removed it (`install.sh` cleans it up): Qt's Dutch
  locale made `strtod` read every option wrong (fixed in build 16, `c_strtod`).
* **Login screen** (build 16, `install.sh --login-screen`): greetd runs `syncrain/login/login.sh`;
  KWin, the rain, a GTK box on every screen (`syncrain/greeter.py`) speaking greetd's IPC; text login
  as fallback. Works on the operator's desktop (2026-10-13). After the login Plasma's splash and
  wallpaper are a still of the rain (`syncrain/handover.py`, build 17).
* **The login screen is optional** (the operator, 2026-10-14): nothing but `--login-screen` touches
  how the machine logs in, and `--login-screen-off` goes back to the record of what started at boot
  (`/etc/greetd/display-manager.before-syncrain`); only the user who set it up changes it.
  `tests/unit/test_the_login_screen_is_optional.py` holds every build to it. Root copies only what
  the user could read.
* **A review of build 17** (2026-10-14, the operator's Claude doc "Syncrain build 17 code review"):
  9 middling findings (M), 21 small (L). Builds 18 and 19 fixed every M and most L; open: L8, L11,
  L12, L20, L21, and a font name that is not UTF-8 (`syncrain/glyphs.py`, a stream file); build 19's
  notes.
* **The box speaks PAM's whole conversation** (build 19): the password to the first prompt, further
  prompts asked in the box. **greetd's config** is changed only in `[default_session]`
  (`syncrain/greetdconf.py`).
* **Memory**: 123 MiB at start on their card. Build 11 (explicit sync off) grew to 225 MiB in 18 h,
  slowing, then fell to 170 by itself: freed memory, not a leak. Build 12 hands it back every five
  minutes and writes `~/.local/state/syncrain/memory.log`; `--diagnose` shows it.
* **Picture options** (build 12): `--glow`, `--bloom`, `--bg-gain`, `--speed`, `--density`,
  `--snow`, `--hieroglyphs` (`engine.look`); uniforms set once, in every host.
* **Power**: about 11 W at 30 fps there; the watts follow the frames.
* **Covered screens**: not drawn on KDE (a KWin script); 0 W there.
* **Timing**: every frame on the refresh; 97 to 100% even and steady on their screens.
* **Symbols**: sets with weights or shares (`syncrain/glyphs.py`); the themes' own, or the
  operator's `~/.config/syncrain/glyphs.json`. 489 shipped glyphs; others from the machine's fonts.
* **Stream**: `def5684f` since build 15 (symbols by set); `c18f8be2` in 12 to 14; `48e6bf9c` 3 to 11.
* **GitHub**: `main` holds builds 7 to 19, one commit each (`syncrain build <N>`).

## Waits on the operator

* How build 17's hand-over looks there; how fast the login screen came up (`--diagnose`); that
  build 18's `./install.sh` moved the record of Plasma Login beside greetd's config.
* The memory record after a few hours of build 12.
* The time of the next glow flare-up: two hours of frames show none (build 12's notes).
* The three questions in `docs/ROADMAP.md`.

## Their standing calls

Build numbers only; deliveries only from the release tool; short documents; no long dashes; "the
operator" or "they"; consolidation at every number ending in 0; nothing that flashes; measure
before claiming; the login screen stays optional.
