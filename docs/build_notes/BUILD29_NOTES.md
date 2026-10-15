# Build 29: a video of your look, hidden sentences, readable lists

**Type: feature; the stream changes on purpose** (stream `822ea58a`, was `85ace386`: a sentence's
spaces are gaps in `state.frag`, and a long one's trail outlasts it). Made on 2026-10-15, as the operator asked at 12:52 ("generate a
.gif or .mp4 as recorded/set by their index.html preferences ... a loop ... but we obviously want to
retain the native real dynamic channel") and 13:18 (the lists' white background; "hidden sentences
as well, not just words").

## A video

* `syncrain --video rain.mp4`: 30 s at 1920x1080 of your settings, at 30 fps, from now (or
  `--time`). `--seconds`, `--size`, `--video-fps`; `.mp4` and `.mkv` (H.264), `.webm` (VP9), `.gif`
  (10 s at 640x360 and 15 fps unless told otherwise, one palette for the whole video; a GIF too big
  for memory is refused). Colours in BT.709, said in the file, as players take HD video. Needs
  ffmpeg; without it, it says what to install.
* It is made as `rain.part.mp4` and named `rain.mp4` when whole: Ctrl+C or a failure leaves no half
  video, and an earlier `rain.mp4` stays as it was. The window goes on answering while it works.
* It loops: the first two seconds (half the video, if shorter) are the moments just after its end
  fading into themselves, so the last frame flows into the first. `--loop off` for the moments only.
* Each frame is drawn off the screen at the video's own size and handed to ffmpeg as it is drawn:
  nothing is kept on disk, and 4K works in a small window.
* The page's Settings has a **Video** section: length 10 s to 2 min, sizes 720p to 4K (21:9 and a
  phone's 1080x1920 too), 24 to 60 fps, Loop, **Save video** and **Stop**. It saves WebM (VP9, or
  VP8 where the browser has no VP9 encoder), made frame by frame in the browser, the same frames as
  `--video`. Inside the claude.ai viewer it saves through the viewer's own save; the other settings
  stand still while it is made.
* The live rain stays the default: a video repeats and plays the same everywhere, the live rain
  never repeats and follows the clock. Whether a video costs fewer watts is not measured yet (no
  graphics card here): try it on your machine before counting on it.

## Hidden sentences

* `--words "WAKE UP NEO,AI"` and the page's Hidden words: a word or a sentence up to 30 characters
  (was 16), a space falling as a gap. Every host draws them, the native wallpaper and lock screen
  too, and the NixOS module takes them.
* A word falls only where a column has rows for it and three to spare at each end: 30 characters on
  a 16:9 screen, 21 on a 21:9 one. A long sentence's trail lasts longer than it, so its first letters
  are still lit when its last one lands.

## Readable lists

* An open list on the page (preset, logo, frame rate and the rest) was light text on the browser's
  white. Its options are now the page's dark sheet with its light text, the chosen one in the accent.

## Also

* An option with only a top (`--record-fps 2000`) said "invalid parse value"; it says the top now.

## From the review (an agent that did not write it)

* Sentences capped at 30, what a 16:9 screen has rows for (40 never fell there), and their trails
  lengthened; the NixOS module took only 16 characters and no spaces.
* `--video` colours tagged BT.709 (untagged, players showed full green about 14% darker); made in
  slices so the window answers; a stopped or failed video leaves nothing and keeps an earlier one;
  GIFs shorter, slower and size-checked (the first default needed about 1 GB of memory); a GIF at
  most 50 fps; the graphics card's size limit checked.
* The page: the viewer's save for the video, VP9 level 5.1 above 2.2 Mpixel, at most 40 Mbit/s,
  the loop's seam exactly one frame whatever the length.
* Left: the page's WebM has no SeekHead (seeking finds its cues later; playing and looping are
  unaffected).

## Tests

* The page's video, decoded: its codec, size and frame count; its frame 0 is the app's moment just
  after the end, and a frame after the fade the app's own moment (closer than a tenth of a second
  on). `--video` and the page's video, frame for frame. Every open list's options readable.
* `--video`'s options, its plan of frames, the blend, the ffmpeg command and a video made from a
  stand-in drawing; a sentence's gaps.

## What the operator does

* `./install.sh` from `syncrain_build_29/`. Machines on 28 and 29 stop matching (the stream).
* For videos, ffmpeg (`sudo pacman -S ffmpeg`), then `syncrain --video rain.mp4`. Or open
  `index.html`, Settings, Video, Save video.

## Verification

432 passed in 1148.26s (0:19:08)
