# Lessons

Rules learned by shipping their opposite, one line each. When and how: `docs/HISTORY.md`.

## Drivers, OpenGL and GTK

* **Never ask GTK for an OpenGL version.** It hands out OpenGL ES; asking for "3.3" drew nothing on
  NVIDIA. Take what comes and check it.
* **Force the failures the sandbox can't have.** Mesa hides what NVIDIA refuses, so the lanes run
  OpenGL ES only, desktop OpenGL only, and none.
* **On a fast card the watts are a frame count**: about 0.17 J a frame per screen. Fewer frames
  save power; faster code or fewer pixels barely do.
* **Compare watts within one sweep**: a row moves by a watt or more from run to run.
* **Copies cost more than drawing**: GTK's Vulkan hand-over cost 25.5 W, its OpenGL path 10.6 W.
* **A language buys memory and processor time, not watts**: C 123 MiB and 0.9% of a core, Python
  and GTK 205 MiB and 4.7%. Most of either is what the program loads; syncrain's own state is a few MiB.
* **GTK shares GL objects between all contexts of a display**: delete a widget's own objects when it
  goes, or every screen change leaks (build 7: 120 MiB each).
* **GTK 4.16+ sends GLArea frames out as dmabufs and back in**, unless `GDK_DISABLE=dmabuf`.
* **The C heap keeps freed memory until asked** (`malloc_trim`): memory that falls by itself was
  freed, not leaked; a cold shader cache leaves tens of MiB there.
* **NVIDIA's Wayland driver leaks a fixed amount per frame with explicit sync on**; flat on Mesa.
  `__NV_DISABLE_EXPLICIT_SYNC=1` stops it.
* **C that must match Python must do Python's arithmetic**: float `//`, `round`, the order of
  operations. Compare both, printed exactly.
* **Python rounds halves to even, JavaScript up**: say which, in both, when the two must agree.
* **Two rasterizers round an 8-bit blur differently**, and a gain multiplies it: compare page and
  desktop where the gain is small, and every other pass with it off.
* **An untagged HD video is shown as BT.709**; ffmpeg's untagged default is BT.601. Convert to
  BT.709 and say so in the file.

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
* **gtk4-layer-shell must load before libwayland-client.**
* **A Qt program sets the locale**: `strtod` then reads "0x1.8p-1" by Dutch rules. Parse numbers
  in the C locale (`c_strtod`).
* **A toolkit's item inside someone else's shell breaks where no lane can see** (builds 13 and 14's
  Plasma wallpaper). Our own program, on our own surface, holds up.
* **One screen that never draws must not hold up what all screens share** (the memory trim).
* **Plasma's lock screen is Plasma's**: KWin 6 lets no other locker in; change what it shows, not
  which locker runs (`docs/ARCHITECTURE.md`).
* **kscreenlocker refuses a PAM start inside its delay** (3 s after a refusal in 6.7): ask again
  after it, or the box loops and wipes the field.
* **Each screen of a lock screen is its own QML root**: what all screens share (PAM, the typed
  text) lives in a singleton, or a screen plugged in again cannot unlock.

## The login screen

* **GTK waits seconds for the desktop portal** where there is none: `GDK_DEBUG=no-portals`.
* **greetd's PAM does not open KDE's wallet**; SDDM's does. Add its lines, as SDDM has them.
* **greetd joins a command's words with spaces and has sh run them**: send one word, quoted for sh.
* **greetd signals the greeter alone**: a greeter that starts a compositor in its own session
  stops it on SIGTERM.
* **PAM may ask more than once**: answer the first password prompt with the password and show
  the rest, in its own words.
* **Change only your part of someone else's config** (greetd's `[default_session]`), and write to
  the PAM service it names, not the one you expect.
* **root copying a user's file follows the user's links**, and `chmod -R` follows a link it is
  given by name: the user reads, root only writes, into a folder root made.
* **A shared folder such as /tmp is no fallback for state**: any user can leave a file there.
* **A record of what to put back lives outside what gets removed**, goes last, and counts only
  while what replaced it still runs. Without one, leave things as they are rather than guess.

## Launching, services, releases

* **`python -m` puts the current directory first**: the launcher sets `PYTHONSAFEPATH=1`.
* **systemd unescapes inside single quotes**: double each `\`, `%` and `$`, then quote.
* **With RestartSec=3, systemd's start limit never trips**: every status a restart cannot change
  (2, 69, 70, 78) goes in RestartPreventExitStatus, or the service retries it for good.
* **Exit with status 1 when the compositor goes**, as GTK does, or the service never restarts you.
* **"syncrain" in a command line is not a syncrain**: read the argument list.
* **Two trees under one name is what build numbers prevent.**
* **A reviewer who didn't write the build finds what the gate can't.**
* **Generated files go stale silently**: the release regenerates them and the gate compares.
* **The lanes run a newer Python than pyproject.toml promises**: f-strings changed in 3.12, so a
  test reads the app as 3.10 and 3.11 do.

## Rendering and sync

* **Time as a float since 1970 loses the fraction**: whole seconds since 2024 plus the fraction.
* **Anything periodic needs whole cycles per hour**, or it jumps when the hour restarts.
* **Atlas lookups need explicit gradients**, or cell edges pick the wrong mip level.
* **Integer hashing is the only randomness bit-exact on every GPU.**
* **A loop shows on a wallpaper within seconds** (the GIFs before build 1).
* **A frame is a function of the clock**: for a fault seen on screen, ask for the minute, and draw
  that moment again.
* **A limit has to fit the screen it falls on**: 40-character sentences never fell where a column
  has 36 rows. Test what a user sees, not only what the data holds.
* **A new default can make old tests pass without testing anything** (snow on, a black
  background): run them where the option still shows.

The traps of the sandbox itself: `docs/agent/ENVIRONMENT.md`, "Traps".
