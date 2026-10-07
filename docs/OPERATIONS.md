# Operating syncrain

Every recipe and every option, in one place. How it works is `docs/ARCHITECTURE.md`.

## Install

### Arch, CachyOS, EndeavourOS, Manjaro (no NixOS needed)

```sh
tar xf SYNCRAIN<N>.tar.zst && cd syncrain_build_<N>
./install.sh                  # pacman packages (asks for sudo once), then the app in ~/.local
syncrain --window             # try it in a normal window
syncrain                      # run it as your wallpaper; Ctrl+C stops it
./install.sh --autostart      # optional: start it with every graphical login
```

The script installs `python python-gobject python-cairo python-opengl python-pillow gtk4
gtk4-layer-shell` with pacman and puts everything else in your home directory: the app in
`~/.local/share/syncrain`, a launcher at `~/.local/bin/syncrain`, and with `--autostart` a systemd
user service. `--theme`, `--channel`, `--rainbow` and `--arg ...` (repeatable) bake options into
the autostart. If pacman reports missing files, run `sudo pacman -Syu` first.

**Upgrading**: unpack the newer archive and run its `./install.sh`. It says which build it
replaces ("Upgrading syncrain from build 2 to build 3"), keeps the autostart service, and restarts
the wallpaper if it is running. `syncrain --build` says what is installed.

**Removing**: `./install.sh --uninstall` takes the app, the launcher and the service; the pacman
packages stay.

### NixOS (flake)

```nix
{
  inputs.syncrain.url = "path:/path/to/syncrain_build_<N>";   # or a git URL once it is pushed
  inputs.syncrain.inputs.nixpkgs.follows = "nixpkgs";

  outputs = { nixpkgs, syncrain, ... }: {
    nixosConfigurations.myhost = nixpkgs.lib.nixosSystem {
      modules = [
        ./configuration.nix
        syncrain.nixosModules.default
        { services.syncrain = { enable = true; theme = "nixos"; channel = "public"; }; }
      ];
    };
  };
}
```

This installs the `syncrain` command and a systemd user service that starts with
`graphical-session.target`. Plasma and GNOME reach that target on their own; on Hyprland or Sway,
start the session through UWSM or run `systemctl --user start graphical-session.target` from the
compositor's startup. The module keeps `services.timesyncd` on (the NixOS default), since frames
come from the clock. Options: `enable`, `package`, `theme`, `channel`, `fps`, `logo`, `background`,
`mask`, `rainbow`, `spin`, `drift`, `scale`, `pauseUnder`, `layer`, `extraArgs` (`nix/options.nix`).

A home-manager module with the same options is `homeManagerModules.default`. Without installing:
`nix run path:.` (as the wallpaper) or `nix run path:. -- --window`.

### Other distributions

GTK 4, gtk4-layer-shell (for Wayland), PyGObject, pycairo, PyOpenGL and Pillow, then `pip install .`
in the unpacked folder. If gtk4-layer-shell is not preloaded, the app re-executes itself once with
`LD_PRELOAD` set.

### In a browser

`web/index.html` is one self-contained page running the same shaders: open it on two devices on
the same channel and they show the same frame. As a wallpaper page it reads URL parameters:
`?theme=nixos&channel=public&fps=30&logo=white&rainbow=logo&spin=180&drift=0.03&hud=0` (`hud=0`
keeps the control strip hidden behind your icons; `t=<unix seconds>` freezes the clock). On KDE
Plasma, a wallpaper plugin that shows web pages can host it, which keeps the desktop icons on top.

## Options

