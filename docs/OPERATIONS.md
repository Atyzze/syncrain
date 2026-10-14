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
./install.sh --login-screen   # optional: also the login screen, from the next boot (greetd)
./install.sh --config config.json   # the settings the web page saved (see below)
./install.sh --uninstall      # remove it (the pacman packages stay)
```

* Packages: `python python-gobject python-cairo python-pillow gtk4 gtk4-layer-shell`, plus
  `gcc pkgconf wayland dbus` to build the native wallpaper. If that build fails, the installer says
  why and Python and GTK draw instead.
* `--preset`, `--channel`, `--rainbow` and `--arg ...` (repeatable) go into the autostart service and
  the login screen's rain. Also `--prefix DIR`, `--no-deps`, `--yes`; `./install.sh --help`.
* `--config FILE`: a settings file from the web page, checked, then kept as
  `~/.config/syncrain/config.json` (one there before is kept as `config.json.before`). The service
  is written again without options, so the file decides; the login screen's rain gets a copy.
* Builds 13 and 14's Plasma wallpaper (dropped in build 15) is removed by any later install.
* The login screen is optional. Until `--login-screen` is run, the installer never touches how the
  machine logs in: installing, upgrading and removing the wallpaper leave the display manager,
  what starts at boot and their files as they are.
* `--login-screen`: greetd instead of SDDM (or Plasma Login); the rain and the same box on every
  screen, then Plasma, with its splash and wallpaper a still frame of the rain. Only greetd's
  `[default_session]` changes; what PAM asks after the password (a second factor) is asked in the
  box. If it fails (or after "Text login" in the box), greetd's text login asks. What started at
  boot before is kept in `/etc/greetd/display-manager.before-syncrain`. The installs of the user
  who set it up keep it current, and their `--uninstall` takes it out; other users' leave it alone.
* Back: `./install.sh --login-screen-off` puts back what started at boot before (SDDM, Plasma Login,
  greetd's own login, or none) and greetd's config and PAM file. A display manager picked since
  stays; one removed since leaves greetd with its own config; if systemctl fails otherwise, running
  it again finishes. Where syncrain's login screen is not installed, it changes nothing.
* From a text console (Ctrl+Alt+F3), with SDDM or Plasma Login recorded: `sudo systemctl enable
  --force` and its unit, then `sudo reboot`. `--diagnose` shows the record and the last starts.
* Upgrading: run the newer `./install.sh`; it names the build it replaces and restarts the
  autostart service if it runs. `syncrain --build` says what is installed.

**NixOS** (flake): `services.syncrain = { enable = true; theme = "nixos"; channel = "public"; };`
with `syncrain.nixosModules.default` (or `homeManagerModules.default`). Options: `enable`,
`package`, `settings` (a `config.json` from the page), `theme` (the preset), `channel`, `fps`,
`rainColors`, `glowColor`, `backgroundColors`, `vignette`, `flavours`, `flavourLayout`, `cycle`,
`logo` (a name or a picture), `logoColor`, `logoSize`, `logoCycle`, `words`, `background`, `mask`, `rainbow`,
`spin`, `drift`, `speed`, `density`, `glow`, `bloom`, `bgGain`, `snow`, `hieroglyphs`, `scale`,
`pauseUnder`, `layer`, `extraArgs` (`nix/options.nix`). Without installing:
`nix run github:Atyzze/syncrain -- --window`.

**Other systems**: GTK 4, gtk4-layer-shell, PyGObject, pycairo and Pillow, then `pip install .`.
For the native wallpaper: `sh syncrain/native/build.sh <path>` and `SYNCRAIN_WALLPAPER=<path>` in
the session's environment.

**Browser**: `index.html` at the top of the folder, one self-contained file; Settings tries every
option live and saves them for the desktop (below). As a wallpaper page, URL parameters: `preset`,
`channel`, `fps`, `logo` (`syncrain`, `nixos`, `nixos-colours`, `none`), `logo-size`, `logo-cycle`, `cycle`, `flavours`, `flavour-layout`,
`vignette`, `spin`, `drift`, `speed`, `density`, `glow`, `bloom`, `bg-gain`, `snow=off`,
`hieroglyphs`, `scale`, `hud=0` (no control strip or settings), `t=<unix seconds>` (frozen clock).
A Plasma web-wallpaper plugin can host it, behind the desktop icons.

## Options

| Flag | Default | Meaning |
| --- | --- | --- |
| `--preset` | `syncrain` | Where the look starts: `syncrain`, `nixos` or `matrix` (`--theme` is the earlier name); `--list-themes` prints them |
| `--channel` | `public` | Stream name: same name, synced clock, same frame |
| `--fps` | `30` | Cap; frames land on whole refreshes (every 2nd at 60 Hz) |
| `--host` | `auto` | Wayland: `auto` (native when built, else GTK), `native` (only), `gtk` |
| `--pause-under` | `maximized` | KDE: stop a screen under a maximized or full-screen window; `fullscreen`, `never` |
| `--rain-colors C,C,C,C` | preset's | The rain's gradient, dark, middle, bright, then the leading symbol: `#rrggbb` (or `r/g/b`, 0 to 1) |
| `--glow-color C` | preset's | The glow round the rain |
| `--flavours N` | preset's | Colours at once, 1 to 64: each column one of N hues round the colour wheel |
| `--flavour-layout` | preset's | `random`: the columns' hues by the channel; `wave`: in order across the screen |
| `--cycle S` | preset's | Seconds a turn of the colour wheel, every flavour together (an RGB keyboard's rainbow); 0 = the colours stay |
| `--background-colors C,C,C` | preset's | The background gradient: top, bottom, centre glow |
| `--vignette F` | preset's | How much darker the corners are, 0 to 1 |
| `--logo` | preset's | `syncrain`, `nixos`, `nixos-colours`, `none`, or a picture file (PNG or JPEG) |
| `--logo-color C` | its own | One colour over the logo's shape, any logo or picture; `own` for its own colours |
| `--logo-size F` | preset's | The logo's height in screen heights, 0.05 to 0.9 |
| `--logo-cycle S` | preset's | Seconds a turn of the logo's rainbow (over its colour); 0 = its own colours |
| `--words W,W` | preset's | The hidden words that fall now and then (`--words=` for none) |
| `--background IMAGE` | - | An image instead of the gradient, darkened by `--bg-gamma` (2.0) and `--bg-gain` (0.42) |
| `--mask IMAGE` | - | Greyscale mask for the background: white stays bright, rain passes behind |
| `--rainbow` | `logo` | The earlier spelling: `all` is `--cycle 600`, `off` is `--logo-cycle 0` |
| `--spin S` | `180` | Seconds per logo turn; 0 = still |
| `--drift F` | `0.03` | Logo orbit (or image pan) in screen heights; 0 = fixed |
| `--bg-gain F` | `1` | Background brightness; lower is darker (0.42 with `--background`) |
| `--glow F` | `1` | Glow around the centre and the logo, 0 (none) to 2 |
| `--bloom F` | `1` | Glow around the falling symbols, 0 (none) to 2 |
| `--speed F` | `1` | Fall speed, 0.25 to 4 |
| `--density F` | `1` | How often a column starts a stream, 0 to 2.3 |
| `--snow` | preset's | `on` or `off`: the falling snowflakes (on for nixos, off for matrix) |
| `--hieroglyphs F` | sets' | Share of the changing symbols that are Egyptian hieroglyphs (the presets: 0.15) |
| `--config FILE` | see below | A settings file (the web page saves one); `none` for none. Options given go over it |
| `--check-config` | - | Read the settings file and the options, say what they come to, exit (2 if wrong) |
| `--glyphs FILE` | see below | A symbols file; `theme` for the preset's own symbols |
| `--write-glyphs` | - | Write a starter symbols file (a bit of everything) and exit |
| `--scale` | `1.0` | Render resolution scale, up to 4 (0.75 on a weak GPU) |
| `--layer` | auto | `background` or `bottom`; auto is `bottom` on KDE |
| `--window` | - | A normal window instead of the wallpaper |
| `--size WxH` | `1280x720` | Size for `--window` and `--record`; for `--benchmark` (default: the first screen) |
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

