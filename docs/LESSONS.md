# Lessons

The rules this project learned by shipping their opposite, each with the shortest case that
justifies it, so a reader can judge whether it still applies. Each build's notes are in
`docs/build_notes/`; `docs/HISTORY.md` says what each build did.

## OpenGL and GTK

**Never ask GTK for an OpenGL version.** GTK 4.14 and later create every context to share with
the display's own, which is OpenGL ES unless `GDK_DEBUG=gl-prefer-gl`. Build 2 called
`set_required_version(3, 3)`: as OpenGL ES that is 3.3, above every ES version GTK tries, so none
was tried, and GTK fell back to desktop OpenGL shared with an ES context. Mesa allows that (so every
sandbox run drew); the EGL specification does not, and the operator's machine refused: "Unable to
create a GL context", and a grey screen. Take what GTK gives and check it afterwards.

**A sandbox that cannot fail the way the target fails needs the failure forced.** Mesa hid build 2's
bug in every run. The lanes now force each case: only OpenGL ES (`GDK_DEBUG=gl-disable-gl`, or
`GDK_DISABLE=gl-api` from GTK 4.16), only desktop OpenGL, and none.

**A wallpaper that cannot draw must leave at once.** GTK windows are light grey by default, and
build 2's windows stayed up with nothing in them, covering the desktop until Ctrl+C. Now the
windows are black until the first frame, and without OpenGL they are hidden and the app exits
with status 69, which the services will not restart.

**The sandbox never ran GTK's Vulkan renderer, and the operator's desktop does.** GTK takes Vulkan
on Wayland when the device is a real GPU; the sandbox's only Vulkan device is a CPU, which GTK
refuses, so every lane used GTK's OpenGL renderer. With Vulkan, a GLArea's picture crosses from
OpenGL to Vulkan every frame, by dmabuf or by a copy through the processor. Build 4 chose the OpenGL
renderer for syncrain's windows and made the sweep measure both.

**On a fast card the watts are a frame count.** The operator measured a GIF and syncrain at about
20 W each (2026-10-07), and build 4's sweep on their RTX 5090 showed why: about 0.17 J a frame per
screen, falling in a straight line from 30 to 10 fps, while half the resolution saved an eighth and
no snow a tenth. Rust, C or fewer shader instructions would shave the small part. What saves power
is fewer frames, and none that nobody sees. Measure on the card, not in the sandbox.

**Copies cost more than drawing.** GTK's Vulkan path (a GLArea's picture handed to Vulkan each
frame) cost 25.5 W on the operator's card, its OpenGL path 10.6 W, for the same frames.

**A frame drawn for the moment it is asked for is drawn for the wrong moment.** Build 4 asked for a
frame every 33 ms and drew it for that instant; the screen showed it at its next refresh, anywhere
up to a refresh later, so the motion stepped unevenly even while the frames were evenly spaced. On
a headless KWin, 17 to 44% of build 4's frames were shown the usual delay after the moment they were
drawn for, against 95 to 100% for build 5, which draws each frame for the refresh it is shown on.

**A lead that only grows makes frames early; one that moves both ways finds the window.** A frame
must reach the compositor within one refresh before its own: after the deadline of the refresh
before, before its own. Build 5 first grew the lead by a whole refresh whenever a frame came late,
and the compositor then showed every frame a refresh early. Build 5 shipped a fixed lead (half a
refresh plus 6 ms), right at 60 Hz, where the window is 16.7 ms wide, and off at 141 Hz, where it is
7 ms (74 to 84% of frames steady on the kwin lane). Build 6 moves the lead by half a millisecond
toward whichever side GTK reports a miss on, and counts no frame planned before the last move: 86
to 100% at 141 Hz. A late but constant delay keeps the steps even; an early frame is as wrong as a
late one.

**GLArea does not reset the viewport between frames.** Take the framebuffer size from the
"resize" signal.

**Quitting from an idle callback can starve.** `GLib.idle_add(app.quit, priority=GLib.PRIORITY_HIGH)`.

**PyGObject turns Ctrl+C into a KeyboardInterrupt after the main loop ends**, unless Python's
default SIGINT handler is already replaced. Replace it, then let GLib own SIGINT, SIGTERM and SIGHUP.

## Memory and the hosts

**A wallpaper's memory is mostly what it loads, not what it draws.** Build 7 kept 287 MiB at boot
on the operator's desktop. In the sandbox the frame itself needs a few MiB (the textures, the
targets, the scene); the rest was the interpreter, GTK and everything they bring (fonts, icon
themes, accessibility, a Vulkan renderer GTK started for the dmabuf round trip), PyOpenGL, and the
graphics driver. What lowers it is loading less: build 8's GTK host drops PyOpenGL, numpy and the
round trip, and the native wallpaper loads neither Python nor GTK (in the sandbox, two screens:
build 7 308 MiB, build 8's GTK host 263, the native wallpaper 136, of which about 130 is the
software renderer).

