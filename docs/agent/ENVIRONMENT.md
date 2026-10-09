# The build sandbox

What every lane needs, how to bring a sandbox up, and its traps. `tools/prepare_environment.sh
--verify` checks a sandbox and changes nothing. The operator's machine: `docs/agent/TARGET_ENVIRONMENT.md`.

## What the lanes need

| Lane | Needs |
| --- | --- |
| unit, contract | Python 3.11+ with PyGObject, Pillow, pycairo, pytest, pyflakes; shellcheck, zstd |
| native | cc, pkg-config, wayland-scanner, libwayland-client/-egl and libdbus-1 headers |
| render | GTK 4.14+ with typelibs, Mesa (llvmpipe is fine), Xvfb |
| wayland | sway, grim, gtk4-layer-shell 1.x with its typelib on `GI_TYPELIB_PATH` |
| kwin | KWin 6 (`SYNCRAIN_KWIN` = its `kwin_wayland`), dbus-daemon, dbus-send, node |
| browser | node with Playwright and its Chromium |
| nix | nix-build; nixpkgs and home-manager checkouts (`SYNCRAIN_NIXPKGS`, `SYNCRAIN_HOME_MANAGER`); a driver in `/run/opengl-driver` |
| release | all of the above, plus setuptools and wheel |

The release runs every lane with `--require-all`: a missing environment fails it.

## Bring-up (Ubuntu 24.04)

1. Packages: `libgtk-4-dev gobject-introspection libcairo2-dev meson xvfb sway grim shellcheck zstd
   gcc pkg-config libwayland-dev libdbus-1-dev`; node 22; Playwright's Chromium; Nix.
2. A venv outside the tree: `pip install PyGObject Pillow pycairo pytest pyflakes "setuptools>=64" wheel`.
3. gtk4-layer-shell v1.3.0 from source (`meson setup build -Dintrospection=true`, `ninja -C build
   install`), then `export GI_TYPELIB_PATH=/usr/local/lib/x86_64-linux-gnu/girepository-1.0`.
4. `npm i -g playwright`.
5. Shallow clones of nixpkgs and home-manager; export their paths.
6. KWin 6: `nix build --no-link --print-out-paths -f "$SYNCRAIN_NIXPKGS" kdePackages.kwin`; export
   `SYNCRAIN_KWIN=<path>/bin/kwin_wayland`. It runs headless with software compositing; a 141 Hz
   screen comes from a `kwinoutputconfig.json` the lane writes (`FAST_SCREEN` in
   `tests/kwin/test_the_kwin_desktop.py`).
7. A driver for Nix's programs:
   `ln -sfn "$(nix build --no-link --print-out-paths -f "$SYNCRAIN_NIXPKGS" mesa)" /run/opengl-driver`
   (again after every restart).
8. Release, with the venv first on `PATH` and the exports above:
   `setsid nohup python3 tools/package_release.py --output <dir> > ../release.log 2>&1 < /dev/null &`
   (about ten minutes on two cores). Keep `<dir>` and the log outside the tree.

Before a build that changes `install.sh`, run it once in a real Arch root (the bootstrap tarball,
pacman with the proxy's CA, a user with sudo, headless Sway inside).

## Traps

* It restarts between turns and keeps only files; the lanes start their own displays.
* `pkill -f` and `pgrep -f` match their own shell, and `pkill` in a chroot reaches the host: use PIDs.
* Two cores and software rendering: a frame now and then takes three times as long, so timing
  tests stay small and judge medians.
* Memory measured here is partly Mesa's llvmpipe; only the operator's machine shows NVIDIA's.
* Unix socket paths over 108 bytes fail: keep runtime directories short.
* GitHub: a session cannot create a repository or push a tag. Attach the repository with push
  access before pushing, or the proxy answers 403.
* A file the release does not know at the tree's top fails the gate (a log included).
* Web fonts cannot load; the browser lane serves empty stylesheets for them.
