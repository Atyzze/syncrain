# Agent environment bring-up

What a build sandbox needs to run every lane, the sequence that worked for build 3, and the traps.
Check a sandbox first with `tools/prepare_environment.sh --verify` (it changes nothing and prints
what is missing and the exports the lanes need). The machines syncrain runs on are
`docs/agent/TARGET_ENVIRONMENT.md`.

## 0 What the lanes need

| Lane | Needs |
| --- | --- |
| unit, contract | Python 3.11 or later with PyGObject, Pillow, pycairo, pytest, pyflakes; bash, shellcheck, zstd; the native lane's tools for the installer's test |
| native | a C compiler, pkg-config, wayland-scanner, and the libwayland-client, libwayland-egl and libdbus-1 headers (Ubuntu: `gcc pkg-config libwayland-dev libdbus-1-dev`; Arch: `gcc pkgconf wayland dbus`) |
| render | the unit lane's, GTK 4.14 or later with its typelibs, Mesa (llvmpipe is fine), Xvfb |
| wayland | the above and the native lane's, sway, grim, gtk4-layer-shell 1.x and its typelib on `GI_TYPELIB_PATH` |
| kwin | the wayland lane's GTK side, KWin 6 (`SYNCRAIN_KWIN`: the path of `kwin_wayland`), `dbus-daemon` and `dbus-send`, node (the KWin script's unit test runs in it) |
| browser | node with Playwright, and Playwright's Chromium (`PLAYWRIGHT_BROWSERS_PATH`) |
| nix | nix-instantiate and nix-build; local checkouts of nixpkgs and home-manager named by `SYNCRAIN_NIXPKGS` and `SYNCRAIN_HOME_MANAGER`; sway and grim, and an OpenGL driver where Nix's programs look for one (`/run/opengl-driver`, step 8) |
| release | all of the above, plus setuptools and wheel in the same Python |

The release runs `tools/test_suite.py --lane all --require-all`: a missing environment fails the
release instead of skipping. A lane that skips on the release machine never ran.

## 1 The sequence that worked (build 3: Ubuntu 24.04, GTK 4.14.5, Mesa 25.2 llvmpipe)

1. **System packages** were present: `libgtk-4-dev`, `libgirepository-2.0-dev`,
   `libgirepository1.0-dev`, `gobject-introspection`, `libcairo2-dev`, `meson`, `xvfb`, `sway`,
   `grim`, `shellcheck`, `zstd`; node 22 in `/opt/node22/bin`; Playwright's Chromium in
   `/opt/pw-browsers`; Nix in `/nix/var/nix/profiles/default/bin`.
2. **A venv outside the tree** with the app's libraries and the tools:
   `python3 -m venv <venv> && <venv>/bin/pip install PyGObject Pillow pycairo pytest pyflakes "setuptools>=64" wheel`.
3. **gtk4-layer-shell from source**, since Ubuntu 24.04 has none: clone
   github.com/wmww/gtk4-layer-shell at v1.3.0, `meson setup build -Dintrospection=true`,
   `ninja -C build install` (into `/usr/local`). If `g-ir-scanner` fails on a Python it cannot
   import from, point its shebang at the system Python that has its modules (3.12 here). Then
   `export GI_TYPELIB_PATH=/usr/local/lib/x86_64-linux-gnu/girepository-1.0`.
4. **Playwright for node**: `npm i -g playwright` if `require('playwright')` fails, with
   `NODE_PATH=$(npm root -g)`; the browser lane finds it through `npm root -g` itself.
5. **Nix checkouts** (GitHub is reachable, cache.nixos.org through the proxy):
   `git clone --depth 1 https://github.com/NixOS/nixpkgs` (build 3 used nixos-unstable at
   151fa4e8, 2026-10-06) and `git clone --depth 1 https://github.com/nix-community/home-manager`;
   export `SYNCRAIN_NIXPKGS` and `SYNCRAIN_HOME_MANAGER` to them.
6. **KWin 6 for the kwin lane**, from the same nixpkgs (Ubuntu 24.04 has only KWin 5.27):
   `nix build --no-link --print-out-paths -f "$SYNCRAIN_NIXPKGS" kdePackages.kwin` fetches KWin
   6.7.5 and its Qt 6 and KDE Frameworks from the binary cache (about 1 GB, a few minutes); export
   `SYNCRAIN_KWIN=<that path>/bin/kwin_wayland`. It runs headless with `--virtual` (software
   compositing, 60 Hz screens), on a private session bus the lane starts; its scripting, its D-Bus
   interface and its layer-shell are the real ones. Plasma's shell is not there. A faster screen
   comes from KWin's own output settings: the lane writes a `kwinoutputconfig.json` with a custom
   mode before KWin starts (`FAST_SCREEN` in `tests/kwin/test_the_kwin_desktop.py`, 141.33 Hz), the
   file KWin itself writes after `kscreen-doctor output.Virtual-0.addCustomMode...` (libkscreen,
   also in nixpkgs, if another mode is wanted).
