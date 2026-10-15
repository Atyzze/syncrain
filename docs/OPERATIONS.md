# Operating syncrain

Every option and recipe. How it works: `docs/ARCHITECTURE.md`.

## Install

Needs Linux with GTK 4.14+, OpenGL 3.3 or OpenGL ES 3.0, Python 3.10+ and a synced clock (NTP). On
Wayland, a compositor with layer-shell (not GNOME: use `--window` or the web page there).

**Arch, Debian, Fedora and openSUSE** (and their relatives: what os-release says, else the package
tool there is; `SYNCRAIN_FAMILY=arch|debian|fedora|suse` overrides it)

```sh
git clone https://github.com/Atyzze/syncrain && cd syncrain   # or unpack SYNCRAIN<N>.tar.zst
./install.sh                  # the system's packages (sudo once), then everything in ~/.local
./install.sh --autostart      # also a systemd user service
./install.sh --login-screen   # optional: also the login screen, from the next boot (greetd)
./install.sh --lock-screen    # optional, KDE Plasma 6: also the lock screen, from the next login
./install.sh --config config.json   # the settings the web page saved (see below)
./install.sh --uninstall      # remove it (the system's packages stay)
```

* Packages, by family (`set_packages` in `install.sh`):

  | Family | The app | The native wallpaper's build | `--lock-screen` | `--login-screen` |
  | --- | --- | --- | --- | --- |
  | Arch | `python python-gobject python-cairo python-pillow gtk4 gtk4-layer-shell` | `gcc pkgconf wayland dbus` | `cmake make qt6-base qt6-declarative` | `greetd greetd-agreety` |
  | Debian | `python3 python3-gi python3-gi-cairo python3-cairo python3-pil gir1.2-gtk-4.0 gir1.2-gtk4layershell-1.0` | `gcc pkgconf libwayland-dev libdbus-1-dev` | `cmake make g++ qt6-base-dev qt6-declarative-dev` | `greetd` |
  | Fedora | `python3 python3-gobject python3-cairo python3-pillow gtk4 gtk4-layer-shell` | `gcc pkgconf-pkg-config wayland-devel dbus-devel` | `cmake make gcc-c++ qt6-qtbase-devel qt6-qtdeclarative-devel` | `greetd` |
  | openSUSE | `python3 python3-gobject python3-gobject-cairo python3-cairo python3-Pillow typelib-1_0-Gtk-4_0 typelib-1_0-Gtk4LayerShell-1_0` | `gcc pkgconf-pkg-config wayland-devel dbus-1-devel` | `cmake make gcc-c++ qt6-base-devel qt6-declarative-devel` | `greetd greetd-agreety` |

  gtk4-layer-shell is asked for on its own: where a release lacks it (Ubuntu 24.04, openSUSE Leap
  16.0) the install goes on, and on Wayland the native wallpaper draws. If the native wallpaper
  does not build, the installer says why and Python and GTK draw instead. A tool that cannot
  install says what to try (its index is often old on a fresh system: update it first).
* greetd's user is the one its family's package names (`greeter` on Arch and openSUSE, `_greetd` on
  Debian, `greetd` on Fedora), its text login wherever it is (`/usr/sbin/agreety` on Debian). What
  starts at boot is seen before greetd is installed (Debian's package makes itself what starts at
  boot where nothing did) and recorded once greetd is in, so a run that stops leaves no record.
* Elsewhere: `./install.sh` names what to install by hand, then `./install.sh --no-deps`; or hand
  the repository to an AI agent to adapt `install.sh`.
* `--preset`, `--channel`, `--rainbow` and `--arg ...` (repeatable) go into the autostart service, the
  lock screen's scene and, on a run with `--login-screen`, the login screen's rain. Also `--prefix
  DIR`, `--no-deps`, `--yes`; `./install.sh --help`.
