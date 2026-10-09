# History: the GIFs to build 8

Where each build's notes are kept, a line for what each build did, and the operator's decisions in
their own words. Builds 1 to 8: `docs/build_notes/BUILD<n>_NOTES.md` (all of them, until a
consolidation folds the older ones in here). The rules the builds taught are in `docs/LESSONS.md`.

## Before build 1: the GIFs (2026-10-06)

Five GIFs, each from the operator's photo of a TV showing the CachyOS wallpaper, then from the
4K wallpaper itself: green "AI matrix" code rain over the photo; the screen alone, without the
room; the mouse pointer removed; 1440p from the 3840x2160 original the operator supplied; a darker
version with more variety in how bright the letters light up. Kept, as a loop, by a cyclic
stabiliser and an ffmpeg palette with Bayer dithering (gifsicle's lossy mode was dropped: it
popped at the seam). Set as a wallpaper, the 4 to 6 second loop became visible within seconds,
which is why syncrain exists.

## Builds

* **1** (2026-10-06): the live wallpaper. A frame from the UTC clock and a channel, six GPU passes,
  the nixos theme (snow, blue, the official NixOS snowflake) beside matrix, the native app (GTK 4,
  layer-shell and X11), the web page, the Nix flake with NixOS and home-manager modules. Delivered
  as `syncrain-0.1.0.tar.gz` with a preview video and the live page.
* **2** (2026-10-06): against burn-in, the logo turns every 3 minutes, cycles through the rainbow
  every 90 seconds and drifts; `--rainbow all`; an installer for Arch-based systems, tested in a
  real Arch root. Delivered as `syncrain-0.1.0.tar.gz` again: a second tree under the first one's
  name. On the operator's CachyOS desktop it never drew (grey screen; fixed in 3).
* **3** (2026-10-07): build numbers instead of versions; GSD's way of keeping a project (the
  release tool, six lanes, these documents); the grey-screen fix and `syncrain --diagnose`. It works
  on the operator's desktop; their card draws about 20 W more with it, and the same with their GIF.
* **4** (2026-10-07): power. GTK's OpenGL renderer instead of a hand-over to Vulkan each frame, a
  quarter less processor time per frame, and `--benchmark` and `--power-sweep` to measure the rest
  on the operator's card. Their sweep (an RTX 5090): +10.6 W at 30 fps, half of the Vulkan path's
  +25.5 W; the watts follow the frames, not the pixels; covered, it still drew at full rate.
* **5** (2026-10-07): nothing drawn that nobody sees, and every frame drawn for the moment it is
  shown. On KDE Plasma a screen under a maximized or full-screen window is not drawn (KWin is asked
  through a script it runs); frames land on whole refreshes and are drawn for the refresh they are
  shown on; a headless KWin 6.7.5 in the release's lanes.
* **6** (2026-10-07): what a review of build 5 found, fixed. The lead before each frame follows what
  GTK reports, so frames stay on time at 141 Hz (86 to 100% steady, from 74 to 84%); the KWin script
  starts even when KWin reuses its number, cleans up after a crashed syncrain, and costs KWin less
  while a window is dragged. Made and gated, not delivered: its own review found that the script's
  answer waited for a drag to end.
* **7** (2026-10-07): build 6 with what its review found, fixed: a screen uncovered by a drag draws
  again during the drag; a locked screen no longer moves the lead; a leftover script's process is
  recognised by its command.
* **8** (2026-10-09): memory and the processor, the picture unchanged. On Wayland the wallpaper is
  a C program with neither Python nor GTK in memory (the native wallpaper): in the sandbox about
  136 MiB against build 7's 308 for two screens, the same frames to the pixel, with half the
  processor time around each frame. The Python and GTK host, still drawing everywhere else, drops
  PyOpenGL and numpy, GTK's dmabuf round trip, and the 120 MiB build 7 kept after every screen
  change. The power sweep shows each phase's processor time, memory and what drew it. Delivered in
  the chat for the operator to try before it goes to GitHub, as they asked.

After build 7 (2026-10-08) the tree went to GitHub, github.com/Atyzze/syncrain: the commit
`syncrain build 7` is the archive as delivered, and the commits after it changed no behaviour
(documentation, with a README for visitors and a picture of each theme; package metadata; a test's
comment; the generated pages marked as generated for GitHub). No build was made for them; build 8
carries them.

## The operator's decisions, in one place

* Before build 1: "could we not make a dynamically real time generated one? where we based it off
  some genuine random process so that there is never a repeat and then also make it possible so
  others can sync into the same stream, say base it on the UTC clock", "we want to aim for linux
  of course, it might become part of a nixOS image", a NixOS theme "with snow flakes blue/gray/white
  colors", and "instead of the C In the middle, use the nixos actual logo".
* Before build 2: "lets have the nix os slowly rotate as well, and cycle through all the rainbow
  colors potentially as well, as to have the screensaver als function as a basic pixel cleaner",
  and "have it work on arch based OSs basically, with a simple intaller .sh script attached".
* Before build 3: "can you adopt the good architecture/code-base management practices from this
  codebase, such as a clear build number (instead of these versionings .... stop, no 'versions',
  only build numbers)", with GSD592.
* Before build 4: "the gif actually takes just as much extra power but from the gpu instead, a
  little more even 20W", "perhaps we can reduce it even further? so that we can justify it as an
  actual wallpaper not being too power hungry", "are we using rust/asm/c/cpp optimization where
  possible? could we reduce wattage needed without gimping the smoothness/fps too much?"
* Before build 5 (12:19), with their sweep's table: "it definitely went down linearly together
  with fps".
* After build 7 (2026-10-08): "can you create a new github depository for this and make sure its
  properly documented?"
* Before build 8 (2026-10-08 22:33, with btop showing build 7 at 287 MiB): "can we get it as low as
  realistically possible and also make sure it doesnt creep up? we want to keep the
  look/feel/smoothess of the current default 60fps settings and reduce the power/cpu needed as much
  as possible ... do not change any functionality, only performance gains are of interest, less
  memory (no leaks, should we do it all rust native maybe instead of python?)"; then "do not push to
  github when done, instead, just deliver the new build here in chat so I can try it out myself
  before we commit it"; and at 07:05 the next morning, with build 7 at 420 MiB after the night:
  "drop the memory leak assumption and instead optimize around minimal memory footprint without
  sacrificing actual fps/watt ratio, because even more important is power usage down, so I'm really
  interested to see whether or not a full rust, c, asm, cpp or any other languages has anything to
  offer here."
* Standing, from the start: no long dashes in anything written to them.