**A faster language changes the processor's share, not the card's.** The operator asked before
build 4 and again before build 8 whether Rust, C, C++ or assembly would help. The shaders are the
same whatever drives them, compiled by the driver, and the card's watts follow the frames. What a
native host changes is the memory (no interpreter, no toolkit), the processor time around each
frame, and here one full-screen copy per frame and screen that GTK makes. C rather than Rust:
both compile to machine code with no garbage collector, so memory and processor time come out
alike; C needs only gcc and the libraries' own headers (the installer asks pacman for them), where
Rust needs its toolchain and crates fetched or vendored at build time, for a program that is
mostly calls into libwayland, EGL and libdbus.

**GTK makes every context of a display share objects, so a widget's textures outlive the
widget.** Build 7 built its programs and textures for every GLArea and deleted nothing when one
went; since the textures belonged to the whole share group, every screen change (a DisplayPort
screen waking from sleep is one) kept about 120 MiB. Make what every screen reads once, and delete
each screen's own objects when its area is unrealized.

**A cold shader cache costs memory for as long as the process lives, unless the heap is handed
back.** The first time a driver meets the shaders (after an install, or after a driver update) its
compiler works in the C heap, and glibc keeps what it frees for later. On the operator's NVIDIA
card build 8's first native run kept 182 MiB, the later ones 123; in the sandbox 155 MiB against
133. `malloc_trim` once every screen has drawn its first frames gives the free pages back (155 to
142 MiB in the sandbox; build 9).

**From GTK 4.16 a GLArea's frame goes out as a dmabuf and comes back in**, even when GTK's own
OpenGL renderer draws it: exported, wrapped and imported by the same renderer, which also started a
Vulkan renderer beside itself for the first one. `GDK_DISABLE=dmabuf` (read once, when GTK
initialises, so before `import gi` finishes) keeps the texture where it is.

**C that must match Python must do Python's arithmetic.** Python's float `//` is not `floor(a / b)`
(it is `fmod`, then a quotient snapped to the nearest integer: `_float_div_mod`), `round` rounds
half to even, and `(a * b) * c` is not `a * (b * c)` in doubles. Port the operations in Python's
order, then compare the two on the same inputs printed exactly (`%a` in C, `float.hex` in Python):
`tests/native/` found the last bit that way.

**What never changes has one source of truth.** The native wallpaper reads the shaders, the
textures' pixels and the uniforms set once from a scene Python makes with the GTK host's own code,
handed over in a memfd; only what a frame computes is written twice, and that is compared bit for
bit. `execve` keeps the pid, so the service, the sweep and btop see one process, and frees
everything Python held.

## Desktops

**Plasma 6 puts its own desktop on the background layer.** A background-layer wallpaper is hidden
behind it, so syncrain takes the bottom layer on KDE and covers the icons; its input region is
empty, so clicks reach the desktop.

