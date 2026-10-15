# Handoff: the state of syncrain at build 35

What is true now, for a context that has just opened this tree. Where this page and the code
disagree, the code is right; fix the page in the same build. Each fact has one home; this page
points to it.

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

* **What syncrain is**: syncrain backdrop, the rain for the whole session: the desktop wallpaper,
  the login screen and the lock screen (both optional), the web page and videos (the operator's
  name, 2026-10-15). NixOS is the base: its module gives the wallpaper, login screen and lock screen (build 32), and
  the flake's template a whole Plasma 6 desktop with all of it (`nixosModules.backdrop`, build 33);
  `install.sh` covers Arch, Debian, Fedora and openSUSE
  (each installed for real in a root of its own, `docs/agent/ENVIRONMENT.md`).
* **The operator's machine**: CachyOS, KDE Plasma 6 on Wayland, two screens, RTX 5090; its numbers
  in `docs/agent/TARGET_ENVIRONMENT.md`. It runs build 16 or later (its login screen worked there on
  2026-10-13).
* **How it works**: three hosts (native C on Wayland, GTK elsewhere and for `--screenshot`,
  `--record` and `--video`, the page in browsers), six passes, the settings file, the login and
  lock screens, video: `docs/ARCHITECTURE.md`. Every option and how to use it: `docs/OPERATIONS.md`.
* **The default** is the operator's settings file sent with the review of build 33
  (`tests/fixtures/operator_config.json`), as the `syncrain` preset (`syncrain/data/themes.json`,
  made by `tools/build_assets.py`; its `look` says where the sliders start, so that file and no
  file are the same frame, `tests/unit/test_the_options.py`). Presets: syncrain, nixos, matrix.
* **The login and lock screens stay optional**: only `--login-screen` and `--lock-screen` touch
  them, and `-off` puts back what was there. `tests/unit/test_the_login_screen_is_optional.py` and
  `tests/unit/test_the_lock_screen_is_optional.py` hold every build to it. The lock screen is tested
  in a real headless KWin, and in use on the operator's desktop since build 26 (their request of
  2026-10-15 10:45 came from using it). Build 34 made it answer PAM after every screen went and
  one came back (kscreenlocker 6.7 frees the QML engine at zero views), keep a pending password from
  a second factor, take an empty answer to a visible prompt and ignore clicks while hidden.
* **Boot stays plain text** (the operator, 2026-10-15): never the bootloader, the initramfs or a
  boot splash.
* **Stream**: `1ad0a2dd` since build 35 (the new default, `composite.frag` to the spec, stricter
  colours and periods); `822ea58a` 29 to 34 (sentences' gaps and trails in `state.frag`); `85ace386` in
  28; `a9c058f3` 24 to 27; `f98ef1ca` in 23; `25b02556` in 22; `def5684f` 15 to 21; `c18f8be2` in 12
  to 14; `48e6bf9c` 3 to 11.
* **GitHub**: `main` holds builds 7 to 35, a commit `syncrain build <N>` each, and a few
  documents-only commits between them.

## Under way

The review of build 33 (84 numbered items, in the operator's review document) is being fixed one
area a build, the most critical first: `docs/ROADMAP.md`, "Planned builds". Build 34 did the lock
screen (1, 3, 27, 28, 30, 56); build 35 the operator's new default with every stream-file fix (69,
65, 66, 76), so the builds after it leave the stream alone.

## Waits on the operator

* Anyone booting Debian, Fedora or openSUSE with the login or lock screen (only the roots so far;
  Fedora's SELinux is untried).
* A video's watts against the live rain's, measured there.
* How fast the login screen comes up (`--diagnose`); the memory record after a few hours.
* The time of the next glow flare-up: two hours of frames show none (`docs/HISTORY.md`, build 12).
* The two questions in `docs/ROADMAP.md`.

How to work with them: `docs/agent/WORKING_WITH_THE_OPERATOR.md`.
