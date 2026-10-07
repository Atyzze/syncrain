# Architecture

How a frame is made, why every machine on a channel makes the same one, and how the app, the
page and the packages carry it. The recipes are in `docs/OPERATIONS.md`; why things are the way
they are, case by case, is in `docs/LESSONS.md`.

## The promise

A frame is a pure function of the UTC clock and a channel name. Nothing is stored, nothing
loops, and any two machines whose clocks agree draw the same frame at the same moment. Two people
on the channel `public` see the same rain; `friends` is a different, equally endless stream.

"The same frame" holds between machines whose stream fingerprints match (see "Builds and the
stream" below). Between the native app and the web page of one build it holds to within texture
filtering: 0.14 of 255 on average at 1280x720 (`tests/browser/test_the_web_page.py`).

## The clock and the channel (`syncrain/engine.py`)

* Time goes to the shaders as whole seconds since 2024-01-01T00:00:00Z (an unsigned 32-bit
  counter) plus the fraction of the second, on a millisecond grid like `Date.now()`. A float
  holding seconds since 1970 would lose the fraction.
* The channel goes as the 32-bit FNV-1a hash of its UTF-8 name.
* All randomness is integer hashing (`lowbias32` in `syncrain/data/shaders/common.glsl`), which is
  bit-exact on every GPU. `H(a, b, c, salt)` mixes the channel seed, a column, a second and a
  purpose.
* Anything periodic (a cell's pulse, the logo's turn, its rainbow, its drift, the whole-rain
  rainbow) runs a whole number of cycles per hour, so nothing jumps when the hour counter
  restarts; periods given in seconds are rounded to fit (`cycles_per_hour`).
* Limits: head-glyph ticks wrap in 2033, other ticks in 2058, the second counter in 2160; each
  wrap costs at most a one-off character shuffle.
* The stream is pseudo-random: unpredictable to look at, never looping, computable for any past
  or future moment. Mixing a public randomness beacon (drand) into the seed would make it truly
  random and keep everyone in sync; it is not implemented.

## The six passes (`syncrain/data/shaders/`, driven by `syncrain/renderer.py` and `web/template.html`)

1. **state** (`state.frag`): a 64-column grid of cells. Each column gets one spawn chance per
   second; whether a drop spawns, its speed (7.5 to 20.8 rows a second), trail, brightness, start
   and stop rows, head style and any hidden word all come from hashes of (channel, column,
   second). A cell's state is the brightest drop that can still reach it, so the shader looks back
   only over the slowest drop's lifetime (about 12 s). Resting characters re-roll every 1.5 to 6 s;
   the head scrambles 15 times a second.
2. **field** (`field.frag`): a 5x5 blur of the state, for glow.
3. **glyphs** (`glyphs.frag`, `rain.glsl`): the characters at a quarter of the resolution, as the
   bloom source. Atlas lookups use explicit gradients so cell edges do not pick the wrong mip level.
4. **blur**, horizontal then vertical (`blur.frag`, 17 taps).
5. **composite** (`composite.frag`): background (theme gradient or a darkened image), snow,
   crisp glyphs, bloom, the logo, front snow, a soft clip.

Columns are 64 across; a cell is at least 12 device pixels (14 CSS pixels on the page), so a
narrow or portrait screen shows the middle of the stream rather than shrinking it.

The data the passes read: `syncrain/data/themes.json` (contract `syncrain-themes-1`: theme
colours, weighted 256-entry glyph lookup tables, hidden words, snow layers, logo settings),
`syncrain/data/atlas.png` (16x16 glyph slots, glyph and two blurs in R, G and B) and the NixOS
logos (white and colours, CC BY 4.0). `tools/build_assets.py` makes all of them.

## Burn-in

Nothing on screen stays put. The rain and snow never hold a pattern; the one bright fixed element,
the logo, turns once every 3 minutes, runs its colours round a rainbow wheel every 90 seconds and
wanders up to 3% of the screen height off centre on a slow Lissajous path, all from the shared
clock. With an image background the masked logo cycles colour and the image pans. `--rainbow all`
sends the rain round the rainbow every 10 minutes. This spreads wear; it does not revive stuck
pixels, which pixel fixers do by flashing colours fast, and syncrain never does (photosensitivity).

## Builds and the stream (`syncrain/build.py`)

* **The build number** is the only identity: `BUILD_NUMBER` at the tree's root, or the package
  metadata of an installed wheel (pyproject reads the file; Nix reads the file). There are no
  version strings. `tools/package_release.py` writes it, once per archive, and nothing else does.
* **The stream fingerprint** is a SHA-256 over the files that decide the picture
  (`STREAM_FILES`: the shaders, `themes.json`, the atlas, the logos, `engine.py`). Its first eight
  hex digits, the stream id, are shown by `syncrain --build`, in the startup line and in the
  page's footer. Same stream id, same channel, synced clocks: the same frame. Different ids may
  still draw the same frame (a refactor of `engine.py`), but nothing promises it.
* **The freeze** (`tests/fixtures/stream_freeze.json`) records the stream files' hashes; the gate
  fails when one moves until `tools/stream_freeze.py --write` re-takes it, which a build does only
  on purpose and says so in its notes.

## The native app (`syncrain/app.py`)

* GTK 4 with a `Gtk.GLArea` per viewport and PyOpenGL. **OpenGL or OpenGL ES, whichever GTK hands
  out**: GTK 4.14 and later create every context to share with the display's own, which is OpenGL
  ES unless `GDK_DEBUG=gl-prefer-gl`. The app asks for no version (desktop "3.3" asked of OpenGL ES
  matches nothing, which was build 2's grey screen on the operator's machine) and checks after the
  fact that it got GL 3.3 or GLES 3.0; the shaders get the matching header (`#version 330 core`
  or `#version 300 es` with high precision). Both draw the same frame, pixel for pixel on Mesa.
* **Wayland**: one layer-shell surface per monitor through gtk4-layer-shell, which must be loaded
  before libwayland-client (the app re-executes itself once with `LD_PRELOAD`; the Nix wrapper and
  the installer's launcher preload it). The background layer everywhere except KDE Plasma, whose
  desktop sits on that layer itself, so syncrain takes the bottom layer there: above Plasma's
  desktop, below windows, covering its icons. The input region is empty, so clicks fall through.
* **X11**: one desktop-type window over all monitors (EWMH hints through libX11), a viewport per
  monitor.
* **No OpenGL**: the windows are hidden at once and the app exits with status 69, which the
  services list in `RestartPreventExitStatus`. Until the first frame a window is black, not GTK's
  light grey.
* **Signals**: SIGINT, SIGTERM and SIGHUP end the main loop cleanly (GLib owns them; PyGObject's
  KeyboardInterrupt fallback is kept out of the way).
* **GTK's own OpenGL renderer** puts the picture on screen (`GSK_RENDERER=gl`, unless the user set
  it). On Wayland, GTK 4.16 and later otherwise draw with Vulkan and hand a GLArea's texture over
  every frame: through a dmabuf where the GL driver can export one, else through the processor, a
  full screen per frame per screen.
* **One line at startup** names the build, the stream, the OpenGL it got, GTK's renderer and the
  screens: `syncrain build <N> (stream <id>): OpenGL ES 3.2 on <card>, GTK renderer gl, 2 screens`.
* **When a frame is drawn, and for which moment** (`syncrain/pacing.py`). Each screen asks for its
  next frame on its own: after a frame, the pacer takes the screen's refresh grid from GTK's frame
  clock (`get_refresh_info`, which GTK keeps from the compositor's presentation feedback) and picks
  the refresh N after the last target, N the fewest whole refreshes that keep the rate at or under
  `--fps`. A GLib timeout asks for the frame some time before that refresh (the lead), and the frame
  is drawn for that refresh's moment, not the moment it is drawn, so the motion advances by the same
  step every frame. A compositor shows a frame at the first refresh whose deadline it makes, so the
  commit has to land in a window one refresh wide: after the deadline of the refresh before (or the
  frame is shown a refresh early) and before the deadline of its own (or a refresh late). Where that
  window lies depends on how long drawing takes and on the compositor, and at 144 Hz it is 7 ms wide.
  The lead starts at half a refresh plus 6 ms and moves by half a millisecond whenever GTK reports a
  frame shown a refresh early or late (`Pacer.shown`, fed from GTK's frame timings), within 2 ms and
  two refreshes plus 6 ms; frames asked for before a move are not counted again, nor is a frame shown
  more than two refreshes off (the screen was locked or off, and GTK heard of it only afterwards). A
  card too slow for any lead shows every frame a refresh late, which keeps the steps even.
  Without a grid (X11 without a compositor, the first frame on a screen) the next frame is asked for
  one period later, as build 4 did for every frame from one 33 ms timer for all screens; `--pacing
  timer` (hidden, for the power sweep) still does that. Nothing ticks between frames, and a screen
  the compositor stops asking for frames (off, locked, hidden on Sway) costs nothing.
* **Covered screens** (`syncrain/hidden.py`). KWin sends every surface on a screen its frame
  callbacks after each frame, covered or not (`src/scene/item.cpp`, `Item::framePainted`), so GTK
  never learns that a wallpaper is hidden there. On Wayland, when `org.kde.KWin` is on the session
  bus and `--pause-under` is not `never`, the app writes a small script to `$XDG_RUNTIME_DIR` and
  loads it into KWin (`org.kde.kwin.Scripting.loadScript`, then `run`). The script watches the
  windows (full screen, maximized, minimized, hidden, geometry, desktops, activities, opacity) and
  calls back `org.syncrain.Watch.Covered(screen, covered)` on the app's own bus name whenever a
  screen's answer changes; the app accepts the call only from KWin's bus name. A viewport stops
  asking for frames while all its screens are covered and KWin is not showing the desktop
  (`showingDesktopChanged` on `/KWin`), and draws at once when it shows again. The script only
  reads, checks the two cheap properties (full screen, maximized) before anything else, and answers a
  burst of changes (a window dragged across the screen) at most every 50 ms, from a single-shot
  `QTimer` started only when it is not already running, since it runs on KWin's main thread. KWin numbers a script by how many it
  holds, so the number can be one a running script already has; when the script has not answered
  after 1.5 s the app asks `org.kde.kwin.Scripting.start`, which runs every loaded script not yet
  running, and after 3 s it gives up (KWin 5, whose script API names things differently). The app
  unloads its script when it stops; scripts left in `$XDG_RUNTIME_DIR` by a syncrain that died (no
  process with that pid runs a syncrain command) are unloaded by the next one. The startup is followed by "drawing pauses on a screen under maximized
  and full-screen windows (KWin)" once KWin has answered.
* `--diagnose` (`syncrain/diagnose.py`) runs the same checks without a window and prints a
  verdict first: the session, the libraries, the graphics cards from sysfs, the context GTK hands
  out, the shaders compiled on it, one frame drawn offscreen and, on Plasma, what KWin says about
  covered screens.

## Where a frame's work goes

Every pixel is computed on the graphics card by the shaders, which its driver compiles to the card's
own code; there is no faster language to rewrite them in, only less work to give them. The host
(`syncrain/renderer.py`) issues about forty OpenGL calls a frame, everything that never changes
having been set when the programs were built: about 0.6 ms of one CPU thread per frame in the
sandbox. On the sandbox's software renderer at 1920x1080 the composite pass is 88% of a frame (the
four snow layers half of it) and the two quarter-size blurs 9%. `syncrain --benchmark` measures the
same on a real card; `syncrain --power-sweep` measures what it costs in watts (`syncrain/power.py`).
On the operator's RTX 5090 the watts follow the frames, not the pixels: about 0.17 J a frame per
screen, of which halving the resolution saves an eighth (build 4's sweep). Most of a frame's cost is
the card waking for it, so what saves power is drawing fewer frames, and none that nobody sees.

## The web page (`web/template.html`, `tools/build_web.py`)

A single self-contained page: the same shader files inlined, the themes, the images as data URLs,
the build number and the stream id. WebGL2 (GLSL ES 3.00). It runs from `file://`, reads URL
parameters for wallpaper hosts, and shows a control strip that fades when idle. `web/index.html`
(a full document) and `web/artifact.html` (the body only, for hosts that wrap it) are generated:
the release rebuilds them and the gate fails when they differ from what the generator makes.

## Packaging

* `install.sh`: the Arch-family installer (pacman packages, then everything in `~/.local`, an
  optional systemd user service). It reads `BUILD_NUMBER`, names upgrades, restarts a running
  wallpaper, and writes a launcher that preloads gtk4-layer-shell and sets `PYTHONSAFEPATH`.
* `nix/`: the package (version from `BUILD_NUMBER`), the web bundle, a NixOS module and a
  home-manager module sharing `nix/options.nix` and `nix/args.nix`; `flake.nix` exposes them.
* systemd quoting, everywhere a service line is written: each argument's backslashes, `%` and `$`
  are doubled, then it is single-quoted, because systemd unescapes inside single quotes, expands
  specifiers before splitting and variables after (`tests/support.py`, `systemd_exec_words`).

## The release (`tools/package_release.py`)

Bump, rebuild the pages, run every lane with every environment required, stamp the notes, compile,
build and clean-install a wheel and ask it its build and stream, then write `SYNCRAIN<N>.tar.zst`
holding one directory, `syncrain_build_<N>/`, verified byte for byte before it gets its name. A
journal undoes a killed run. `README.md`, "Releasing", has the command; `docs/agent/NEXT_BUILD.md`
the whole procedure.