| Flag | Default | Meaning |
| --- | --- | --- |
| `--theme` | `nixos` | `nixos` or `matrix` (`--list-themes` prints them) |
| `--channel` | `public` | Stream name; the same name and a synced clock give the same frame |
| `--fps` | `30` | Frame-rate cap. Frames land on whole refreshes of the screen: every 2nd at 60 Hz, every 4th at 120 Hz, every 5th at 144 Hz (28.8 fps), never above the cap |
| `--logo` | theme default | `white`, `colours` or `none` (the NixOS logo; `white` follows the logo guide for dark backgrounds) |
| `--background IMAGE` | - | An image instead of the theme gradient, darkened with `--bg-gamma` (2.0) and `--bg-gain` (0.42) |
| `--mask IMAGE` | - | Greyscale mask framed like the background; white areas keep full brightness and the rain passes behind them |
| `--rainbow` | `logo` | `logo`: the logo cycles through the rainbow; `all`: the rain too; `off`: theme colours |
| `--spin S` | `180` | Seconds per logo turn; 0 = still |
| `--drift F` | `0.03` | Slow orbit of the logo (or pan of the image), in screen heights; 0 = fixed |
| `--scale` | `1.0` | Render resolution scale; try 0.75 on a weak GPU |
| `--layer` | auto | `background` or `bottom` (Wayland); auto is `bottom` on KDE Plasma, `background` elsewhere |
| `--pause-under` | `maximized` | On KDE Plasma: stop drawing a screen while a maximized or full-screen window covers it (`maximized`), only while a full-screen one does (`fullscreen`), or `never` ("Power", below) |
| `--window` | - | An ordinary window instead of the wallpaper |
| `--size WxH` | `1280x720` | Window size for `--window` and `--record`; for `--benchmark`, the size it draws at (default: the first screen) |
| `--offset S` | `0` | Add S seconds to the clock (for a clock you know is off) |
| `--time T` | - | Freeze the clock at UNIX time T |
| `--screenshot PNG` | - | Draw one frame, save it, exit |
| `--record DIR` | - | Draw `--record-seconds` (8) at `--record-fps` (30) into DIR as PNGs, from `--time` or now |
| `--list-themes` | - | Print the themes and exit |
| `--diagnose` | - | Check whether syncrain can draw here and print what it found (below) |
| `--benchmark` | - | Time each pass on this machine's graphics card and print the table ("Power", below) |
| `--power-sweep` | - | Measure the card's power with syncrain at several settings, about four minutes ("Power", below) |
| `--sweep-seconds S` | `25` | Seconds per `--power-sweep` phase |
| `--build` | - | Print the build number and the stream id, exit (`--version` says the same) |

`SYNCRAIN_DEBUG_FPS=<seconds>` prints, that often and per screen, the frame rate and how the frames
were timed: `syncrain: 30.0 fps at 2560x1440 (area 0), spacing 2 refreshes 100%, steady 100%, lead
14.3 ms`. "spacing" is the share of frames shown the expected number of refreshes after the one
before; "steady" the share shown the usual delay after the moment they were drawn for (within 2
ms); "lead" how long before its refresh a frame is asked for now, which syncrain adjusts to the
screen and the machine (`docs/ARCHITECTURE.md`). Both shares near 100% means the motion moves by the
same step every frame. With it set, syncrain also says when
a screen is covered and when it shows again. `GSK_RENDERER=vulkan` (or `gl`, the default syncrain
sets) chooses how GTK puts the picture on screen; `SYNCRAIN_GL_DEBUG=1` turns on PyOpenGL's error
checking.

## When it does not draw

```sh
syncrain --diagnose
```

The first line after the build is the verdict ("OK, syncrain can draw here (OpenGL ES 3.2)" or
the reason it cannot); then the session, the library versions, the graphics cards and driver, the
OpenGL context GTK hands out with its vendor and renderer, one test frame, every screen with its
size, scale and refresh rate; on KDE Plasma also
"covering windows": whether KWin answers the script that pauses covered screens, and which screens
are covered right now (run from a maximized terminal, that screen says so). Run it inside the
desktop session and send the whole output. If OpenGL cannot start, the wallpaper closes itself at
once with exit status 69, and the autostart service does not retry.

`journalctl --user -u syncrain` shows the service's startup line (build, stream, the OpenGL it got,
the number of screens) and, on Plasma, "drawing pauses on a screen under maximized and full-screen
windows (KWin)" once KWin has answered.

## Power

A changing wallpaper keeps the graphics card working: on the operator's card (an RTX 5090, two
screens) syncrain build 4 at 30 frames a second costs 10.6 W more than a still picture, about half
of what their GIF wallpaper cost; GTK's Vulkan path (build 3) cost 25.5 W. The watts follow the
number of frames, not the pixels in them: 20 fps costs 6.9 W, 15 fps 5.0 W, 10 fps 3.0 W; half the
resolution saves 1.2 W and no snow 1 W (`docs/build_notes/BUILD4_NOTES.md` has their table). So
syncrain draws nothing nobody can see:

* **A covered screen is not drawn.** KWin keeps asking a wallpaper for frames while a window covers
  it, so on KDE Plasma syncrain asks KWin, through a small script it loads over D-Bus and unloads
  when it stops, which windows cover which screen (`syncrain/hidden.py`). A screen under a
  maximized or full-screen window on the current desktop and activity, not minimized and not made
  see-through by KWin, is not drawn until that window goes; `--pause-under fullscreen` counts only
  full-screen windows, `--pause-under never` none. A window that is see-through by itself (a
  terminal with a translucent background) still counts, so the rain stands still behind it. Sway
  and most other compositors stop asking a hidden wallpaper for frames by themselves.
