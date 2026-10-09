# Build 8: the wallpaper without Python or GTK in memory

**Type: performance; the picture does not change.** Made on 2026-10-08 and 09. On the operator's
desktop build 7 kept 287 MiB at boot and 420 MiB after a night (btop); they asked for "as low as
realistically possible", with the look, the smoothness and every function kept and the power and
processor time down, and whether Rust or another language would do better than Python. At 07:05
they asked to drop the hunt for a leak, since the rises and falls looked like the garbage
collector's, and to cut the footprint without giving up frames per watt, power first. Build 8
does that in two parts: on Wayland a native wallpaper in C (sections 1 and 2), and a lighter
Python and GTK host for everything else (section 3). The stream is unchanged (48e6bf9c); both hosts
draw build 7's frames, to the pixel on a screen at a whole-number scale (at a fractional one, the
GTK host draws more pixels and GTK scales them down, section 1). The operator asked to try it
before it goes to GitHub, so it was delivered in the chat and `main` still holds build 7.

## 1. The native wallpaper (`syncrain/native/`, `syncrain/native.py`)

On a Wayland session, `syncrain` (still Python) reads its options, prepares the scene with the GTK
host's own functions (the shader sources, the textures' pixels and the uniforms set once from
`syncrain/renderer.py`, the KWin script from `syncrain/hidden.py`, and the command that would start
the GTK host), writes it to a memfd and replaces itself with `syncrain-wallpaper`, a C program of
about 100 KB (`os.execve`: the same pid, nothing of Python left). It draws every screen with one
EGL context and keeps the program, libwayland, libEGL, libdbus and the graphics driver in memory;
no interpreter, no toolkit. Its parts:

* `wallpaper.c`: a layer-shell surface per screen (the layer the GTK host would take; empty input
  region; opaque; the screen's own pixel size through fractional scale and viewporter, where GTK's
  GLArea draws at the next whole scale and GTK scales it down: at 150% the GTK host draws 1.8 times
  the pixels for the same picture, a little softer), the event loop
  (ppoll over Wayland, D-Bus, timers and a signalfd for SIGINT, SIGTERM and SIGHUP), screens coming
  and going, the startup line ("..., native wallpaper, 2 screens"), `SYNCRAIN_DEBUG_FPS`.
* `timing.c`: the viewport's geometry (`renderer.py` `Targets`, `_keep_rect`), the clock's split
  (`engine.py` `split_time`, `cover_fit`) and the pacer (`pacing.py`), ported operation for
  operation so the doubles are Python's to the last bit, Python's float floor division
  (`_float_div_mod`) and round half to even included. The refresh grid comes from `wp_presentation`
  feedback, kept the way GTK's frame clock keeps it (`get_refresh_info`, 150 ms of history, its
  16667 µs default), and a frame is drawn only after the compositor's frame callback for the one
  before, as GTK waits; a screen the compositor stops asking for frames costs nothing.
* `render.c`: EGL opened at run time (so a machine without it hands over instead of failing to
  start), OpenGL or OpenGL ES chosen by GTK's own switches (`GDK_DISABLE`, `GDK_DEBUG`), the six
  passes with the same calls in the same order as `renderer.py`, the composite pass straight into
  the screen's buffer, `eglSwapInterval(0)` since the frame callbacks pace the frames.
* `kwin.c`: `syncrain/hidden.py`'s watch over libdbus, with the same script: covered screens on KDE
  Plasma are not drawn, KWin's own bus name only, scripts left by a dead syncrain unloaded.
* `scene.c`: the scene's format (contract `syncrain-scene-1`), refused when it comes from another
  build's launcher or is cut short.
* **Hand-over**: anything that fails before the first frame is shown (no Wayland, no layer-shell,
  no EGL, an OpenGL too old, a shader the driver refuses, a first swap that fails) runs the GTK
  host's command from the scene, with gtk4-layer-shell back in `LD_PRELOAD` (the launcher keeps it
  out of the native process), so the wallpaper draws wherever build 7 drew. `--host gtk` asks for
  the GTK host; `--host native` insists on the native one: its scene names no GTK host, so it says
  why it cannot draw and stops.