7. **The native wallpaper's build tools** (build 8): `apt-get install gcc pkg-config libwayland-dev
   libdbus-1-dev` (wayland-scanner comes with libwayland-dev, through libwayland-bin). The lanes
   build the program themselves (`native_wallpaper` in `tests/conftest.py`); by hand,
   `sh syncrain/native/build.sh var/native/syncrain-wallpaper` and `SYNCRAIN_WALLPAPER` naming it.
8. **An OpenGL driver for Nix's programs**, for the nix lane's run of the package's native
   wallpaper: Nix's libglvnd looks for drivers under `/run/opengl-driver`, as on NixOS. Build Mesa
   from the same nixpkgs and link it there:
   `ln -sfn "$(nix build --no-link --print-out-paths -f "$SYNCRAIN_NIXPKGS" mesa)" /run/opengl-driver`
   (the sandbox's `/run` is kept only until it restarts; the link must be made again after one).
9. **The release**, from the tree, with the venv's Python first on `PATH` and the exports above:

```
export PATH=<venv>/bin:/opt/node22/bin:/nix/var/nix/profiles/default/bin:$PATH
export GI_TYPELIB_PATH=/usr/local/lib/x86_64-linux-gnu/girepository-1.0
export SYNCRAIN_NIXPKGS=<nixpkgs checkout> SYNCRAIN_HOME_MANAGER=<home-manager checkout>
export SYNCRAIN_KWIN=<kwin store path>/bin/kwin_wayland
setsid nohup python3 tools/package_release.py --output <dir> > ../release.log 2>&1 < /dev/null &
```

   Build 5's gate took about six minutes on two cores; the browser lane is the slowest
   (Chromium's software WebGL), the kwin lane next (about two and a half minutes since build 6).

## 2 A real Arch root, for the installer

The lanes run `install.sh` against the sandbox's own Python. Before a build that changes the
installer, run it once on real Arch packages, as build 2 and build 3 did:

1. The Arch bootstrap tarball (`archlinux-bootstrap-x86_64.tar.zst` from a mirror reachable through
   the proxy) unpacked into a scratch folder; in it, pacman with the proxy's CA added as a trust
   anchor, `DisableSandbox` and `CheckSpace` off in `pacman.conf`, a mirror in the mirrorlist,
   `pacman-key --init && pacman-key --populate`, then `pacman -Syu base sudo sway grim xorg-server-xvfb`.
2. Mounts without recursion (a recursive bind is refused by the sandbox's safety check):
   `mount --bind /dev`, a tmpfs on `dev/shm`, `mount -t proc proc`, `/sys` bound read-only.
3. A user `tester` with passwordless sudo; run commands with
   `chroot <root> runuser -u tester -- env HOME=/home/tester XDG_RUNTIME_DIR=/tmp/xdg-tester ...`.
4. Headless Sway inside it for Wayland: `WLR_BACKENDS=headless WLR_RENDERER=pixman sway -c <conf>`,
   then `WAYLAND_DISPLAY=wayland-1` for clients and grim for screenshots. Arch had GTK 4.22.5 and
   Mesa 26.2.4 in October 2026; the first Python start in the root takes about ten seconds (no
   bytecode cache is writable).
5. When done: stop the chroot's processes by PID (see the traps), then unmount; a gpg-agent left by
   `pacman-key` keeps `/dev` busy.

## 3 What the sandbox gets wrong

* **It restarts between turns and keeps only files.** Xvfb, Sway and anything detached are gone
  after a pause; the lanes start their own displays, and the release is detached so a restart
  cannot stop it halfway (the journal recovers it if one does).
* **`pkill` in the chroot reaches the host**, which shares the process namespace. Use PIDs.
* **Removals with variables are refused** by the sandbox's safety check (`rm -rf "$X/..."` in a
  compound command). Write into a new folder instead of clearing an old one.
* **Heredocs end at their terminator inside the text**, and tool parameters decode `\u` escapes
  (`docs/LESSONS.md`, "The build sandbox").
* **Web fonts cannot load.** The page asks Google Fonts for its typefaces; the browser lane serves
  empty stylesheets for them so nothing waits.
* **Mesa hides OpenGL bugs other drivers expose**: it shares contexts across OpenGL and OpenGL ES.
  The lanes force each API on its own (`docs/LESSONS.md`, "OpenGL and GTK").
* **Two processors and software rendering**: a 640x360 frame takes 18 ms here. Timing tests use
  screens small enough that the machine keeps up (the kwin lane: 320x180), or they measure the
  machine. Even at 320x180 a frame now and then takes three times as long as usual (llvmpipe and
  KWin's software compositing share the two processors), so the kwin lane judges frame timing by
  the median of six reports, not by the worst.
* **Memory measured here is Mesa's llvmpipe as much as syncrain**: about 130 MiB of the native
  wallpaper's 136 is LLVM and llvmpipe (`docs/build_notes/BUILD8_NOTES.md`). A graphics card's
  driver keeps a different amount; only the operator's machine says how much.
* **The Nix store can be collected.** If `SYNCRAIN_KWIN` points at a path that is gone, build it again
  (step 6); the store path is the same for the same nixpkgs.
* **`python3` may not be the Python that has GTK.** On an Ubuntu 24.04 sandbox whose `python3` was
  3.13 (2026-10-08), Ubuntu's `python3-gi` is built for 3.12 and `import gi` failed. After
  `apt-get update && apt-get install gir1.2-gtk-4.0 python3-gi-cairo python3-opengl python3-pil
  python3-pytest zstd shellcheck`, a venv made with `python3.12 -m venv --system-site-packages`,
  first on `PATH`, ran the unit, contract, render and browser lanes; the installer's tests call
  `python3` from `PATH`.
* **GitHub access is per repository.** A session cannot create a repository or push a tag (HTTP
  403 for both, 2026-10-08). The operator creates the repository and the session attaches it with
  push access (the session's add-repository tool); until then the git proxy refuses a push with
  403, "not in this session's authorized repository set" (2026-10-09). Then pushes to a branch,
  `main` included, go through, from any clone of it.
* **A file the gate does not know at the tree's top fails it**, a release log included
  (`tests/contract/test_the_release_takes_everything.py`). Write the log outside the tree, as the
  command above does, and give `--output` a folder outside it too.
