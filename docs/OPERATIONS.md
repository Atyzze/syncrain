# Operating syncrain

Every option and recipe. How it works: `docs/ARCHITECTURE.md`.

## Install

Needs Linux with GTK 4.14+, OpenGL 3.3 or OpenGL ES 3.0, Python 3.10+ and a synced clock (NTP). On
Wayland, a compositor with layer-shell (not GNOME: use `--window` or the web page there).

**Arch, CachyOS, EndeavourOS, Manjaro**

```sh
git clone https://github.com/Atyzze/syncrain && cd syncrain   # or unpack SYNCRAIN<N>.tar.zst
./install.sh                  # pacman packages (sudo once), then everything in ~/.local
./install.sh --autostart      # also a systemd user service
./install.sh --uninstall      # remove it (the pacman packages stay)
```

* Packages: `python python-gobject python-cairo python-pillow gtk4 gtk4-layer-shell`, plus
  `gcc pkgconf wayland dbus` to build the native wallpaper. If that build fails, the installer says
  why and Python and GTK draw instead.
* `--theme`, `--channel`, `--rainbow` and `--arg ...` (repeatable) go into the autostart service.
* Upgrading: run the newer `./install.sh`; it names the build it replaces and restarts the
  wallpaper. `syncrain --build` says what is installed.

**NixOS** (flake): `services.syncrain = { enable = true; theme = "nixos"; channel = "public"; };`
with `syncrain.nixosModules.default` (or `homeManagerModules.default`). Options: `enable`,
`package`, `theme`, `channel`, `fps`, `logo`, `background`, `mask`, `rainbow`, `spin`, `drift`,
`scale`, `pauseUnder`, `layer`, `extraArgs` (`nix/options.nix`). Without installing:
`nix run github:Atyzze/syncrain -- --window`.

**Other systems**: GTK 4, gtk4-layer-shell, PyGObject, pycairo and Pillow, then `pip install .`.
For the native wallpaper: `sh syncrain/native/build.sh <path>` and `SYNCRAIN_WALLPAPER=<path>` in
the session's environment.

**Browser**: `web/index.html`, one self-contained file. URL parameters: `theme`, `channel`, `fps`,
`logo`, `rainbow`, `spin`, `drift`, `scale`, `hud=0` (no control strip), `t=<unix seconds>`
(frozen clock). A Plasma web-wallpaper plugin can host it, behind the desktop icons.

## Options

| Flag | Default | Meaning |
| --- | --- | --- |
| `--theme` | `nixos` | `nixos` or `matrix`; `--list-themes` prints them |
| `--channel` | `public` | Stream name: same name, synced clock, same frame |
| `--fps` | `30` | Cap; frames land on whole refreshes (every 2nd at 60 Hz) |
| `--host` | `auto` | Wayland: `auto` (native when built, else GTK), `native` (only), `gtk` |
| `--pause-under` | `maximized` | KDE: stop a screen under a maximized or full-screen window; `fullscreen`, `never` |
| `--logo` | theme | `white`, `colours` or `none` |
| `--background IMAGE` | - | An image instead of the gradient, darkened by `--bg-gamma` (2.0) and `--bg-gain` (0.42) |
| `--mask IMAGE` | - | Greyscale mask for the background: white stays bright, rain passes behind |
| `--rainbow` | `logo` | `logo`, `all` (the rain too) or `off` |
| `--spin S` | `180` | Seconds per logo turn; 0 = still |
| `--drift F` | `0.03` | Logo orbit (or image pan) in screen heights; 0 = fixed |
| `--scale` | `1.0` | Render resolution scale (0.75 on a weak GPU) |
| `--layer` | auto | `background` or `bottom`; auto is `bottom` on KDE |
| `--window` | - | A normal window instead of the wallpaper |
| `--size WxH` | `1280x720` | Size for `--window`, `--record` and `--benchmark` |
| `--offset S` | `0` | Add S seconds to the clock |
| `--time T` | - | Freeze the clock at UNIX time T |
| `--screenshot PNG` | - | Draw one frame, save it, exit |
| `--record DIR` | - | Save `--record-seconds` (8) at `--record-fps` (30) as PNGs |
| `--diagnose` | - | What this machine offers and why syncrain can or can't draw |
| `--benchmark` | - | GPU time of each pass on this card |
| `--power-sweep` | - | The card's watts at several settings, about four minutes |
| `--sweep-seconds S` | `25` | Seconds per sweep phase |
| `--build` | - | The build number and the stream id |

