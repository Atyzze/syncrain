# Handoff: the state of syncrain at build 12

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
* **Hosts**: on Wayland the native wallpaper (C, `syncrain/native/`); on X11, in windows and as
  fallback the GTK host (`syncrain/app.py`); in browsers the page (`web/template.html`).
* **Memory**: 123 MiB at start on their card. Build 11 (explicit sync off) grew to 225 MiB in 18 h,
  slowing, then fell to 170 by itself: freed memory, not a leak. Build 12 hands it back every five
  minutes and writes `~/.local/state/syncrain/memory.log`; `--diagnose` shows it.
* **Picture options** (build 12): `--glow`, `--bloom`, `--bg-gain`, `--speed`, `--density`,
  `--snow`, `--hieroglyphs` (`engine.look`); uniforms set once, in all three hosts.
* **Power**: about 11 W at 30 fps there; the watts follow the frames.
* **Covered screens**: not drawn on KDE (a KWin script); 0 W there.
* **Timing**: every frame on the refresh; 97 to 100% even and steady on their screens.
* **Stream**: `c18f8be2` since build 12 (hieroglyphs in the atlas); `48e6bf9c` from build 3 to 11.
* **GitHub**: `main` holds builds 7 to 12, one commit each (`syncrain build <N>`).

## Waits on the operator

* The memory record after a few hours of build 12.
* The time of the next glow flare-up: two hours of frames show none (build 12's notes).
* The three questions in `docs/ROADMAP.md`.

## Their standing calls

Build numbers only; deliveries only from the release tool; short documents; no long dashes; "the
operator" or "they"; consolidation at every number ending in 0; nothing that flashes; measure
before claiming.
