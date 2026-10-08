# syncrain

A live code-rain wallpaper that never loops and stays in sync across machines. Every frame is a
function of the UTC clock and a channel name, so two machines on the same channel draw the same
frame at the same moment. Two themes: **nixos** (icy blue rain, falling snow, the NixOS snowflake
turning slowly through the rainbow) and **matrix** (green). It runs as a wallpaper on Linux
(Wayland and X11) and as a web page in any browser with WebGL2.

<p align="center">
  <img src="docs/images/nixos.jpg" width="49%" alt="The nixos theme: pale blue characters falling in columns over dark blue, with snowflakes and the NixOS snowflake in rainbow colours in the middle">
  <img src="docs/images/matrix.jpg" width="49%" alt="The matrix theme: green katakana, digits and letters falling in columns over black">
</p>
<p align="center"><sub>The channel <code>public</code> at 2026-10-07 00:00:07 UTC, in both themes.
<code>syncrain --window --time 1791331207</code> (and <code>--theme matrix</code>) draws that moment on any machine.</sub></p>

## What it does

* **Never loops.** Nothing is stored or replayed: each frame is computed from the clock, for any
  moment, past or future.
* **The same rain everywhere.** Machines on one channel with synced clocks show the same frame, in
  the app or in the browser. Another channel name is another endless stream.
* **A real wallpaper.** One view per monitor, behind your windows. On Wayland compositors with
  layer-shell (KDE Plasma 6, Hyprland, Sway and others) clicks go through to the desktop; on KDE
  Plasma it covers the desktop icons, which still take the clicks. On X11 it is the desktop window
  itself.
* **Frugal.** Frames are capped and timed to the screen's refresh wherever a compositor reports it,
  and on Wayland a screen hidden by a window is not drawn. `syncrain --power-sweep` measures what it
  costs on your graphics card.
* **Easy on screens and eyes.** Nothing stays put, against burn-in: the logo turns, drifts and
  cycles through the rainbow. Nothing flashes.

## Try it

On Arch, CachyOS, EndeavourOS or Manjaro:

```sh
git clone https://github.com/Atyzze/syncrain && cd syncrain
./install.sh                 # pacman packages (asks for sudo once), then the app in ~/.local
syncrain --window            # try it in a window
syncrain                     # as your wallpaper; Ctrl+C stops it
./install.sh --autostart     # optional: start it with every graphical login
syncrain --diagnose          # if it does not draw: what this machine offers, and why
```

`git pull` and `./install.sh` again upgrade it. A build's archive, `SYNCRAIN<N>.tar.zst`, installs
the same way from the folder it unpacks to.

* **NixOS**, with flakes on: `nix run github:Atyzze/syncrain -- --window` tries it; the flake also
  has a NixOS module and a home-manager module (`services.syncrain`).
* **In a browser**: open `web/index.html` from a clone or a download, one self-contained file;
  `?theme=matrix&channel=friends` picks the look and the stream.

It needs GTK 4.14 or later, OpenGL 3.3 or OpenGL ES 3.0 and a synced clock; on Wayland, a
compositor with layer-shell (GNOME has none: use `--window`, or the web page). The rest of what it
needs, other distributions, the Nix modules, every option, recording a video and measuring power:
[`docs/OPERATIONS.md`](docs/OPERATIONS.md).

## Documentation

