# Handoff: the state of syncrain at build 11

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
* **Memory**: 123 MiB at start on their card. Builds 8 to 10 then grew about 0.9 MiB a minute
  while drawing: NVIDIA's explicit-sync leak, not syncrain's (flat on Mesa). Build 11 turns
  explicit sync off for syncrain (`syncrain/app.py`); not yet seen on their desktop.
* **Power**: about 11 W at 30 fps there; the watts follow the frames.
* **Covered screens**: not drawn on KDE (a KWin script); 0 W there.
* **Timing**: every frame on the refresh; 97 to 100% even and steady on their screens.
* **Stream**: `48e6bf9c`, unchanged since build 3.
* **GitHub**: `main` holds builds 7 to 11, one commit each (`syncrain build <N>`).

## Waits on the operator

* Whether memory stays flat with build 11 (btop over a few hours).
* The three questions in `docs/ROADMAP.md`.

## Their standing calls

Build numbers only; deliveries only from the release tool; short documents; no long dashes; "the
operator" or "they"; consolidation at every number ending in 0; nothing that flashes; measure
before claiming.
