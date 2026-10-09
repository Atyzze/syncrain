# Lessons

Rules learned by shipping their opposite, one line each. When and how: `docs/HISTORY.md`.

## Drivers, OpenGL and GTK

* **Never ask GTK for an OpenGL version.** It hands out OpenGL ES; asking for "3.3" drew nothing on
  NVIDIA. Take what comes and check it.
* **Force the failures the sandbox can't have.** Mesa hides what NVIDIA refuses, so the lanes run
  OpenGL ES only, desktop OpenGL only, and none.
* **A wallpaper that cannot draw leaves at once**, with status 69, which the service won't restart.
* **On a fast card the watts are a frame count**: about 0.17 J a frame per screen. Fewer frames
  save power; faster code or fewer pixels barely do.
* **Copies cost more than drawing**: GTK's Vulkan hand-over cost 25.5 W, its OpenGL path 10.6 W.
* **A language buys memory and processor time, not watts**: in C, 123 MiB and 0.9% of a core;
  Python and GTK, 205 MiB and 4.7%; the card's watts the same.
* **Memory is mostly what a program loads** (interpreter, toolkit, driver); syncrain's own state is a
  few MiB.
* **GTK shares GL objects between all contexts of a display**: delete a widget's own objects when it
  goes, or every screen change leaks (build 7: 120 MiB each).
* **GTK 4.16+ sends GLArea frames out as dmabufs and back in**, unless `GDK_DISABLE=dmabuf`.
* **A cold shader cache leaves memory in the heap** until it is handed back (`malloc_trim` after the
  first frames).
* **NVIDIA's Wayland driver leaks a fixed amount per frame with explicit sync on**; flat on Mesa.
  `__NV_DISABLE_EXPLICIT_SYNC=1` stops it.
* **C that must match Python must do Python's arithmetic**: float `//`, `round`, the order of
  operations. Compare both, printed exactly.

## Frame timing

* **Draw each frame for the refresh it is shown on**, not the moment it is asked for.
* **Move the lead both ways**, by what the compositor reports; one that only grows shows frames
  early.
* **Ignore frames reported long after their refresh** (a locked screen), or each lock moves the
  lead.
* **Judge timing tests by the median**: the sandbox's software renderer spikes.

## KDE and Wayland

* **Plasma's desktop sits on the background layer**, so syncrain takes the bottom layer there.
* **KWin asks covered wallpapers for frames; Sway doesn't.** Ask KWin's scripting which screens a
  window covers.
* **To KWin, syncrain is an ordinary window**: "show desktop" hides it.
* **KWin numbers scripts by count**, so a new script can get a running one's number;
  `Scripting.start` runs them all.
* **A KWin script runs on KWin's main thread**: read the cheap properties first.
* **`QTimer.start()` restarts a running timer**: start it only when it is idle.
* **Exit with status 1 when the compositor goes**, as GTK does, or the service never restarts you.
* **gtk4-layer-shell must load before libwayland-client.**

## Launching, services, releases

* **`python -m` puts the current directory first**: the launcher sets `PYTHONSAFEPATH=1`.
* **systemd unescapes inside single quotes**: double each `\`, `%` and `$`, then quote.
* **"syncrain" in a command line is not a syncrain**: read the argument list.
* **Two trees under one name is what build numbers prevent.**
* **A reviewer who didn't write the build finds what the gate can't.**
* **Generated files go stale silently**: the release regenerates them and the gate compares.

## Rendering and sync

* **Time as a float since 1970 loses the fraction**: whole seconds since 2024 plus the fraction.
* **Anything periodic needs whole cycles per hour**, or it jumps when the hour restarts.
* **Atlas lookups need explicit gradients**, or cell edges pick the wrong mip level.
* **Integer hashing is the only randomness bit-exact on every GPU.**
* **A loop shows on a wallpaper within seconds** (the GIFs before build 1).

## The sandbox

* It restarts and keeps only files; the lanes start their own displays.
* `pkill -f` and `pgrep -f` match their own shell; stop processes by PID.
* A script named after a standard module replaces it.
* A heredoc ends at its terminator, even inside the text; tool parameters decode JSON escapes.
* Two cores and software rendering: keep timing tests small.
* A Unix socket path over 108 bytes fails: keep runtime directories short.