## Settings from the web page

Open `index.html` (or the live page), press **Settings** and move anything: a preset to start from,
the channel, the rain's colours and how many at once, the colour cycle, the background, the logo
(or a picture of your own), motion, light, the symbol sets (add, remove, weigh, type your own), the
hidden words, the frame rate. The rain changes as you go; **Screen shape** previews a 16:9, 21:9 or
other desktop. Then **Save config.json** (or **Copy**) and, in the syncrain folder,
`./install.sh --config config.json`.

* The desktop draws what the page showed: the same frame at the same moment on the same channel.
  Symbols that are not among the 489 shipped ones are drawn by each side's fonts and can differ a
  little; the page names them.
* The file is `~/.config/syncrain/config.json`, read at every start; `syncrain --config FILE
  --window` tries one without installing it. It holds every setting written out, the symbol sets
  too, so a symbols file cannot draw others. Colours are `"#rrggbb"`, or three numbers 0 to 1.
* A picture as the logo is made into the logo's texture by the page (a square, the picture in its
  middle two thirds) and kept in the file as a PNG (`data:image/png;base64,...`): the desktop draws
  those very pixels. `--logo FILE` makes one the same way from a file. **Colour** puts one colour
  over any logo's shape (a picture's too), and over its glow.
* **Colours at once**: each column of rain takes one of that many hues, the gradient turned round
  the colour wheel; by the channel (the same columns on every machine) or as a wave across the
  screen. **Colour cycle** turns them all round the wheel together, like an RGB keyboard's rainbow.
  One colour and no cycle is the picture as it always was.