**KWin asks a covered wallpaper for frames; Sway does not.** KWin sends frame callbacks to every
surface on a screen after each frame, covered or not, so on Plasma a wallpaper under a full-screen
window drew at full rate (the operator's sweep: 60 frames a second, +11 W). The KWin lane shows it
in every release. The fix asks KWin, whose scripting API knows each window's state.

**To KWin, a layer-shell surface is a window of the type its namespace names.** "desktop", "dock",
"notification" and a few more are types; "syncrain" names none, so syncrain is a normal window to
KWin: show desktop hides it, and a script that counted screen-sized normal windows as covering would
pause syncrain behind itself (the script counts only maximized and full-screen windows).

**KWin's restricted Wayland protocols are granted by the executable's desktop file.** Up to 6.7,
`org_kde_plasma_window_management` needs `X-KDE-Wayland-Interfaces` in a desktop file whose `Exec`
is the client's executable, which for syncrain is Python itself, so granting it would grant every
Python program. KWin's scripting over D-Bus asks for nothing of the kind.

**KWin numbers a script by how many scripts it holds.** `loadScript` returns `scripts.size()`, so
after an earlier script is unloaded a new one can get the number of one still running, and
`/Scripting/Script<n>` then reaches the old one: build 5's script never ran in that case, and the
wallpaper said "KWin 5?". `org.kde.kwin.Scripting.start` runs every loaded script that is not running.

**A KWin script runs on KWin's main thread.** Build 5's script looked at every window on every move
of a dragged one; build 6 reads the two cheap properties first (0.10 to 0.04 ms a pass with 13
windows, in the sandbox).

**`QTimer.start()` restarts a running timer.** Build 6 called it on every change to answer bursts
together, which put the answer off until the changes stopped: a screen uncovered by dragging a
maximized window stayed paused until the pointer rested (1.6 s into a 1.5 s drag, on the kwin lane).
Start it only when it is not running, and the answer comes at most 50 ms after the first change.
The unit test's stand-in timer did not restart, so it could not see the fault; it now runs on a
clock the test moves, as Qt's does.

**A frame GTK hears about late was not necessarily shown late.** While a screen is locked, KWin
asks nothing of the wallpaper, and the frame committed before the lock is reported as shown when
the screen comes back, minutes after its refresh. The pacer ignores frames more than two refreshes
off; otherwise each lock moved the lead.

**"syncrain" in a command line is not a syncrain.** A dead process's pid can be taken by
`journalctl -fu syncrain` or an editor open on `syncrain/app.py`; the leftover check reads the
command as the sweep does (`python -m syncrain`, the Nix wrapper).

**KWin's show desktop lasts while its caller is on the bus.** `org.kde.KWin.showDesktop(true)` ends
when the caller disconnects, so a `dbus-send` that exits ends it at once; a test keeps a connection
open. A `dbus-send` without `--print-reply` can exit before its call is delivered at all.

**gtk4-layer-shell must load before libwayland-client.** The app re-executes itself with
`LD_PRELOAD`; the Nix wrapper and the installer's launcher preload it.

## Launching and services

**`python -m` puts the current directory first.** The operator ran `syncrain` from inside the
unpacked release folder, and build 2's launcher started that folder's copy instead of the
installed one. The launcher sets `PYTHONSAFEPATH=1`.

**systemd is not a shell.** It unescapes backslashes inside single quotes, expands `%` specifiers
before splitting and `$` variables after it. Double all three, then quote; check by parsing the
line the way systemd does (`tests/support.py`).

**A service that fails for a missing capability must not restart into it.** `Restart=on-failure`
alone would have covered the desktop again every three seconds.

## Releases and identity

**Two trees under one name is the failure a build number exists to prevent.** Builds 1 and 2 were
both delivered as `syncrain-0.1.0.tar.gz`. Every archive now has its own number, written by the
release tool only.

**A review by someone who did not build it finds what the gate cannot.** Build 5 passed every lane;
a review of its code against KWin's and GTK's sources, by an agent that had not written it, found
three faults in the KWin script (a reused script number, scripts left by a crash, work on KWin's
main thread for every step of a drag) and a timing margin that shrank with the refresh rate. Each
became a test that fails without its fix (build 6).

**You cannot know the gate's result before the gate.** The notes carry the token GATE_RESULT and
the release writes the summary in.

**A generated file goes stale silently.** The web pages carry the shaders and the build number;
the release regenerates them and the gate compares them byte for byte.

## Rendering and sync

**Time as a float since 1970 loses the fraction.** The shaders get whole seconds since 2024 and the
fraction separately.

**Anything periodic needs a whole number of cycles per hour**, or it jumps where the hour
counter restarts.

**Atlas lookups need explicit gradients.** Neighbouring cells pick different mip levels at their
edges otherwise.

**Integer hashing is the only randomness that is bit-exact on every GPU.** Two sessions at
different resolutions produce identical rain grids; the browser lane checks it every release.

## The GIFs (before build 1)

**A loop is visible on a wallpaper within seconds.** The 4 to 6 second GIF loop is why syncrain
draws every frame from the clock instead.

**gifsicle's lossy mode breaks a loop's seam.** It made a visible pop where the loop restarted.

## The build sandbox

**The sandbox restarts and keeps only files.** Background processes (Xvfb, Sway) are gone after a
pause; the lanes start their own displays.

**`pkill` inside a chroot reaches the host.** The chroot shares the process namespace: an in-chroot
`pkill -x Xvfb` killed the host's Xvfb. Stop processes by their PID.

**`pkill -f` matches the shell that runs it.** By PID, again. The same holds for `pgrep -f` in a
test: the tool's own shell carries the pattern. Read `/proc/<pid>/cmdline` as an argument list.

**A scratch script named after a standard module replaces it.** `profile.py` beside a script that
imported `cProfile` was imported as the standard `profile`.

**A heredoc ends at its terminator, even inside the text it carries.** A script containing a line
`EOF` ended its own heredoc early and the rest ran as shell. Use a terminator the text cannot
contain, or write the script with a file tool.

**Tool parameters are JSON, and JSON decodes `\u` escapes.** A file written through a tool gets
the character, not the escape; write escapes through a script.

**Sources for GTK and systemd come from their GitHub mirrors.** The sandbox reaches GitHub and the
package registries, not the projects' own sites; build 3's diagnosis read `gdkglcontext.c` from
the GNOME/gtk mirror at the tag Arch ships, build 5's KWin reading came from KDE/kwin's.

**KWin takes a screen's refresh rate from its own output settings.** The virtual backend's screens
are 60 Hz; a `kwinoutputconfig.json` written before KWin starts (the one KWin writes after
`kscreen-doctor ... addCustomMode`) gives the kwin lane a 141 Hz screen. The stored mode must be the
mode KWin computes from the custom one (141332 mHz for 144000 asked), or KWin falls back to 60 Hz.

**A timing test that judges the worst window measures the machine.** On 2026-10-09 the kwin lane's
frames now and then took three times as long as usual (llvmpipe and KWin's software compositing
sharing two processors), and the second-worst of four 2-second reports failed a pacer whose median
was well above the line. The lane now judges the median of six.

**The sandbox has two processors and renders in software.** A 640x360 frame takes 18 ms there, more
than half a refresh, so a timing test measured the machine instead of the pacing until its screen
was made 320x180 (6 ms). Keep timing tests small enough for the machine, or they test the machine.
