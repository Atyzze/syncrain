# History

A few lines per build, and the operator's words. The last two builds' notes are in
`docs/build_notes/`; the rules they taught are in `docs/LESSONS.md`.

## Before build 1 (2026-10-06)

Five looping GIFs of code rain over the CachyOS wallpaper. As a wallpaper, the 4 to 6 second loop
showed within seconds, which is why syncrain draws every frame from the clock.

## Builds

* **1** (2026-10-06): the live wallpaper. Frames from the UTC clock and a channel, six GPU passes,
  the nixos and matrix themes, the GTK app (layer-shell, X11), the web page, the Nix flake.
  Delivered as `syncrain-0.1.0.tar.gz`.
* **2** (2026-10-06): against burn-in the logo turns, cycles through the rainbow and drifts; an Arch
  installer. Delivered under the same name as build 1. On the operator's desktop it drew nothing:
  it asked GTK for OpenGL "3.3", which NVIDIA's EGL refused.
* **3** (2026-10-07): build numbers, the release tool, the test lanes and the documents, adopted
  from the operator's GSD project; the grey-screen fix; `--diagnose`. Works on their desktop.
* **4** (2026-10-07): power. GTK's OpenGL renderer instead of a Vulkan hand-over each frame;
  `--benchmark` and `--power-sweep`. Their sweep (RTX 5090): +10.6 W at 30 fps against +25.5 W via
  Vulkan; the watts follow the frames (+6.9 W at 20 fps, +5.0 W at 15); half the pixels saved
  1.2 W; a covered wallpaper still drew at full rate (+11 W).
* **5** (2026-10-07): covered screens not drawn on KDE (a script loaded into KWin); every frame drawn
  for the refresh it is shown on; a headless KWin 6.7.5 in the lanes.
* **6** (2026-10-07): a review of 5, fixed: the lead follows what GTK reports (on time at 141 Hz);
  the KWin script survives a reused number, a crash and drags. Not delivered: its own review found
  that a dragged window's screen stayed paused until the drag ended.
* **7** (2026-10-07): 6 with that fixed, and a locked screen no longer moves the lead. Went to
  GitHub on 2026-10-08 with a README for visitors.
* **8** (2026-10-09): on Wayland a native wallpaper in C, with no Python or GTK in memory. On the
  operator's desktop: 123 MiB and 0.9% of a core at 30 fps (build 7: 287 MiB at boot, 420 later);
  the same frames to the pixel. The GTK host lost PyOpenGL, numpy and GTK's dmabuf round trip, and
  no longer kept 120 MiB per screen change. The sweep shows CPU and memory. Tried by the operator
  before it went to GitHub.
* **9** (2026-10-09): the sweep warns before its black screens; memory handed back after the first
  frames (a cold shader cache had kept 182 MiB).
* **10** (2026-10-09): consolidation. The documents made short; builds 1 to 8 folded in here.
* **11** (2026-10-09): no memory creep on NVIDIA (explicit sync off for syncrain's own process);
  build 9's review fixed.
* **12** (2026-10-10): picture options (glow, bloom, background, speed, density, snow), Egyptian
  hieroglyphs among the symbols (a new stream); freed memory handed back every five minutes, with a
  record `--diagnose` shows.

## The operator's words

* **Before 1**: "could we not make a dynamically real time generated one? ... others can sync into
  the same stream, say base it on the UTC clock"; a NixOS theme "with snow flakes blue/gray/white
  colors".
* **Before 2**: "lets have the nix os slowly rotate as well, and cycle through all the rainbow
  colors"; "a simple intaller .sh script".
* **Before 3**: "a clear build number (instead of these versionings .... stop, no 'versions', only
  build numbers)".
* **Before 4**: "perhaps we can reduce it even further? ... are we using rust/asm/c/cpp
  optimization where possible?"
* **Before 5**: "it definitely went down linearly together with fps".
* **After 7**: "can you create a new github depository for this and make sure its properly
  documented?"
* **Before 8**: "can we get it as low as realistically possible and also make sure it doesnt creep
  up?"; "do not push to github when done ... so I can try it out myself"; "drop the memory leak
  assumption and instead optimize around minimal memory footprint without sacrificing actual
  fps/watt ratio".
* **After 8**: "122 on the other hand feels just right for something like this, so, update the
  github please"; a warning that the sweep's last two phases turn the screens black.
* **After 9**: "Will it ever gc and go back down or?"; "Keep it minimal please, walls of text arent
  inviting to read :)".
* **After 11**: "I want to be able to make the background more black!"; a parameter for the speed,
  for how many lanes spawn, the snow off; "include egyptian hyroglyphs in the symbols as well";
  "suddenly it dropped back to 170MiB?".
* **Standing**: no long dashes in anything written to them.