* **After the first frame**: a swap that fails (as a driver's can after a resume or a reset of the
  card) commits nothing, so the frame's callback and feedback are dropped and the next frame tries
  again at its time; when no frame can be shown for 5 s, or when the compositor goes away (a crash,
  or a restart of KWin), the program stops with status 1, as GTK does, so the service
  (`Restart=on-failure`) starts it again. X11, `--window`, `--screenshot`,
  `--record` and build 4's `--pacing timer` (the sweep's comparison) are the GTK host's.
* `syncrain --diagnose` gains a "native wallpaper" section: built or not, and on Wayland what the
  program's `--probe` finds (the compositor's protocols, the screens, the OpenGL it gets, whether
  the shaders compile, its verdict).

## 2. What the native wallpaper saves, measured in the sandbox

Headless Sway with two screens, Ubuntu's GTK 4.14 and Python 3.12, Mesa's llvmpipe: a software
renderer, since the sandbox has no graphics card, so every frame's pixels are drawn by the
processor and the driver is LLVM. Each host settled for 15 to 20 s and was then measured for 60 s,
twice; the two runs agreed within a MiB and a few percent.

| two screens, 30 fps each | build 7 | build 8, GTK host | build 8, native |
| --- | --- | --- | --- |
| resident memory, 640x360 each | 307.8 MiB | 262.8 MiB | 136.1 MiB |
| resident memory, 320x180 each | 302.5 MiB | 258.0 MiB | 132.7 MiB |
| processor time per frame, all threads (320x180) | 21.1 to 22.7 ms | 21.2 to 21.8 ms | 18.6 to 18.7 ms |
| of it on the main thread | 2.2 to 2.5 ms | 2.2 ms | 1.0 ms |
| threads, file descriptors | 10, 11 | 10, 11 | 6, 6 |

With nixpkgs' Python 3.14 and GTK 4.22 (the versions the operator's CachyOS has), build 7 kept
279 MiB and the GTK host 235 MiB at 640x360, and their main threads took 2.6 and 2.4 ms a frame at
320x180; the native wallpaper is the same program whichever Python started it (136 MiB, 1.0 ms).

At 320x180 every host kept up (60 frames a second over the two screens). Most of a frame's
processor time here is llvmpipe drawing the pixels, which a graphics card does instead; what is
left on a card is closer to the main thread's share, where the host and the driver's command
handling run: about 1 ms a frame for the native wallpaper against 2.2 for the GTK host, or 6% of
one core against 13% at 60 frames a second. At 640x360 the processor could not keep up with either
host, and the native wallpaper drew 28.7 frames a second where the others drew 23 to 25, from the
same processor time.

Where the memory goes (resident, 640x360): build 7 keeps 128 MiB of C heap, 68 MiB of other
anonymous memory (Python's objects among it), LLVM 57, llvmpipe 12, GTK 8, the interpreter 6. The
native wallpaper keeps LLVM 57, llvmpipe 11, and 55 MiB of heap and anonymous memory, most of it
llvmpipe's: the textures alone are 24 MiB with their mipmaps (the glyph atlas and the logo, 1536 by
1536 each), and the compiled shaders and the frame's intermediate targets add to them; a graphics
card keeps all of that in its own memory. libdbus, libwayland and the program are under a MiB
each. So in the sandbox about 130 of the native wallpaper's 136 MiB is the driver. NVIDIA's driver
keeps a different amount, unknown here; the sweep's "MiB" column measures it on the operator's
machine.

