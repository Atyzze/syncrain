# The build sandbox

What every lane needs, how to bring a sandbox up, and its traps. `tools/prepare_environment.sh
--verify` checks a sandbox and changes nothing. The operator's machine: `docs/agent/TARGET_ENVIRONMENT.md`.

## What the lanes need

| Lane | Needs |
| --- | --- |
| unit, contract | Python 3.11+ with PyGObject, Pillow, pycairo, pytest, pyflakes; shellcheck, zstd; ffmpeg; node; Python 3.10 or 3.11 beside it (the oldest-Python check) |
| native | cc, pkg-config, wayland-scanner, libwayland-client/-egl and libdbus-1 headers |
| render | GTK 4.14+ with typelibs, Mesa (llvmpipe is fine), Xvfb |
| wayland | sway, grim, gtk4-layer-shell 1.x with its typelib on `GI_TYPELIB_PATH` |
| kwin | KWin 6 (`SYNCRAIN_KWIN` = its `kwin_wayland`), dbus-daemon, dbus-send, node |
| browser | node with Playwright and its Chromium |
| nix | nix-build; nixpkgs and home-manager checkouts (`SYNCRAIN_NIXPKGS`, `SYNCRAIN_HOME_MANAGER`); a driver in `/run/opengl-driver` |
| lockscreen | Nix and `SYNCRAIN_NIXPKGS` (Qt, Plasma's locker, libei), sway, KWin 6 (`SYNCRAIN_KWIN`), dbus-daemon, cc; root, for a PAM service `kde` of the test's own (only where `/etc/pam.d/kde` is not the machine's) |
| release | all of the above, plus setuptools 77 or newer (with packaging 24.2 or newer) and wheel |

The release runs every lane with `--require-all`: a missing environment fails it.

## Bring-up (Ubuntu 24.04)

1. Packages: `libgtk-4-dev gobject-introspection libcairo2-dev meson xvfb sway grim shellcheck zstd
   gcc pkg-config libwayland-dev libdbus-1-dev`; node 22; Playwright's Chromium; Nix.
2. A venv outside the tree: `pip install PyGObject Pillow pycairo pytest pyflakes "setuptools>=77" "packaging>=24.2" wheel cairosvg`
   (CairoSVG draws `logo-syncrain.svg` for `tools/build_logo.py` where there is no rsvg-convert).
3. gtk4-layer-shell v1.3.0 from source (`meson setup build -Dintrospection=true`, `ninja -C build
   install`), then `export GI_TYPELIB_PATH=/usr/local/lib/x86_64-linux-gnu/girepository-1.0`.
4. `npm i -g playwright`.
5. nixpkgs at the revision `flake.lock` pins (`git init`, then `git fetch --depth 1
   https://github.com/NixOS/nixpkgs <rev>` and check it out, or that revision's channel tarball) and
   a shallow clone of home-manager; export their paths. The nix lane holds the two revisions equal.
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
pacman with the proxy's CA and `CheckSpace` off, `pacman -Syu` before anything else (a partial
upgrade breaks GTK), a user with sudo whose sudoers keeps `HTTPS_PROXY`, headless Sway inside). A
Plasma session there: `plasma-workspace kwin`, then in `dbus-run-session`: `kwin_wayland --virtual`,
`/usr/lib/kactivitymanagerd`, `plasmashell`.

The other three families the same way, each in a root of its own (build 31 did all four, Arch too):

* **Debian 13**: `debootstrap --variant=minbase trixie <root> http://deb.debian.org/debian`; apt's
  proxy and CA in `/etc/apt/apt.conf.d/` (`Acquire::https::Proxy`, `Acquire::https::CaInfo`).
* **Fedora**: the `Fedora-Container-Base-Generic` OCI image from dl.fedoraproject.org, its one layer
  unpacked; `proxy=` and `sslcacert=` in `/etc/dnf/dnf.conf`; disable `fedora-cisco-openh264`
  (its host is not reachable from here).
* **openSUSE Tumbleweed**: `opensuse-tumbleweed-image.x86_64-lxc.tar.xz` from
  download.opensuse.org/tumbleweed/appliances; the CA in `/etc/pki/trust/anchors/` then
  `update-ca-certificates`, the proxy in `/etc/sysconfig/proxy` (zypper under sudo reads it there);
  replace its `busybox-diffutils` with `diffutils` first, or Qt's packages conflict.
* In each: `/proc`, `/sys`, `/dev` bound in, a user with sudo, the tree copied in, `./install.sh
  --yes` as that user; then Xvfb and a `--screenshot` against this machine's, `cmake` of
  `syncrain/lockscreen/`, and `--login-screen` then `--login-screen-off` over a fake `sddm.service`
  (KWin installed for its check). Add `127.0.0.1 <hostname>` to the root's `/etc/hosts` for sudo.

## Traps

* It restarts between turns and keeps only files; the lanes start their own displays.
* `pkill -f` and `pgrep -f` match their own shell, and `pkill` in a chroot reaches the host: use PIDs.
* Two cores and software rendering: a frame now and then takes three times as long, so timing
  tests stay small and judge medians.
* Memory measured here is partly Mesa's llvmpipe; only the operator's machine shows NVIDIA's.
* `pip` here is Python 3.13's, the lanes run 3.12 (`/opt/py312shim`): install for the lanes with
  `/opt/py312shim/python3 -m pip install --break-system-packages ...`. Upgrading setuptools with the
  bare `pip` took Debian's shared copy from 3.12 too. setuptools 77 needs packaging 24.2, newer
  than Debian's, which pip cannot uninstall: `--ignore-installed packaging`.
* Unix socket paths over 108 bytes fail: keep runtime directories short.
* GitHub: a session cannot create a repository or push a tag. Attach the repository with push
  access before pushing, or the proxy answers 403.
* A file the release does not know at the tree's top fails the gate (a log included).
* Web fonts cannot load; the browser lane serves empty stylesheets for them.
* Qt writes its messages to the journal unless `QT_FORCE_STDERR_LOGGING=1`.
* On a headless Sway with the pixman renderer, Qt's windows show nothing to grim: the lock screen's
  frames are taken inside Qt (`grabToImage`), and the real lock is judged by KWin's log and PAM.
* KWin 6.7 has no fake input for tests any more: keys go in through libei
  (`org.kde.KWin.EIS.RemoteDesktop.connectToEIS`, one connection per word; `tests/lockscreen/type.c`).
* Ubuntu's g-ir-scanner is Python 3.12's: with another `python3` first, building gtk4-layer-shell's
  typelib needs its first line pointed at `/usr/bin/python3.12`.
* A script named after a standard module replaces it.
* A heredoc ends at its terminator, even inside the text; tool parameters decode JSON escapes. A
  `\u2028` written through a tool lands as the character, which ends a JavaScript regex literal:
  make such escapes in a script (`chr(92) + "u2028"`) and check the page with `node --check`.
* The system's `python3` may not be the one PyGObject was built for (a circular import of `_gi`):
  run the app, outside the lanes too, with the venv of step 2 first on `PATH` and the exports above.