Environment: `SYNCRAIN_DEBUG_FPS=<s>` reports each screen's frame rate and timing ("even" and
"steady" near 100% means smooth); `SYNCRAIN_GL_DEBUG=1` checks every OpenGL call;
`SYNCRAIN_WALLPAPER=<path>` names the native program; `GSK_RENDERER` picks GTK's renderer.
syncrain sets `__NV_DISABLE_EXPLICIT_SYNC=1` and `__GL_YIELD=USLEEP` for itself unless you set them
(NVIDIA's driver leaks memory per frame with explicit sync on).

## When it does not draw

`syncrain --diagnose`, inside the desktop session: a verdict first, then the session, libraries,
cards, OpenGL, screens, the native wallpaper and, on KDE, KWin's answer about covered screens. If
OpenGL cannot start, syncrain exits with status 69 and the service does not retry.
`journalctl --user -u syncrain` shows the startup line.

## Power and memory

* Measured on the operator's RTX 5090 (two screens): about +11 W at 30 fps, +7 W at 20, +3.5 W at
  15; 0 W behind a covering window. The watts follow the frames.
* `systemctl --user stop syncrain`, then `syncrain --power-sweep`: a phase with nothing, then the
  wallpaper as installed, the GTK host (`--host gtk`), build 4's timer, 20 and 15 fps, and behind a
  maximized and a full-screen window. Per phase: watts, frames, timing, CPU %, MiB, what drew it;
  saved to `~/syncrain-power-<utc>.json`. Power comes from `nvidia-smi`, the amdgpu sensor, or
  `SYNCRAIN_POWER_COMMAND`.
* **The last two phases turn every screen black** for about a minute (a covering window). The sweep
  warns first. To get the screens back sooner, Alt+Tab to its terminal and press Ctrl+C.
* Memory: the native wallpaper keeps about 123 MiB on that card, the GTK host 205.

## Desktops

| Desktop | How | Tested |
| --- | --- | --- |
| Hyprland, Sway, river, niri, Wayfire, labwc, COSMIC | background layer | headless Sway, every release |
| KDE Plasma 6 | bottom layer (above Plasma's desktop, covering its icons); covered screens not drawn | headless KWin, every release |
| X11 | a desktop window over all monitors | Xvfb, every release |
| GNOME | no layer-shell: `--window` or the web page | no |

## Recipes

* **A video**: `syncrain --time 1791331200 --record /tmp/frames --size 1920x1080`, then
  `ffmpeg -framerate 30 -i /tmp/frames/frame_%05d.png -c:v libx264 -crf 17 -pix_fmt yuv420p rain.mp4`.
* **The README's pictures** (`docs/images/`; redo when the stream changes): under Xvfb with
  `GDK_BACKEND=x11`, `syncrain --window --size 1600x900 --time 1791331207 --screenshot nixos.png`
  (and `--theme matrix`); save as JPEG with Pillow, `quality=90, subsampling=0, progressive=True`.
* **The CachyOS look**: `syncrain --theme matrix --background <nebula.png> --mask extras/cachyos-logo-mask.png`.
* **New assets**: `python3 tools/build_assets.py --nixos-artwork <checkout>`, then
  `python3 tools/build_web.py`; a new atlas or theme changes the stream.

## Credits and licences

Code: MIT (`LICENSE`). The NixOS snowflake: Simon Frankau and Tim Cuthbertson (NixOS/nixos-artwork),
CC BY 4.0; NixOS is a trademark of the NixOS Foundation. Glyphs from Noto Sans Mono CJK JP (OFL 1.1)
and DejaVu Sans. Wayland protocol files in `syncrain/native/protocols/`: wayland-protocols and
wlr-protocols, MIT-style, as each file says.