What does not change: the watts. The card runs the same shaders for the same frames whatever drives
them, and on the operator's RTX 5090 the watts follow the frames (build 4's sweep). The native
wallpaper does draw one full-screen copy fewer per frame and screen (the GTK host draws into a
GLArea's texture, which GTK then draws into the window), which is the card's only saving; the rest
is memory and processor time. On a card, the sweep's rows "as installed" and "the Python and GTK
host" will measure it.

The language: C, because the program is mostly calls into libwayland, EGL and libdbus, it builds
with gcc and those libraries' headers and nothing fetched, and it compiles to machine code with no
collector, as Rust would. Assembly would not touch the shaders, which the driver compiles.

## 3. The GTK host, lighter (`syncrain/app.py`, `syncrain/gl.py`, `syncrain/renderer.py`)

Python and GTK still draw on X11, in a window, for screenshots and recordings, and wherever the
native wallpaper cannot; build 8 makes them lighter as well (262.8 against 307.8 MiB above).

* **OpenGL through ctypes** (`syncrain/gl.py`): the functions come from libepoxy, GTK's own OpenGL
  loader, so PyOpenGL and numpy are not loaded; `SYNCRAIN_GL_DEBUG=1` checks every call and names
  the one that failed. Frames are the same to the pixel (the render lane).
* **The screen-change leak**: build 7 made its programs and textures for every screen's context
  and deleted none when a screen went. GTK makes every context of a display share objects, so the
  textures outlived their screen: about 120 MiB a change in the sandbox, and a DisplayPort screen
  waking from sleep is a change. Now the programs and textures are made once per process, and each
  screen's own targets are deleted when its area is unrealized. Three changes now leave under
  30 MiB (the first change is not counted: GTK and Mesa keep some of their own then) with either
  host (`tests/wayland/test_the_wallpaper_layer.py`, `tests/render/test_the_gpu_objects.py`).
* **No dmabuf round trip**: with GTK's OpenGL renderer, `GDK_DISABLE=dmabuf` too. From GTK 4.16 a
  GLArea exported each frame as a dmabuf and the same renderer imported it back, after starting a
  Vulkan renderer beside itself for the first one. Set before `import gi`, since GTK reads it once.
* **After startup**: once every screen has drawn, Python's garbage is collected and the C heap's
  free pages are handed back (`settle_memory`); a frame makes no garbage after that.
* An installed wheel's build number is read from its own `METADATA` file (`importlib.metadata`,
  which brings the `email` package and a few MiB with it, only when that fails), and `ctypes.util`
  (which imports `subprocess`) only where gtk4-layer-shell must be found.

## 4. The power sweep (`syncrain/power.py`)

* A phase "the Python and GTK host" (`--host gtk`) right after "as installed", so the two hosts
  are side by side on the operator's card.