* Options on the command line go over the file. **Open a settings file** (or drop one on the page)
  shows one again; a symbols file (`glyphs.json`) loads as the sets.

## Your own symbols

`syncrain --write-glyphs` writes `~/.config/syncrain/glyphs.json`, used whenever it is there:

```json
{ "balance": "sets",
  "sets": [ { "name": "katakana", "chars": "アイウエオ", "weight": 2 },
            { "name": "arabic",   "chars": "ابتثج",     "weight": 1 },
            { "name": "mine",     "chars": "λ❄𓆙",       "share": 0.1 } ] }
```

* `weight`: how often a set falls next to the others (0 leaves it out); `share`: that fraction of
  all symbols. `balance` `glyphs`: a weight counts for each character, so every symbol is alike.
* Per set, optional: `font` (a family or a file), `size` (of a cell, 0.9), `mirror` (true).
* Up to 16 sets and 640 different symbols. The 489 shipped ones need no font; others come from
  this machine's fonts, and `syncrain --diagnose` lists any no font has.
* Restart syncrain after a change (`systemctl --user restart syncrain` for the service).
* The same file on the same channel gives the same rain everywhere, symbol for symbol; only a
  character that is not shipped looks as each machine's fonts draw it.

## When it does not draw

`syncrain --diagnose`, inside the desktop session: a verdict first, then the session, running
wallpapers, symbols, the login screen, cards, libraries, screens, OpenGL, covered screens (on
Wayland; KWin's answer on KDE) and the native wallpaper. If
OpenGL cannot start, syncrain exits with status 69. The service does not retry that, nor 2 (no
wallpaper layer, or an option it cannot use), 70 (a native wallpaper from another build) or 78 (a
picture or font it cannot use).
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
* Memory: the native wallpaper keeps about 123 MiB on that card, the GTK host 205. Both hand freed
  memory back every five minutes. The native one writes `~/.local/state/syncrain/memory.log` (a line
  an hour); `syncrain --diagnose` shows its end and every running wallpaper.

## Desktops

| Desktop | How | Tested |
| --- | --- | --- |
| Hyprland, Sway, river, niri, Wayfire, labwc, COSMIC | background layer | headless Sway, every release |
| KDE Plasma 6 | bottom layer (above Plasma's desktop, covering its icons); covered screens not drawn | headless KWin, every release |
| X11 | a desktop window over all monitors | Xvfb, every release |
| GNOME | no layer-shell: `--window` or the web page | no |
| Login screen (greetd, Arch) | KWin, the rain and a box on the overlay layer | headless KWin, every release |

## Recipes

* **A video**: `syncrain --time 1791331200 --record /tmp/frames --size 1920x1080`, then
  `ffmpeg -framerate 30 -i /tmp/frames/frame_%05d.png -c:v libx264 -crf 17 -pix_fmt yuv420p rain.mp4`.
* **The README's pictures** (`docs/images/`; redo when the stream changes): under Xvfb with
  `GDK_BACKEND=x11`, `syncrain --config none --window --size 1600x900 --time 1791331207 --screenshot
  syncrain.png` (and `--preset nixos`); save as JPEG with Pillow, `quality=90, subsampling=0, progressive=True`.
* **An RGB keyboard's rainbow**: `syncrain --flavours 64 --flavour-layout wave --cycle 20` (a rainbow
  across the screen, turning every 20 s); `--flavours 6 --cycle 60` for six colours by the channel.
* **A picture behind the rain**: `syncrain --background <picture.png>`, with `--mask <mask.png>` to
  keep part of it bright and the rain behind it.
* **syncrain's logo**: `syncrain/data/logo-syncrain.svg` is its drawing; after a change,
  `python3 tools/build_logo.py` makes the texture (and the stream changes).
* **New assets**: `python3 tools/build_assets.py --hieroglyph-font <NotoSansEgyptianHieroglyphs.ttf>`
  (add `--nixos-artwork <checkout>` to redraw the logos), then `python3 tools/build_web.py`; a new
  atlas or preset changes the stream.

## Credits and licences

Code: MIT (`LICENSE`). syncrain's logo (`syncrain/data/logo-syncrain.svg`): the operator's, drawn
from their picture. The NixOS snowflake: Simon Frankau and Tim Cuthbertson (NixOS/nixos-artwork),
CC BY 4.0; NixOS is a trademark of the NixOS Foundation. Glyphs from Noto Sans Mono CJK JP (OFL 1.1)
and DejaVu Sans; Egyptian hieroglyphs from Noto Sans Egyptian Hieroglyphs (OFL 1.1). Wayland
protocol files in `syncrain/native/protocols/`: wayland-protocols and wlr-protocols, MIT-style, as
each file says.
