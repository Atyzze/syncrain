# syncrain

A live code-rain wallpaper that never loops and stays in sync across machines: every frame is a
function of the UTC clock and a channel name. Two themes, **nixos** (blue rain, snow, the NixOS
snowflake) and **matrix** (green). A wallpaper on Linux (Wayland, X11) and a web page.

<p align="center">
  <img src="docs/images/nixos.jpg" width="49%" alt="The nixos theme: pale blue characters falling in columns over dark blue, with snowflakes and the NixOS snowflake in rainbow colours in the middle">
  <img src="docs/images/matrix.jpg" width="49%" alt="The matrix theme: green katakana, digits and letters falling in columns over black">
</p>
<p align="center"><sub>The channel <code>public</code> at 2026-10-07 00:00:07 UTC.
<code>syncrain --window --time 1791331207</code> draws that moment on any machine.</sub></p>

## Try it

Arch, CachyOS, EndeavourOS, Manjaro:

```sh
git clone https://github.com/Atyzze/syncrain && cd syncrain
./install.sh                 # pacman packages, then the app in ~/.local
syncrain --window            # in a window
syncrain                     # as your wallpaper (Ctrl+C stops it)
./install.sh --autostart     # start it with every login
```

* **NixOS**: `nix run github:Atyzze/syncrain -- --window`; the flake has NixOS and home-manager modules.
* **Browser**: open `web/index.html`.

Options, other systems, power and recipes: [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

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
browser (Chromium), nix. What each needs: `docs/agent/ENVIRONMENT.md`.

**What costs you if you get it wrong**

* Only `tools/package_release.py` makes an archive and writes `BUILD_NUMBER`. No version strings.
* The stream is frozen: a change to a shader, a theme, the atlas, a logo or `syncrain/engine.py`
  changes every machine's picture; `tools/stream_freeze.py --write` re-takes it, on purpose only.
* Three hosts draw the same frame: the page (JavaScript), the GTK host (Python) and the native
  wallpaper (C). Change one, change all; the lanes compare them.
* Never ask GTK for an OpenGL version (build 2 drew nothing on NVIDIA).
* systemd unescapes inside single quotes; every service line goes through one quoting function.

### Layout

    syncrain/          app.py (options, GTK host), native.py (starts the native wallpaper), renderer.py,
                       gl.py, pacing.py, hidden.py (KWin), engine.py, build.py, diagnose.py, bench.py,
                       power.py, cover.py, data/ (shaders, themes, atlas, logos)
    syncrain/native/   the native wallpaper in C
    web/               template.html; index.html and artifact.html are generated from it
    nix/               package, web bundle, NixOS and home-manager modules
    tools/             package_release.py, test_suite.py, stream_freeze.py, build_web.py, build_assets.py,
                       prepare_environment.sh
    tests/             one folder per lane; fixtures/stream_freeze.json
    install.sh         the Arch-family installer

## Licence

MIT ([`LICENSE`](LICENSE)). The NixOS snowflake is CC BY 4.0; credits in
[`docs/OPERATIONS.md`](docs/OPERATIONS.md).
