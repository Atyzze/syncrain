# History

A few lines per build, and the operator's words. The last two builds' notes (19 and 20) are in
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
* **9** (2026-10-09): the sweep warns before its black screens, and a closed terminal or `kill`
  stops it cleanly; memory handed back after the first frames (a cold shader cache had kept 182 MiB;
  in the sandbox 155 MiB became 142). Build 8's sweep on their desktop: build 4's timer 90% even
  and 47% steady; a sweep's rows move by a watt or more from run to run. Gate: 184 passed.
* **10** (2026-10-09): consolidation. About 2,700 lines of documents became about 850; builds 1 to 8
  folded in here. The kwin lane's timing floors set to fit a slow sandbox (median even 75% and
  steady 85% at 60 Hz, 65% and 75% at 141 Hz).
* **11** (2026-10-09): no memory creep on NVIDIA. The native wallpaper grew 0.9 MiB a minute there
  (154 MiB after 44 minutes), flat on Mesa over 55,000 frames. NVIDIA's forum shows the same with
  Mesa's `eglgears_wayland` alone (RTX 5080, driver 610.43.02, egl-wayland2 1.0.2, May 2026):
  +2 MiB a minute, flat with `__NV_DISABLE_EXPLICIT_SYNC=1`. syncrain sets it, and
  `__GL_YIELD=USLEEP`, for its own process. Build 9's review fixed (the sweep saves before it
  prints, survives `nohup`, holds a second Ctrl+C). Gate: 189 passed.
* **12** (2026-10-10): picture options (glow, bloom, background, speed, density, snow), 95 Egyptian
  hieroglyphs from Gardiner's list (stream `c18f8be2`; with `--hieroglyphs 0` build 11's frame to the
  pixel). Build 11 there: 110 MiB at start, 196 after 2.5 h, 217 after 7.6 h, 225 after 18 h, then
  170 at once: freed, not leaked; handed back every five minutes since, with a record. The glow
  flare-up: two hours at 4 frames a second and ten minutes at 30 show none; the screen's brightness
  stays within about 12%. Gate: 204 passed.
* **13** (2026-10-10): the Plasma wallpaper (`--plasma`): a Qt item drawing the native passes inside
  plasmashell, desktop and lock screen. Not delivered: its review came first. The passes moved to
  `syncrain/native/passes.c`. Gate: 214 passed.
* **14** (2026-10-10): build 13's review fixed (a crash when switched away mid-frame, KWin scripts
  left behind, a blank lock screen); run in a real plasmashell in an Arch root. Gate: 214 passed.
* **15** (2026-10-11): your own symbols: a file of sets with weights or shares; 489 shipped glyphs
  (𓆙 among 30 more hieroglyphs), others from the machine's fonts; the themes' atlas 195 glyphs.
  Stream `def5684f`. The Plasma wallpaper removed. Gate: 222 passed.
* **16** (2026-10-13): the rain as the login screen (greetd, KWin, a login box), text login as
  fallback. The Plasma wallpaper's white screen explained: Qt sets the locale, and under Dutch rules
  `strtod` read every option as 1 or 0; numbers now read in the C locale. Gate: 234 passed.
* **17** (2026-10-13): the box on every screen; after a login, Plasma's splash and wallpaper show a
  still frame of the rain. Their login screen before was Plasma Login, not SDDM. Gate: 238 passed.
* **18** (2026-10-14): the first fixes from the review of 17 (below). The login screen stays
  optional: only `--login-screen` changes how the machine logs in, `--login-screen-off` puts back
  what started at boot. In an Arch root build 17's login screen had copied `/etc/shadow` through a
  link; 18's upgrade removed the copy. Gate: 279 passed.
* **19** (2026-10-14): the rest of the review: greetd's own settings kept, a second factor asked in
  the box, a wallpaper chosen since kept, options checked as they are read.
* **20** (2026-10-14): consolidation. Builds 9 to 18 folded in here; the documents checked against
  the code; what stays open listed in `docs/ROADMAP.md`.

## The review of build 17 (2026-10-14)

