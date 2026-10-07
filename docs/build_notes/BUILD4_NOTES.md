# Build 4: power, measured on the operator's card, and two cuts that keep the picture

**Type: feature (measurement) and an efficiency fix; the picture does not change.** Made on
2026-10-07 from the operator's messages after build 3: at 02:52, "it works perfectly ... noticed my
gpu uses 20 more watts when having it run tho, which is exactly why I dont think it'll ever get
popular as a main desktop background"; at 03:02, after measuring the GIF wallpaper too, "the gif
actually takes just as much extra power but from the gpu instead, a little more even 20W ....
perhaps we can reduce it even further? ... are we using rust/asm/c/cpp optimization where
possible? could we reduce wattage needed without gimping the smoothness/fps too much?". Build 4
draws build 3's frames pixel for pixel (three moments and the matrix theme compared at 1280x720).

## 1. What the 20 W is, as far as the sandbox can tell

A GIF that the processor decodes and syncrain's six shader passes cost the operator's card the same
20 W, so most of it is the card leaving its idle state for any picture that changes thirty times a
second, not the amount of drawing. On the software renderer here, at 1920x1080, a frame's work is
88% the composite pass (half of that the snow), 9% the two bloom blurs, 3% the rest
(`syncrain --benchmark`); a desktop GPU should do the whole frame in a small fraction of its
capacity, which the benchmark on the operator's card will show. The
host side (Python and the driver issuing about forty OpenGL calls) took 0.85 ms of one CPU thread
per frame; Rust or C would save part of that, which is processor time, not the card's watts.

## 2. GTK's OpenGL renderer for our windows (`syncrain/app.py`, `use_gl_renderer`)

GTK 4.16 and later draw Wayland windows with Vulkan when they can (GTK 4.22.5 `gsk/gskrenderer.c`),
and a GLArea's OpenGL texture then reaches Vulkan every frame either through a dmabuf, if the GL
driver can export one (`gsk/gpu/gskvulkanframe.c`), or through a download to the processor and an
upload back: a full screen per frame per screen. syncrain now sets `GSK_RENDERER=gl` unless the
user set it, and GTK's OpenGL renderer uses the texture where it is. The sandbox never exercised
GTK's Vulkan path (its only Vulkan device is a CPU one, which GTK refuses), so build 3 shipped the
path the operator's desktop takes untested. The startup line and `--diagnose` now name the
renderer; the power sweep measures both.

## 3. Less processor time per frame (`syncrain/renderer.py`)

Uniforms that never change (the theme, the channel, the texture units, the snow tables, the motion)
are set once when the programs are built; a frame sets the clock and what depends on the viewport.
Host CPU per frame 0.846 ms to 0.639 ms (the sandbox, 200 frames). Every frame identical.

## 4. `syncrain --benchmark` and `syncrain --power-sweep`

`--benchmark` (`syncrain/bench.py`) draws offscreen at the first screen's size and reports each
pass's GPU time (timer queries on desktop OpenGL; it asks GTK for desktop OpenGL first) and the host
CPU per frame. `--power-sweep` (`syncrain/power.py`) is the operator's measurement: nine phases of
25 s (nothing; as installed; 20, 15 and 10 fps; half resolution; GTK's Vulkan renderer; the matrix
theme; covered by a full-screen window from `syncrain/cover.py`), each a real wallpaper, the card's
power from `nvidia-smi` (streaming, one process) or the amdgpu power sensor, the first 8 s of each
phase discarded; a table and `~/syncrain-power-<utc>.json`. It refuses to run beside another
syncrain. In a headless Sway, a wallpaper covered by a full-screen window drew no frames at all
(the compositor stops asking for them); whether KWin does the same is one of the sweep's rows.
`SYNCRAIN_DEBUG_FPS` now takes the report interval in seconds, and each report names its screen.

## 5. What the operator does

* Install build 4 (`./install.sh` from `syncrain_build_4/`).
* For a fair "nothing", give Plasma a still picture as its wallpaper; stop the autostart service if
  it runs (`systemctl --user stop syncrain`); then `syncrain --power-sweep` (about four minutes; the
  screens turn black for the last phase), and send the JSON file it names.
* The KDE icons question stays open (`docs/ROADMAP.md`).

## Verification

108 passed in 264.66s (0:04:24)

Before the gate, by hand: the frames of build 3 and this tree compared at three moments (identical);
the sweep run under Xvfb and under a headless Sway with a stand-in power reading (every phase ran,
nothing left behind; covered drew 0 frames a second in Sway). Not measured: any real card's watts,
GTK's Vulkan renderer (the sandbox cannot run it), KWin.
