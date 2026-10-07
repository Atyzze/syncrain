# syncrain

A live code-rain wallpaper that never loops and stays in sync across machines. Every frame is a
function of the UTC clock and a channel name, so two machines on the same channel draw the same
frame at the same moment. Two themes: **nixos** (icy blue rain, falling snow, the NixOS snowflake
turning slowly through the rainbow) and **matrix** (green).

**This file is a directory.** It says where to look and the few things that cost you if you get
them wrong. Everything else lives in `docs/`, because a second copy of a fact is a copy that goes
stale without anything failing.

## Read these, in this order

    docs/WHERE_WE_ARE.md                       the project on one page, in plain words (the operator's page)
    docs/agent/HANDOFF.md                      what is true right now, for a context that just opened the archive
    docs/agent/NEXT_BUILD.md                   the next build: what it is, what blocks it, how to release it
    docs/agent/WORKING_WITH_THE_OPERATOR.md    how the operator sends, decides and wants answers
    docs/agent/ENVIRONMENT.md                  the agent sandbox: bring-up, the lanes, the traps
    docs/agent/TARGET_ENVIRONMENT.md           the machines syncrain runs on
    docs/ROADMAP.md                            what is open, in order; the build cadence; standing constraints
    docs/ARCHITECTURE.md                       the clock, the passes, the stream, the app, the page, the packages
    docs/OPERATIONS.md                         every option and recipe: install, upgrade, run, diagnose, record
    docs/LESSONS.md                            the rules this project learned by shipping their opposite
    docs/HISTORY.md                            a line per build, and the operator's decisions
    docs/build_notes/                          one file per build, in full

Everything outside the notes and the history says what is true now. Every build whose number ends
in 0 is a consolidation build: it changes no behaviour and makes that true again
(`docs/ROADMAP.md`, "Build cadence"). When you fix something a document describes, fix the
description in the same pass, and prefer deleting a sentence to qualifying it. Only the code is
real.

## Install it (Arch, CachyOS, EndeavourOS, Manjaro)

    tar xf SYNCRAIN<N>.tar.zst && cd syncrain_build_<N>
    ./install.sh                 # pacman packages, then the app in ~/.local; a newer build's script upgrades
    syncrain --window            # try it in a window
    syncrain                     # as your wallpaper; Ctrl+C stops it
    syncrain --diagnose          # if it does not draw: what this machine offers, and why

NixOS, home-manager, other distributions, the browser page, autostart, what it costs in power and
how to measure that (`syncrain --power-sweep`), and every option: `docs/OPERATIONS.md`.

## Builds, not versions

Every archive that leaves the build machine has its own number, `SYNCRAIN<N>.tar.zst` holding one
directory `syncrain_build_<N>/`, and the number is the only identity a tree has: `BUILD_NUMBER`.
Nothing carries a version string. `syncrain --build` prints `syncrain build <N> (stream <id>)`;
the stream id names what decides the picture, so two machines with the same stream id and channel
and synced clocks draw the same frame, whatever their build numbers.

## Verifying a tree before you change it

    python3 tools/test_suite.py --lane quick     # unit and contract lanes: seconds, no display
    python3 tools/test_suite.py                  # every lane this machine can run; the rest skip with a reason
    python3 tools/stream_freeze.py               # the stream has not moved

The lanes: unit, contract (the project's rules), render (the app on Xvfb), wayland (the wallpaper
layer in a headless Sway), kwin (the wallpaper on a headless KWin 6, Plasma's compositor: covered
screens and frame timing), browser (the page in Chromium, and against the app), nix (the package
and both services, evaluated and built). What each needs: `docs/agent/ENVIRONMENT.md`.

## Releasing

One command, detached:

    setsid nohup python3 tools/package_release.py --output <dir> > release.log 2>&1 < /dev/null &

It undoes a previously killed run from its journal, writes `current + 1` into `BUILD_NUMBER`,
rebuilds the generated pages, runs every lane with every environment required, stamps the gate's
result into the build's notes, builds and clean-installs a wheel, and writes `<dir>/SYNCRAIN<N>.tar.zst`,
verified byte for byte against the tree before it gets its name. The log's last line is
`build <N>: <path>`. A run that raises puts the tree back and spends no number.

**Every archive that leaves this machine bumps the build number**, and `tools/package_release.py`
is the only thing that makes one: never a patch, never a hand-made tar, never `BUILD_NUMBER`
edited by hand. Before the command, in the same pass as the change: write the build's notes with
the literal token GATE_RESULT under "## Verification", and rewrite `docs/WHERE_WE_ARE.md`, the
handoff and `docs/agent/NEXT_BUILD.md` (which names the build after it). The gate fails on them.

## Things that will cost you

* **The stream is frozen.** A change to a shader, `themes.json`, the atlas, the logos or
  `syncrain/engine.py` changes what every machine on a channel draws, and the gate refuses it until
  `python3 tools/stream_freeze.py --write` re-takes the freeze on purpose and the notes say so.
* **Never ask GTK for an OpenGL version.** GTK hands out OpenGL ES unless told otherwise; build 2
  asked for "3.3" and drew nothing on the operator's machine. Take what comes and check it
  (`syncrain/app.py`, `gl_context_problem`).
* **The page and the app are two implementations of the host side** (JavaScript and Python) over
  the same shaders. Change one, change the other; the browser lane compares their frames.
* **systemd unescapes inside single quotes.** Every service line goes through the same quoting
  (`docs/ARCHITECTURE.md`, "Packaging"), and the tests parse it the way systemd does.

## Where defects cluster

* **Starting OpenGL.** Which API and version GTK gives depends on the GTK and the driver; the
  render and Wayland lanes run with only OpenGL ES, only desktop OpenGL and none at all.
* **The desktop it attaches to.** Layer choice (KDE takes the bottom layer), click-through, monitors
  coming and going, and what the compositor says about covered screens; KWin is in a lane, Plasma's
  shell is not.
* **What the operator's machine runs.** The launcher's module path, preloading, systemd quoting:
  each was right in the sandbox and wrong somewhere else once (`docs/LESSONS.md`).

## Layout

    syncrain/            the app: app.py (windows, layers, OpenGL, signals), renderer.py (the six passes),
                         pacing.py (when frames are drawn), hidden.py (KWin: covered screens),
                         engine.py (clock, seed, motion), build.py (build number, stream fingerprint),
                         diagnose.py, bench.py (--benchmark), power.py (--power-sweep), cover.py,
                         data/ (shaders, themes.json, glyph atlas, logos)
    web/                 template.html, and index.html and artifact.html generated from it
    nix/                 the package, the web bundle, the NixOS and home-manager modules
    install.sh           the Arch-family installer
    tools/               package_release.py, test_suite.py, stream_freeze.py, build_web.py, build_assets.py,
                         prepare_environment.sh
    tests/               unit, contract, render, wayland, kwin, browser, nix; fixtures/stream_freeze.json
    extras/              the CachyOS logo mask
    docs/                everything above