The operator's Claude doc "Syncrain build 17 code review": 9 middling findings (M), 21 small (L).

* **Fixed in 18**: M1 root copied the user's files through their links; M2 `--login-screen-off`
  guessed SDDM; M3 `last.json` read from `/tmp`; M8 services restarted on 2 and 70; L1 Python 3.10
  and 3.11; L2 a session's quoted words; L3 KWin left running; L4 Text login during a password check.
* **Fixed in 19**: M4 greetd's whole config written; M5 no second factor; M6 a missing picture's
  black screen; M7 the page's `--spin` rounding; M9 one dark screen stopped the trim; L5 to L7, L9,
  L10, L13 to L19.
* **Open**: L8, L11, L12, L20, L21 (`docs/ROADMAP.md`, "Open items").

## The operator's words

* **Before 1** (2026-10-06): "could we not make a dynamically real time generated one? ... others
  can sync into the same stream, say base it on the UTC clock"; a NixOS theme "with snow flakes
  blue/gray/white colors".
* **Before 2** (2026-10-06): "lets have the nix os slowly rotate as well, and cycle through all the
  rainbow colors"; "a simple intaller .sh script".
* **Before 3** (2026-10-07): "a clear build number (instead of these versionings .... stop, no
  'versions', only build numbers)".
* **Before 4** (2026-10-07): "perhaps we can reduce it even further? ... are we using rust/asm/c/cpp
  optimization where possible?"
* **Before 5** (2026-10-07): "it definitely went down linearly together with fps".
* **After 7** (2026-10-08): "can you create a new github depository for this and make sure its
  properly documented?"
* **Before 8** (2026-10-09 00:02 and 07:05): "can we get it as low as realistically possible and
  also make sure it doesnt creep up?"; "do not push to github when done ... so I can try it out
  myself"; "drop the memory leak assumption and instead optimize around minimal memory footprint
  without sacrificing actual fps/watt ratio".
* **After 8** (2026-10-09 11:36): "122 on the other hand feels just right for something like this,
  so, update the github please"; a warning that the sweep's last two phases turn the screens black.
* **After 9** (2026-10-09 13:07): "Will it ever gc and go back down or?"; "Keep it minimal please,
  walls of text arent inviting to read :)".
* **After 11** (2026-10-10 12:29): "I want to be able to make the background more black!"; a
  parameter for the speed, for how many lanes spawn, the snow off; "include egyptian hyroglyphs in
  the symbols as well"; "suddenly it dropped back to 170MiB?".
* **After 12** (2026-10-10 13:38): "shouldnt there be a way to install it as a default theme instead
  of needing to run/trigger it in a console to start?"; "could we apply it to the background of the
  login/lock screen as well? (Without disabling the current login window)"; "yes make build 13, the
  plasma plugin".
* **After 14** (2026-10-11 18:29 and 19:03): "I have yet to see 𓆙"; "I'm also missing arabic symbols
  I mean, and russian, and french and japanese ... this calls for a json config, where one can
  explicitly inspect/set the exact symbol/language-set to include and what %/bias if any, or all
  equally neutral"; "I tried the plasma wallpaper but that was severely broken ... stay closer to
  the barebone linux kernel"; "yes, lets incorporate greetd".
* **After 15** (2026-10-13 13:08): a photo of the Plasma wallpaper, all white and all hieroglyphs;
  "yes, make it".
* **After 16** (2026-10-13 15:29): "Success!"; "I want it displayed always on all screens"; "the kde
  login logo with a black screen and then for 1s I still saw my old static wallpaper".
* **After 17** (2026-10-14 12:10): "Full in depth code review please"; "makes sure that the login
  screen replacement remains fully optional, and that those who just want the wallpaper that their
  existing login method isn't touched".
* **After 18** (2026-10-14 15:26): "continue as recommended"; "our html page should be designed to
  let you change/try out all the config settings, and select which char sets etc, basically, its a
  live previewer ... and then lets you export/save the json config file"; "fix the bugs first of
  course".
* **Standing**: no long dashes in anything written to them.
