# Target environment

Where syncrain runs, as far as this tree knows it. The build sandbox is
`docs/agent/ENVIRONMENT.md`.

## The operator's desktop

* **CachyOS** (Arch-based, with CachyOS's own repositories for Zen 4 and Zen 5 CPUs), **KDE Plasma 6
  on Wayland**, Konsole with the **fish** shell, **two screens**. Python 3.14, gtk4-layer-shell
  1.3.0 (from `cachyos-extra-znver4`), python-opengl 3.1.10 (which build 8 no longer uses), as of
  2026-10-07. Pacman runs Limine
  and snapper hooks that take a btrfs snapshot around every transaction.
* The same machine as GSD's research host (AMD Ryzen 9 9950X3D, 16 cores, about 92 GiB of RAM),
  so a heavy syncrain setting competes with a running study: 30 fps is the cap; `--fps 15` halves
  the frames and `--scale 0.75` draws 56% of the pixels.
* **The graphics card is an NVIDIA GeForce RTX 5090** (build 4's power sweep, 2026-10-07 12:19),
  which also explains build 2's failure: NVIDIA's EGL will not share contexts across OpenGL and
  OpenGL ES. With both screens on, the card idles at 50.4 W with its memory clock at full speed
  (14001 MHz), so a frame's cost is the card's graphics side waking for it.
* **What syncrain costs there** (build 4's sweep, `docs/build_notes/BUILD4_NOTES.md` and build 5's
  notes): +10.6 W at 30 fps through GTK's OpenGL renderer, +25.5 W through GTK's Vulkan renderer
  (build 3's path); +6.9 W at 20 fps, +5.0 W at 15, +3.0 W at 10; half resolution saves 1.2 W and
  the matrix theme 1 W; covered by a full-screen window it still drew 60 frames a second for
  +11.0 W, because KWin keeps asking a covered wallpaper for frames (build 5 stops that). Build 3 ran
  there from 02:52 ("it works perfectly"); the GIF wallpaper before it cost a little more than 20 W.
* **What build 7 kept in memory there** (btop, 2026-10-08 and 09): 287 MiB resident at boot, 291
  and 299 within minutes, 331 after 37 minutes, 402 after 1 h 22, 382 ten minutes later, and 420
  after a night (about 9 h). The operator read the falls and the plateau as the garbage collector's
  ebb and flow, not a leak, and asked for the footprint itself to come down instead. Build 7 did
  keep about 120 MiB more after every screen change (in the sandbox), and a DisplayPort screen
  waking from sleep is one, so some of those steps may have been that; build 8 keeps nothing after
  one.
* **Build 8 there** (their sweep, 2026-10-09 09:32 UTC, `docs/build_notes/BUILD9_NOTES.md`): the
  native wallpaper draws with NVIDIA's EGL ("OpenGL ES 3.2 on NVIDIA GeForce RTX 5090/PCIe/SSE2"),
  at 123 MiB and 0.9% of one core at 30 fps (the GTK host: 205 MiB, 4.7%), +11.9 W at 30 fps
  against +10.6 W for the GTK host in the same sweep, within the rows' run-to-run spread; covered
  screens cost nothing. Its first phase kept 182 MiB, most likely the native program's first start
  there, with NVIDIA's shader cache still cold. The operator: "122 on the other hand feels just
  right for something like this".
* They unpack archives under `/data/projects/nixOS/liveWallpaper/` (a browser's duplicate
  download gave one folder a name with a space and brackets, which the installer handles) and
  install with `./install.sh`; build 3 is installed there.
* On Plasma, syncrain takes the bottom layer and covers the desktop icons
  (`docs/ROADMAP.md`, the open question). KWin takes it for an ordinary window (its layer-shell
  namespace names no window type), so KWin's "show desktop" hides it and shows Plasma's own
  wallpaper.
* **Plasma's version** is not known exactly; CachyOS follows Plasma's releases closely, so 6.7 or
  later in October 2026. The kwin lane runs KWin 6.7.5 from nixpkgs.

## NixOS

The starting idea: syncrain as part of a NixOS image. The flake's package and modules are
evaluated and built every release (`tests/nix/`); no NixOS machine has run them yet.

## What every target needs

`docs/OPERATIONS.md`, "What it needs", the one place it is kept (the README repeats it in a line
for visitors to the repository).
