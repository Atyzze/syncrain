# Roadmap

Open questions, planned builds, the cadence and the constraints. What shipped: `docs/HISTORY.md`.

## Questions for the operator

* **Default frame rate** (asked 2026-10-07; numbers from their sweep of build 8): 30 fps +11.9 W
  (now), 20 fps +7.3 W, 15 fps +3.5 W. Below about 21 fps the fastest streams skip a row now and
  then. Recommended: `syncrain --fps 20` for a day, then judge by eye.
* **Pause behind maximized windows too, or only full-screen ones?** (2026-10-07) Both now; behind a
  see-through window the rain then stands still. Recommended: both.
* **Build 19: the rest of the review, or the boot splash first?** (2026-10-14) Five middling
  findings are open (M4 to M7, M9; build 18's notes). Recommended: the review first. M4 and M5
  decide whether the login screen works on machines set up unlike theirs (a greetd config of
  their own, a second factor); the splash after.

## Decisions answered

* **2026-10-14 12:10**: a full review of build 17; "Yes, make build 18 please" with M1 to M3 and
  the one-line fixes; on GitHub, "makes sure that the login screen replacement remains fully
  optional, and that those who just want the wallpaper that their existing login method isn't
  touched". Build 18.

* **2026-10-13 15:29**: build 16 works; the box on all screens, always; no Plasma logo or old
  wallpaper between the login and the rain. Build 17.

* **2026-10-13 13:08**: a photo of the broken Plasma wallpaper (all white, all hieroglyphs); "yes,
  make it" (the login screen). Build 16.

* **2026-10-11 19:03**: the Plasma wallpaper "was severely broken"; "stay closer to the barebone
  linux kernel ... our own boot sequence ... the rain ... as the login screen ... then load
  KDE/Plasma"; greetd rather than a login manager of our own. Build 15 drops the Plasma wallpaper;
  build 16 is the login screen.
* **2026-10-11 18:29**: "a json config ... the exact symbol/language-set to include and what %/bias
  if any, or all equally neutral". Build 15.
* **2026-10-10 13:38**: "yes make build 13, the plasma plugin" (asked at 13:28 for a way to start it
  without a terminal, and for the lock and login screens). Builds 13 and 14; the login screen is next.
* **2026-10-10 12:29**: a darker background and less glow in the centre, parameters for speed and
  for how many lanes spawn, the snow off, Egyptian hieroglyphs; a rare glow flare-up; memory "a
  slowdown/plateau ... is this a non issue?", then "dropped back to 170MiB". Build 12.
* **2026-10-09 13:07**: memory still creeps on build 8 ("Will it ever gc and go back down?"); the
  documents: "Keep it minimal please". Builds 10 and 11.
* **2026-10-09 11:36**: build 8 approved for GitHub; a warning before the sweep's black screens.
  Builds 8 and 9.
* **2026-10-09 07:05**: the smallest footprint, power first; does another language help? Build 8.
* **2026-10-09 00:02**: build 8 delivered in the chat, on GitHub only after their trial.
* **2026-10-08**: a documented GitHub repository.
* **2026-10-07**: less power without losing smoothness (builds 4, 5); build numbers, not versions
  (build 3).
* **2026-10-06**: a turning, rainbow NixOS logo against burn-in and an Arch installer (build 2); a
  live, never-repeating, clock-synced wallpaper (build 1).

## Planned builds

1. **The rest of the review of build 17**: M4 to M7 and M9, then the small ones (build 18's notes).
2. **The boot splash**: a still frame of the rain (Plymouth), until the login screen's live one.
3. **A NixOS image** with syncrain as its wallpaper and login screen.

## Build cadence

Consolidation builds: every build number ending in 0, and no other build. Fixed: the operator's
rule, adopted at build 3. A consolidation changes no behaviour: it folds older notes into the
history, makes every document true and short again, and writes down what it finds as open items.

Next consolidation: 20

`tests/contract/test_the_working_documents_are_current.py` reads the two lines above.

## Standing constraints

* **Release**: only `tools/package_release.py` makes an archive and writes `BUILD_NUMBER`; notes in
  the same pass, ending in GATE_RESULT; the gate runs every lane; generated pages are regenerated
  and compared.
* **Picture**: the stream changes only on purpose; the hosts draw the same frame; nothing
  flashes (the fastest colour cycle is 90 s).
* **OpenGL**: never ask GTK for a version; take what it hands out and check it.
* **Writing**: short and plain; no long dashes; "the operator" or "they"; comments say why, not
  when; one home per fact.

## Not scheduled

* A public randomness beacon (drand) in the seed: truly random, still in sync.
* Two screens in the Sway lane (the KWin lane has two).
* Pausing on wlroots compositors that keep asking a hidden wallpaper for frames, if one turns up.