* Columns "cpu %" (the wallpaper's processor time, 100 being one core kept busy), "MiB" (its
  resident memory at the end of the phase) and "drawn by" (`native`, or GTK's renderer); the JSON
  rows carry `cpu_percent` and `resident_mib`.
* The native program counts as a running syncrain when the sweep looks for one.

## 5. Installing it

* `install.sh` builds the native wallpaper into the installed copy (`syncrain/native/build.sh`,
  about two seconds) and asks pacman for `gcc pkgconf wayland dbus` besides the app's packages;
  `python-opengl` is no longer among them. When the build fails, it prints why and the GTK host
  draws.
* The Nix package builds it into `libexec/syncrain/` with libglvnd's libEGL, which finds the
  system's driver (`/run/opengl-driver`), and its wrapper names it in `SYNCRAIN_WALLPAPER`.
  `pyopengl` is gone from its dependencies.
* `pyproject.toml` ships the C sources and drops PyOpenGL; the release and `.gitignore` leave the
  built program out.

## 6. Tests

* `tests/native/` (a lane of its own, in the gate): the program is built from the tree; the
  geometry, the clock's split, the pacer's plans and the timing report agree with the Python
  host's value for value (hexadecimal floats, thousands of cases); a scene from another
  build or cut short is refused; without a compositor it hands over to the GTK host; asked for by
  name it says why it cannot draw; the launcher hands over everything the GTK host would use and
  keeps gtk4-layer-shell out of the native process.
* The wayland lane runs every on-screen test with both hosts, holds them to the same frame to the
  pixel, checks that the native process holds neither libpython nor GTK, changes screens under
  both, takes the compositor away under both, and makes the native wallpaper's swaps fail. The
  kwin lane checks the full-screen pause with both hosts and times the native wallpaper's frames
  at 60 and 141 Hz against build 4's timer. The nix lane runs the package's own
  native wallpaper in a headless Sway and compares its frame with the tree's.
* The unit lane checks the installer's build (and its fallback without a compiler), the sweep's new
  phase and columns, and the environment GTK starts in.
* The kwin lane's frame timing is judged by the median of six 2-second reports, not by the
  second-worst of four: on 2026-10-09 this sandbox's frames now and then took three times as long
  as usual, and the old rule failed a pacer whose median was well over the line. Measured that day
  at 60 Hz, "even" and "steady": the native wallpaper 77 to 97% and 87 to 98%, the GTK host 40 to
  87% and 62 to 93%, build 7 36 to 87% and 62 to 93%; at 141 Hz the native wallpaper 74 to 96% and
  86 to 98%, the GTK host 61 to 75% and 74 to 86%.

## 7. What the review found, fixed before delivery

An agent that had not written build 8 reviewed it against build 7 and against GTK 4.22's and
NVIDIA's egl-wayland sources. It ran the native wallpaper through 25 screen changes, screens off
and on and fractional scales (also built with AddressSanitizer, which found nothing), with memory
flat at 129.8 MiB and six file descriptors throughout, and under a crash of Sway and of KWin; it
found the KWin watch, the options and the hand-over to match the GTK host's. What it found wrong:

* **A compositor that went away left no wallpaper.** The native program returned status 0 when
  its connection broke (KWin crashing or restarting), and the service restarts only after a
  failure; GTK exits with 1 there. It now stops with status 1 and says why, and a hung-up
  connection is read rather than polled again (`tests/wayland/`,
  `test_when_the_compositor_goes_the_wallpaper_stops_with_an_error`, both hosts).
* **A swap that failed after the first frame froze that screen for good**: the frame's callback
  was asked for before the swap, and with nothing committed it never came. Now the frame's
  requests are dropped and the next frame tries again; failures for 5 s stop the program with
  status 1, and a first swap that fails hands over to the GTK host. The lane makes swaps fail on
  purpose (`SYNCRAIN_TEST_SWAP_FAILURES`, for the tests only): three tests, the recovery one
  failing without its fix.
* **`--host native` still handed over to the GTK host**: the scene named the GTK host's command
  anyway. It names none now (`tests/native/`).
* **A scene left open**: when the exec failed, the GTK host kept the scene's memfd (19 MiB and
  more) open for its whole life. It is closed now (`tests/native/`).
* **The GTK host could delete in GTK's own context** when making its own current failed (which
  GTK does not report) while a screen went. It now deletes only with its own context current.
* **"To the pixel" holds at whole-number scales only**, since GTK's GLArea draws at the next whole
  scale; said so (section 1, `docs/ARCHITECTURE.md`).
* A document pointed at the built program as if it were in the tree; reworded.

Left as it is: a driver that fails after the first frame every time makes the service start the
wallpaper every 3 s, and the GTK host does not take over then (it would only after a failure
before the first frame). On the operator's machine that would show as the rain stopping and
starting again; the journal says why.

## 8. What the operator does

* Unpack `SYNCRAIN8.tar.zst` and run `./install.sh` from `syncrain_build_8/` (pacman may install
  `gcc pkgconf wayland dbus`); it builds the native wallpaper, replaces build 7 and restarts the
  wallpaper. The service's startup line (`journalctl --user -u syncrain`) should say "native
  wallpaper"; btop lists the process as `syncrain-wallpa`, the kernel's 15-letter cut of
  `syncrain-wallpaper`, where build 7 was `python3`.
* Look: nothing should look or move differently. If anything does, `syncrain --host gtk` draws
  through Python and GTK as before, for comparison.
* Optionally `systemctl --user stop syncrain`, then `syncrain --power-sweep`: the rows "as
  installed" and "the Python and GTK host" are the two hosts on their card, with watts, processor
  time and memory side by side.
* Say whether build 8 goes to GitHub; the three questions in `docs/ROADMAP.md` are still theirs.

## Verification

179 passed in 559.96s (0:09:19)

Before the gate, by hand: every lane on the tree (native, wayland, render, browser, nix and kwin
all passed on 2026-10-09, and again after the review's fixes); the measurements of section 2 with
`syncrain` on a headless Sway; the screen-change test against build 7 (about 120 MiB a change,
failing) and build 8 (passing); the tests of the review's first two findings, each failing with
its fix undone.