**This file is a directory.** It says where to look and the few things that cost you if you get
them wrong. Everything else lives in `docs/`, because a second copy of a fact is a copy that goes
stale without anything failing. The summary above repeats a few facts for visitors; each is kept
in [`docs/OPERATIONS.md`](docs/OPERATIONS.md), which has every option and recipe. How a frame is
made, and why every machine makes the same one, is [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Working on syncrain

syncrain is made in numbered builds by AI agents, for one person, the operator, whose requests and
decisions steer it; the documents call them "the operator" and "they". `docs/agent/` briefs
whoever makes the next build. Read these, in this order:

1. [`docs/WHERE_WE_ARE.md`](docs/WHERE_WE_ARE.md): the project on one page, in plain words (the operator's page)
2. [`docs/agent/HANDOFF.md`](docs/agent/HANDOFF.md): what is true right now, for a context that just opened the tree
3. [`docs/agent/NEXT_BUILD.md`](docs/agent/NEXT_BUILD.md): the next build: what it is, what blocks it, how to release it
4. [`docs/agent/WORKING_WITH_THE_OPERATOR.md`](docs/agent/WORKING_WITH_THE_OPERATOR.md): how the operator sends, decides and wants answers
5. [`docs/agent/ENVIRONMENT.md`](docs/agent/ENVIRONMENT.md): the agent sandbox: bring-up, the lanes, the traps
6. [`docs/agent/TARGET_ENVIRONMENT.md`](docs/agent/TARGET_ENVIRONMENT.md): the machines syncrain runs on
7. [`docs/ROADMAP.md`](docs/ROADMAP.md): what is open, in order; the build cadence; standing constraints
8. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): the clock, the passes, the stream, the app, the page, the packages
9. [`docs/OPERATIONS.md`](docs/OPERATIONS.md): every option and recipe: install, upgrade, run, diagnose, record
10. [`docs/LESSONS.md`](docs/LESSONS.md): the rules this project learned by shipping their opposite
11. [`docs/HISTORY.md`](docs/HISTORY.md): a line per build, and the operator's decisions
12. [`docs/build_notes/`](docs/build_notes/): one file per build, in full

Everything outside the notes and the history says what is true now. Every build whose number ends
in 0 is a consolidation build: it changes no behaviour and makes that true again
(`docs/ROADMAP.md`, "Build cadence"). When you fix something a document describes, fix the
description in the same pass, and prefer deleting a sentence to qualifying it. Only the code is
real.

### Builds, not versions

Every archive that leaves the build machine has its own number, `SYNCRAIN<N>.tar.zst` holding one
directory `syncrain_build_<N>/`, and the number is the only identity a tree has: `BUILD_NUMBER`.
Nothing carries a version string. `syncrain --build` prints `syncrain build <N> (stream <id>)`;
the stream id names what decides the picture, so two machines with the same stream id and channel
and synced clocks draw the same frame, whatever their build numbers.

On GitHub, `main` carries each released build from 7 on as one commit, `syncrain build <N>`,
holding exactly the tree of its archive. A commit between two builds changes no behaviour
(documentation, say), and the next build includes it, so a new build starts from `main` rather than
from the last archive.

### Verifying a tree before you change it

    python3 tools/test_suite.py --lane quick     # unit and contract lanes: seconds, no display
    python3 tools/test_suite.py                  # every lane this machine can run; the rest skip with a reason
    python3 tools/stream_freeze.py               # the stream has not moved

The lanes: unit, contract (the project's rules), render (the app on Xvfb), wayland (the wallpaper
layer in a headless Sway), kwin (the wallpaper on a headless KWin 6, Plasma's compositor: covered
screens and frame timing), browser (the page in Chromium, and against the app), nix (the package
and both services, evaluated and built). What each needs: `docs/agent/ENVIRONMENT.md`.

### Releasing

One command, detached:

    setsid nohup python3 tools/package_release.py --output <dir> > ../release.log 2>&1 < /dev/null &

It undoes a previously killed run from its journal, writes `current + 1` into `BUILD_NUMBER`,
rebuilds the generated pages, runs every lane with every environment required, stamps the gate's
result into the build's notes, builds and clean-installs a wheel, and writes `<dir>/SYNCRAIN<N>.tar.zst`,
verified byte for byte against the tree before it gets its name. The log's last line is
`build <N>: <path>`. A run that raises puts the tree back and spends no number. Keep `<dir>` and
the log outside the tree: a log at its top fails the gate, and an archive inside it would be
committed with it. The tree the release leaves is the archive's, and goes to `main` as the commit
`syncrain build <N>`.

**Every archive that leaves this machine bumps the build number**, and `tools/package_release.py`
is the only thing that makes one: never a patch, never a hand-made tar, never `BUILD_NUMBER`
edited by hand. Before the command, in the same pass as the change: write the build's notes with
the literal token GATE_RESULT under "## Verification", and rewrite `docs/WHERE_WE_ARE.md`, the
handoff and `docs/agent/NEXT_BUILD.md` (which names the build after it). The gate fails on them.

### Things that will cost you

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

### Where defects cluster

* **Starting OpenGL.** Which API and version GTK gives depends on the GTK and the driver; the
  render and Wayland lanes run with only OpenGL ES, only desktop OpenGL and none at all.
* **The desktop it attaches to.** Layer choice (KDE takes the bottom layer), click-through, monitors
  coming and going, and what the compositor says about covered screens; KWin is in a lane, Plasma's
  shell is not.
* **What the operator's machine runs.** The launcher's module path, preloading, systemd quoting:
  each was right in the sandbox and wrong somewhere else once (`docs/LESSONS.md`).

### Layout

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
    docs/                everything above; images/ holds this page's pictures

## Licence

The code is MIT ([`LICENSE`](LICENSE)). The NixOS snowflake artwork is CC BY 4.0 and NixOS is a
trademark of the NixOS Foundation; the credits are in [`docs/OPERATIONS.md`](docs/OPERATIONS.md),
"Credits and licences".