* **A locked screen or a screen that is off** is not drawn either: KWin stops asking.
* **KWin's "show desktop" hides syncrain too**: to KWin, syncrain's surface is an ordinary window
  (`docs/ROADMAP.md`), so while the desktop is shown Plasma's own wallpaper shows and syncrain
  draws nothing.

What it costs on a given card, setting by setting:

```sh
systemctl --user stop syncrain       # if the autostart service runs; the sweep refuses to measure two
syncrain --power-sweep               # about three minutes; the screens turn black for the last phases
```

It runs, after a phase with no syncrain at all: the wallpaper as installed; build 4's frame timer,
for comparison; 20 and 15 fps; and the wallpaper behind a maximized and behind a full-screen window
(`syncrain/cover.py`). For each it prints the card's power, how far above "nothing" it is, the
frames drawn, how evenly and how steadily they were timed (as `SYNCRAIN_DEBUG_FPS` reports them,
above) and the card's state; the same goes to `~/syncrain-power-<utc>.json`. Give Plasma a still
picture as its wallpaper first, or "nothing" includes whatever that wallpaper costs. Power comes
from `nvidia-smi` (NVIDIA), the amdgpu power sensor (AMD), or any command printing watts named by
`SYNCRAIN_POWER_COMMAND`.

`syncrain --benchmark` says where a frame's work goes on the card: each pass's GPU time at the
screen's size, and the processor time of issuing a frame.

What lowers the cost further, at some smoothness or sharpness: `--fps 20` or `--fps 15` (fewer
frames: the snow and the fading trails move less smoothly, and below about 21 fps the fastest rain
streams sometimes skip a row), `--scale 0.75` (56% of the pixels, slightly softer letters; little
saving, since the cost is per frame).

## Desktops

| Desktop | How it attaches | Checked |
| --- | --- | --- |
| Hyprland, Sway, river, niri, Wayfire, labwc, COSMIC | Wayland background layer | headless Sway, every release (`tests/wayland/`) |
| KDE Plasma 6 (Wayland) | Wayland bottom layer: above Plasma's own desktop surface, which sits on the background layer, so desktop icons and widgets are covered; clicks pass through; covered screens are not drawn | headless KWin 6.7.5, every release (`tests/kwin/`); Plasma's shell itself not |
| X11 (Plasma X11, Xfce, i3, ...) | Desktop-type window over all monitors, one viewport each | Xvfb, every release (`tests/render/`) |
| GNOME (Wayland) | No layer-shell: use `--window`, or `web/index.html` in a web-wallpaper extension | not supported natively |

Each monitor gets its own full view of the stream. When a full-screen window covers the
wallpaper, most compositors stop asking it for frames, so it stops drawing; KWin does not, and
syncrain asks it instead ("Power", above).

## Channels and sync

Pick any name: everyone on it with a synced clock (NTP agrees to tens of milliseconds, about a
frame) sees the same rain. Compare stream ids (`syncrain --build`, the page's footer) when two
machines disagree: different builds with the same stream id draw the same frames.

## Recipes

A video of any moment of any channel:

```sh
syncrain --channel public --time 1791331200 --record /tmp/frames --size 1920x1080
ffmpeg -framerate 30 -i /tmp/frames/frame_%05d.png -c:v libx264 -crf 17 -pix_fmt yuv420p rain.mp4
```

The darkened CachyOS look (`extras/cachyos-logo-mask.png` masks the 3840x2160 green-nebula
wallpaper so its logo stays bright and the rain passes behind it):

```sh
syncrain --theme matrix --background ~/Pictures/cachyos-nebula.png --mask extras/cachyos-logo-mask.png
```

Rebuilding the assets (glyph atlas, themes, logos) needs Noto Sans Mono CJK, DejaVu Sans,
`rsvg-convert` and a checkout of github.com/NixOS/nixos-artwork:
`python3 tools/build_assets.py --nixos-artwork <checkout>`, then `python3 tools/build_web.py`.
A changed atlas or theme changes the stream (`tools/stream_freeze.py`).

## Credits and licences

Code: MIT (`LICENSE`). The NixOS snowflake: Simon Frankau and Tim Cuthbertson, from
NixOS/nixos-artwork, CC BY 4.0; NixOS is a trademark of the NixOS Foundation. The glyph atlas is
rendered from Noto Sans Mono CJK JP (SIL Open Font License 1.1) and DejaVu Sans (Bitstream Vera
and DejaVu licence).
