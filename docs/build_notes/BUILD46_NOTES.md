# Build 46: the lock screen's frame, the GTK host at a fractional scale, a logo file on the page

**Type: fix** (the stream does not change). Made on 2026-10-16, the last of the builds on the
roadmap's open items that can be done without the operator's machine.

## The lock screen's frame was never darker

* The lockscreen lane found the lock screen's frame about 2% darker than the desktop's, in
  proportion to brightness, and the cause was open. It is the lane, not the lock screen: the lane's
  Qt comes from Nix with Mesa 26.2, the GTK host it was compared with ran on the system's Mesa 25.2,
  and the two versions' llvmpipe differ by that much. The native wallpaper built from the same
  nixpkgs draws exactly the lock screen's frame (the native wallpaper on Mesa 25.2 draws the GTK
  host's to the pixel).
* The lane now builds that native wallpaper with the lock screen and compares the two to the pixel,
  instead of within a level: a real difference would now show.

## The GTK host at a fractional scale

* At 1.25 (and any scale between whole ones) GtkGLArea's framebuffer has the next whole scale's
  pixels and the compositor shrinks it: the GTK host drew the frame of a screen 1.6 times larger,
  shrunk, softer and not quite the native wallpaper's (2.6 levels apart on average). GTK 4.22
  still does this.
* The GTK host now draws the screen's own pixels (GTK 4.12 on gives the exact scale) and blows each
  up whole into GtkGLArea's framebuffer; the compositor's shrinking lands on them again: 0.26
  levels from the native wallpaper's frame. At a whole scale nothing changes (still to the pixel).
  The native wallpaper, Wayland's default, was and is exact. A still (`--screenshot`) and a
  record keep the framebuffer's pixels, the size their files have.

## A logo file on the page

* A settings file whose `"logo"` is a picture file's path (written by hand, `"logo": "mine.png"`)
  was refused by the page. The page now keeps it, as it keeps `background`: the preview shows the
  preset's logo, and the file it saves names the picture again while no other logo is picked there.
  Both sides tell a file from a logo's name by the same rule, a name ending .png, .jpg, .jpeg,
  .webp, .gif, .bmp, .tif, .tiff, .ico, .svg or .svgz; a settings file's logo that is neither a
  name nor such a path is refused on both (the desktop took any file it could open, the page none).
* On the desktop, a settings file's logo picture moved since is left out, said, and the preset's
  logo is drawn, as for a background since build 45.

## The review of this build

An agent that did not write it read it: nothing critical. Fixed: the page and the desktop told a
logo file apart differently (the rule is now one, wider, and the desktop refuses what the page
refuses); a still or a record could have been drawn the new way had the scale been known at the
first frame; the screen's pixels are now taken from the window's size and the exact scale (so a
GTK that someday sizes the framebuffer exactly is left alone, and the rounding is the native
wallpaper's); `--scale` above 1 at a fractional scale; the new lane helper could hang or leave a
process behind; a whole scale is now checked to the pixel.

## What the operator does

* Nothing.

## Verification

571 passed in 1562.21s (0:26:02)