* `--config FILE`: a settings file from the web page, checked, then kept as
  `~/.config/syncrain/config.json` (one there before is kept as `config.json.before`). The service
  is written again with only the options of that run, so the file decides; the login screen's rain
  gets a copy.
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
* The lock screen is optional too, and KDE Plasma 6 on Wayland only. `--lock-screen` gives Plasma's
  own locker syncrain's screen: the rain, live, and syncrain's box (your name, the password, Unlock,
  PAM's words) on every screen. The box comes up on a key or a moved pointer, goes after a minute
  without either and forgets what was typed (Escape sends it away at once); every screen shows the
  same box, so it never matters which one you type on. It builds a QML module (with the lock screen's packages above) into
  `~/.local/lib/syncrain/`, puts the shell package `org.syncrain.lockscreen` in
  `~/.local/share/plasma/shells/`, writes the scene to `~/.local/state/syncrain/lock-screen.scene`
  (each start of the native wallpaper keeps it current), and gives KWin's unit alone a drop-in
  (`plasma-kwin_wayland.service.d/syncrain-lock-screen.conf`) naming the package. Log out and back
  in once. Unlocking is still Plasma's PAM service `kde`; without the module the box shows on black,
  and a lock screen that cannot load is Plasma's built-in one. Should it ever not unlock:
  Ctrl+Alt+F3, log in, `loginctl unlock-sessions`. A plasmashellrc that spells out Plasma's own shell
  package has that line taken out (it would win over the drop-in), and one naming another package
  stops `--lock-screen` with nothing changed. `--lock-screen-off` takes those files away and puts
  the line back; `--uninstall` too. What KWin starts (Xwayland, an input method) also sees the drop-in's
  variables, and its `QML_IMPORT_PATH` replaces one the session had; Plasma's shell, started by
  systemd, does not see them (were it to, it would open a fresh desktop layout).
* Upgrading: run the newer `./install.sh`; it names the build it replaces and restarts the
  autostart service if it runs. `syncrain --build` says what is installed.

**NixOS** (flake): `services.syncrain = { enable = true; settings = ./config.json; };` with
`syncrain.nixosModules.default` (or `homeManagerModules.default`): the wallpaper as a user service.
`settings` takes the page's `config.json`; every other option, with its range, is in
`nix/options.nix` (some ranges are narrower than the command line's: `scale` up to 1, `fps` up to
240). Without installing: `nix run github:Atyzze/syncrain -- --window`.

**The flavour**: `nix flake init -t github:Atyzze/syncrain` makes a flake for a whole NixOS
desktop (`nix/template/`: its README says the five steps): `syncrain.nixosModules.backdrop`
(`nix/backdrop.nix`: Plasma 6, the rain as wallpaper, login screen and lock screen, SDDM off, a
network, sound, the clock in sync; every one a default) with your hardware and boot loader.

On a Plasma 6 system (`services.desktopManager.plasma6.enable`), the NixOS module also gives the
login and lock screens:

```nix
services.syncrain = {
  enable = true;
  settings = ./config.json;
  loginScreen = { enable = true; user = "alice"; };   # greetd runs the rain and the box; SDDM off
  lockScreen.enable = true;                           # Plasma's locker shows the rain and the box
};
services.displayManager.sddm.enable = false;
```

* `loginScreen`: greetd runs `login.sh` from a folder the module builds (the app, its build and
  `login.json`: `user` offered first, `session` offered first (`services.displayManager.defaultSession`,
  else `plasma`), the rain with the wallpaper's options) as `greeter`, with Plasma's KWin, the
  package's Python (`libexec/syncrain/python3`) and greetd's text login if the box fails. KDE's
  wallet opens through the login PAM service Plasma sets up. Not there: automatic login (it says
  so), and the still frame of the rain after a login (`install.sh`'s hand-over).
* Follow the system's nixpkgs (`inputs.syncrain.inputs.nixpkgs.follows = "nixpkgs"`), so the
  package's graphics libraries match the system's driver.
* `lockScreen`: a drop-in for KWin's unit alone names syncrain's shell package (in the system's
  `share/plasma/shells`) and QML module; the wallpaper writes the lock screen's scene before each
  start. A `plasmashellrc` that names a `ShellPackage` wins over it (`install.sh --lock-screen` takes
  out one that names Plasma's own; on NixOS, delete that line by hand), and Plasma must start
  through systemd (its default). The home-manager module has neither.

**Other systems**: GTK 4, gtk4-layer-shell, PyGObject, pycairo and Pillow, then `pip install .`.
For the native wallpaper: `sh syncrain/native/build.sh <path>` and `SYNCRAIN_WALLPAPER=<path>` in
the session's environment.

**Browser**: `index.html` at the top of the folder, one self-contained file; Settings tries every
option live and saves them for the desktop (below). As a wallpaper page, URL parameters: `preset`,
`channel`, `fps`, `logo` (`syncrain`, `nixos`, `none`), `logo-size`, `logo-cycle`, `cycle`, `flavours`, `flavour-layout`,
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
| `--cycle S` | preset's | Seconds a turn of the colour wheel, every flavour together (an RGB keyboard's rainbow); 0 = the colours stay, else 10 or more |
| `--background-colors C,C,C` | preset's | The background gradient: top, bottom, centre glow |
| `--vignette F` | preset's | How much darker the corners are, 0 to 1 |
| `--logo` | preset's | `syncrain`, `nixos`, `none`, or a picture file (PNG, JPEG, WebP: what Pillow reads) |
| `--logo-color C` | its own | One colour over the logo's shape, any logo or picture; `own` for its own colours |
| `--logo-size F` | preset's | The logo's height in screen heights, 0.05 to 0.9 |
| `--logo-cycle S` | preset's | Seconds a turn of the logo's rainbow (over its colour); 0 = its own colours, else 10 or more |
| `--words W,W` | preset's | The hidden words and sentences that fall now and then, up to 32, each up to 30 characters (on a 21:9 screen, 21 fall); a space falls as a gap (`--words=` for none) |
| `--background IMAGE` | - | An image instead of the gradient, darkened by `--bg-gamma` (2.0) and `--bg-gain` (0.42) |
| `--mask IMAGE` | - | Greyscale mask for the background: white stays bright, rain passes behind |
| `--rainbow` | `logo` | The earlier spelling: `all` is `--cycle 600`, `off` is `--logo-cycle 0` |
| `--spin S` | preset's (300; 180 nixos, matrix) | Seconds per logo turn; 0 = still, else 10 or more |
| `--drift F` | preset's (0; 0.03 nixos, matrix) | Logo orbit (or image pan) in screen heights; 0 = fixed |
| `--bg-gain F` | preset's (0.6; 1 nixos, matrix) | Background brightness; lower is darker (0.42 with `--background`) |
| `--glow F` | preset's (0.5; 1 nixos, matrix) | Glow around the centre and the logo, 0 (none) to 2 |
| `--bloom F` | `1` | Glow around the falling symbols, 0 (none) to 2 |
| `--speed F` | `1` | Fall speed, 0.25 to 4 |
| `--density F` | preset's (1.15; 1 nixos, matrix) | How often a column starts a stream, 0 to 2.3 |
| `--snow` | preset's | `on` or `off`: the falling snowflakes (on for syncrain and nixos, off for matrix) |
| `--hieroglyphs F` | sets' | Share of the changing symbols that are Egyptian hieroglyphs (the presets: 0.15) |
| `--config FILE` | see below | A settings file (the web page saves one); `none` for none. Options given go over it |
| `--check-config` | - | Read the settings file and the options, say what they come to, exit (2 if wrong) |
| `--glyphs FILE` | see below | A symbols file; `theme` for the preset's own symbols |
| `--write-glyphs` | - | Write a starter symbols file (a bit of everything) and exit |
| `--scale` | `1.0` | Render resolution scale, up to 4 (0.75 on a weak GPU) |
| `--layer` | auto | `background` or `bottom`; auto is `bottom` on KDE |
| `--window` | - | A normal window instead of the wallpaper |
| `--size WxH` | `1280x720` | Size for `--window` and `--record`; of `--video` (1920x1080, a GIF 640x360); for `--benchmark` (default: the first screen) |
| `--offset S` | `0` | Add S seconds to the clock |
| `--time T` | - | Freeze the clock at UNIX time T |
| `--screenshot PNG` | - | Draw one frame, save it, exit |
| `--record DIR` | - | Save `--record-seconds` (8) at `--record-fps` (30) as PNGs |
| `--video FILE` | - | A video of the rain from `--time` or now: `.mp4`, `.mkv`, `.webm` or `.gif` (needs ffmpeg) |
| `--seconds N` | `30` (a GIF 10) | How long `--video` is |
| `--video-fps F` | `30` (a GIF 15, at most 50) | Frames per second of `--video` |
| `--loop` | `on` | `--video` ends where it begins, so a player repeating it shows no seam; `off` for the moments only |
| `--diagnose` | - | What this machine offers and why syncrain can or can't draw |
| `--benchmark` | - | GPU time of each pass on this card |
| `--power-sweep` | - | The card's watts at several settings, about four minutes |
| `--sweep-seconds S` | `25` | Seconds per sweep phase |
| `--build` | - | The build number and the stream id |

Environment: `SYNCRAIN_DEBUG_FPS=<s>` reports each screen's frame rate and timing ("even" and
"steady" near 100% means smooth); `SYNCRAIN_GL_DEBUG=1` checks every OpenGL call;
`SYNCRAIN_WALLPAPER=<path>` names the native program; `GSK_RENDERER` picks GTK's renderer.
syncrain sets `__NV_DISABLE_EXPLICIT_SYNC=1` and `__GL_YIELD=USLEEP` for itself unless you set them.

## Settings from the web page

Open `index.html` (or the live page), press **Settings** and move anything: a preset to start from,
the channel, the rain's colours and how many at once, the colour cycle, the background, the logo
(or a picture of your own), motion, light, the symbol sets (add, remove, weigh, type your own), the
hidden words and sentences, the frame rate. The rain changes as you go; **Screen shape** previews
a 16:9, 21:9 or other desktop. Then **Save config.json** (or **Copy**) and, in the syncrain folder,
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
* **Video** saves what the page shows as WebM: 10 s to 2 min, 720p to 4K (or a phone's 1080x1920),
  24 to 60 fps. Drawn frame by frame, so it takes a while; the rain is hidden and the other settings
  stand still meanwhile, and **Stop** ends it. Chrome, Edge and Firefox make it; Safari may not.
  The same as `syncrain --video` (below, "A video").
* Options on the command line go over the file. **Open a settings file** (or drop one on the page)
  shows one again; a symbols file (`glyphs.json`) loads as the sets.

## Your own symbols

`syncrain --write-glyphs` writes `~/.config/syncrain/glyphs.json`, used when it is there and no
settings file names sets (the page's always does, and wins):

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

* On the operator's machine (`docs/agent/TARGET_ENVIRONMENT.md`): +11.9 W at 30 fps, +7.3 W at 20,
  +3.5 W at 15; 0 W behind a covering window. The watts follow the frames.
* `systemctl --user stop syncrain`, then `syncrain --power-sweep`: a phase with nothing, then the
  wallpaper as installed, the GTK host (`--host gtk`), build 4's timer, 20 and 15 fps, and behind a
  maximized and a full-screen window. Per phase: watts, frames, timing, CPU %, MiB, what drew it;
  saved to `~/syncrain-power-<utc>.json`. Power comes from `nvidia-smi`, the amdgpu sensor, or
  `SYNCRAIN_POWER_COMMAND`.
* **The last two phases turn every screen black** for about a minute (a covering window). The sweep
  warns first. To get the screens back sooner, Alt+Tab to its terminal and press Ctrl+C.
* Memory: both hosts hand freed memory back every five minutes. The native one writes `~/.local/state/syncrain/memory.log` (a line
  an hour); `syncrain --diagnose` shows its end and every running wallpaper.

## Desktops

| Desktop | How | Tested |
| --- | --- | --- |
| Hyprland, Sway, river, niri, Wayfire, labwc, COSMIC | background layer | headless Sway, every release |
| KDE Plasma 6 | bottom layer (above Plasma's desktop, covering its icons); covered screens not drawn | headless KWin, every release |
| X11 | a desktop window over all monitors | Xvfb, every release |
| GNOME | no layer-shell: `--window` or the web page | no |
| Login screen (greetd, Arch) | KWin, the rain and a box on the overlay layer | headless KWin, every release |
| Lock screen (KDE Plasma 6) | Plasma's locker loads syncrain's shell package: the rain and the box | headless KWin locked and unlocked through PAM, every release |

## Recipes

* **A video**: `syncrain --video rain.mp4` (30 s at 1920x1080, a seamless loop, your settings
  file's look); `--seconds 60 --size 3840x2160 --video-fps 60` for more, `rain.gif` for a GIF
  (10 s at 640x360 and 15 fps: a GIF of rain is large, and a big one is refused). Its first two
  seconds are the end fading into the start; `--loop off` leaves that out. It is made as
  `rain.part.mp4` and named when whole: Ctrl+C or a failure leaves nothing, and an earlier
  `rain.mp4` as it was. A video repeats where the live rain never does; whether it costs fewer
  watts is not measured yet.
* **Frames as pictures**: `syncrain --time 1791331200 --record /tmp/frames --size 1920x1080`.
* **The README's pictures** (`docs/images/`; redo when the stream changes): under Xvfb with
  `GDK_BACKEND=x11`, `syncrain --config none --window --size 1600x900 --time 1791331207 --screenshot
  syncrain.png` (and `--preset nixos`); save as JPEG with Pillow, `quality=90, subsampling=0, progressive=True`.
* **An RGB keyboard's rainbow**: `syncrain --flavours 64 --flavour-layout wave --cycle 20` (a rainbow
  across the screen, turning every 20 s); `--flavours 6 --cycle 60` for six colours by the channel.
* **A picture behind the rain**: `syncrain --background <picture.png>`, with `--mask <mask.png>` to
  keep part of it bright and the rain behind it.
* **syncrain's logo**: `syncrain/data/logo-syncrain.svg` is its drawing; after a change,
  `python3 tools/build_logo.py` makes the texture (and the stream changes).
* **New assets**: `python3 tools/build_assets.py --hieroglyph-font <NotoSansEgyptianHieroglyphs.ttf>
  --arabic-font <NotoSansArabic-Bold.ttf>` (add `--nixos-artwork <checkout>` to redraw the NixOS
  logo), then `python3 tools/build_web.py`; a new atlas or preset changes the stream.

## Credits and licences

Code: MIT (`LICENSE`). syncrain's logo (`syncrain/data/logo-syncrain.svg`): the operator's, drawn
from their picture. The NixOS snowflake: Simon Frankau and Tim Cuthbertson (NixOS/nixos-artwork),
CC BY 4.0; NixOS is a trademark of the NixOS Foundation. Glyphs from Noto Sans Mono CJK JP (OFL 1.1)
and DejaVu Sans; Arabic from Noto Sans Arabic (OFL 1.1); Egyptian hieroglyphs from Noto Sans
Egyptian Hieroglyphs (OFL 1.1). Wayland
protocol files in `syncrain/native/protocols/`: wayland-protocols and wlr-protocols, MIT-style, as
each file says.
