# Where we are, at build 9

The whole project on one page, in plain words. Every build keeps it current
(`tests/contract/test_the_working_documents_are_current.py`); the detail is in `docs/agent/HANDOFF.md`.

## What syncrain is

A live wallpaper of falling code that never repeats. It is drawn fresh every frame from the clock
and a channel name, so everyone on the same channel sees the same rain at the same moment, on
Linux (Arch family, NixOS) or in a browser. The NixOS theme has blue rain, snow and the NixOS
snowflake turning slowly through the rainbow, which keeps anything bright from burning into a
screen. It grew out of the green matrix GIFs over the CachyOS wallpaper, once the loop in a GIF
became visible after a few seconds.

## Where it stands

* **It works on your machine** (builds 3 to 8), on both screens. You run build 8; build 9 adds the
  sweep's warning. Both are on GitHub.
* **Build 8 is the wallpaper without Python or GTK in memory.** On Wayland, `syncrain` hands over
  to a small C program that draws the same frames, pixel for pixel. On your RTX 5090 (your sweep):
  123 MiB and 0.9% of one core at 30 fps, against 205 MiB and 4.7% for Python and GTK, and 287 to
  420 MiB for build 7. The card's watts follow the frames in any language (+11.9 W and +10.6 W for
  the two, within a sweep's run-to-run spread); what C saves is memory and processor time. Where it
  cannot draw, Python and GTK take over by themselves, and neither keeps memory after a screen wakes
  from sleep any more (build 7 kept about 120 MiB each time).
* **Build 9** warns, before the sweep starts, that all your screens go black in its last two
  phases; closing its terminal no longer leaves the black windows behind; and the wallpaper hands
  back what its first start with a cold shader cache left in memory (your sweep's 182 MiB row).
* **Your sweeps answered the power question.** On your RTX 5090 syncrain costs about 11 W at 30
  frames a second (10.6 W in build 4's sweep, 11.9 in build 8's), half of what it cost through
  GTK's Vulkan path (25.5 W) and about half of your GIF. The watts follow the number of frames, not
  what is in them: 20 fps costs about 7 W, 15 fps 3.5 to 5 W, while half the pixels saves only
  1.2 W. So a faster language shaves the processor's part; what saves the card's power is fewer
  frames, and none that nobody sees.
* **Build 5 draws nothing nobody sees.** KDE's compositor kept asking a covered wallpaper for frames
  (your sweep: 11 W under a full-screen window, for nothing). syncrain now asks KWin which screens a
  maximized or full-screen window covers and stops drawing those until they show again.
* **Build 5 times every frame to your screens' refresh**, and draws it for the moment it is shown.
  Before, a timer started frames slightly out of step with the screen, so the motion stumbled now
  and then. Tested in a real KWin (6.7.5) that now runs with every release.
* **Build 7 fixes what reviews of builds 5 and 6 found**: frames stay on time on fast screens too
  (tested at 141 Hz); the KWin script starts reliably, cleans up after itself and costs KWin less
  while you drag a window; a screen a dragged window leaves draws again at once. (Build 6 was made
  but not sent: its review found that last fault.)
* **On KDE Plasma it covers the desktop icons**, and "show desktop" hides it; clicks still reach the
  desktop.
* **It is on GitHub** (github.com/Atyzze/syncrain), with a README for visitors and a picture of
  each theme. Each build goes there as one commit, `syncrain build <N>`; builds 8 and 9 are there.

## What comes next

* **Build 10**: a consolidation build, fixed: no new behaviour; the documents made true again.
* **Build 11**: your answers below.
* **Later**: the KDE plugin (below), syncrain in a NixOS image, the rest of `docs/ROADMAP.md`.

## The decision in front of you

1. **The default frame rate**, from your sweep of build 8 (two screens): (1) 30 fps, +11.9 W, as now;
   (2) 20 fps, +7.3 W; (3) 15 fps, +3.5 W. Below about 21 fps the fastest rain streams sometimes skip
   a row. Recommended: try `syncrain --fps 20` for a day and judge by eye.
2. **Pause behind maximized windows too, or only full-screen ones?** Builds 5 and 7 do both; the
   catch is a see-through window (a translucent terminal), behind which the rain would stand still.
   Recommended: both.
3. **Your desktop icons on KDE.** (a) Keep it as is; (b) a Plasma wallpaper plugin: syncrain becomes
   a wallpaper you pick in Plasma's own settings, behind the icons and part of Plasma's desktop; a
   build of its own, and you would be its first test; (c) for now, the browser version in an
   existing Plasma web-wallpaper plugin. Recommended: (b), (c) meanwhile.

## Words you will see

* **build**: one numbered archive; the only kind of version this project has. **channel**: the
  name everyone in one stream shares. **stream id**: eight characters that name what decides the
  picture; equal ids and channels draw equal frames. **pass**: one of the six drawing steps of a
  frame. **refresh**: one picture of your screen (60 a second at 60 Hz). **gate**: the full test run
  a release must pass. **consolidation**: a build that changes no behaviour and makes the documents
  true again.
