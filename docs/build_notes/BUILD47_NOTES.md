# Build 47: config.json is the default, the lock screen's rest is a setting, a video has no crossfade

**Type: feature; the picture changes** (stream `0aa22037` to `c5c869a0`: the default look is now
the operator's config.json, so machines on build 46 and 47 stop matching). Made on 2026-10-20, from
the operator's reports and requests of that day.

## The lock screen dropped to 10 fps

* The rain fell to about 10 fps after 4 to 6 minutes on the lock screen (seen live while recording).
  It was build 42's rest: five minutes without a key or a moved pointer, then 10 fps. Nothing else in
  the lock screen slows over time (an agent that did not write it checked the item, its timer, the
  QML and PAM's side).
* The rest stays, as a setting, **off by default**: `"lock_rest"` in the settings file (seconds; 0:
  never), `--lock-rest S`, the page's Desktop only, Lock screen rest. It reaches the lock screen in
  its scene (a `lock-rest` line, written only when above 0); `SyncRain.rest` sets `Shared.restMs`.
* With the rest off, NVIDIA's memory in KWin's greeter grows with every frame for as long as the
  screen stays locked (build 11 measured about 1 to 2 MiB a minute at 30 fps); the rest was also
  for that. A lock left overnight: worth a look at the memory, or a rest.

## A video's first seconds were blurred

* The seamless loop faded the moments after a video's end into its first 2 s: two pictures over
  each other, the logo with them. The operator found a video without the loop fine.
* The crossfade is gone, on the desktop (`syncrain/video.py`) and the page (`makeVideo`), with
  `--loop` and the page's "Loop without a seam". Every frame is its own moment; a player repeating
  a video shows a cut at the end.

## config.json is the default

* `config.json` at the top of the tree is the operator's settings file of 2026-10-20 (with
  `"lock_rest": 0`) and the one home of the defaults; every release carries it.
* `tools/build_assets.py` makes the `syncrain` preset from it (`--themes-only` without the fonts);
  the app's `channel`, `fps`, `pause_under` and `lock_rest` defaults equal it; the page untouched
  saves it to the byte. Tests hold all three. So the default changed with it: glow 1 (was 0.5), the
  symbols without the Latin and Arabic sets, the words `AI AGI sSs AGENT LINUX WAKEUP`, and
  `pause_under` `never` (was `maximized`; the NixOS module's `pauseUnder` is now null, the file's).
* `./install.sh` reads `config.json` beside it by default; where there is none it writes one with
  the defaults (`syncrain --write-config`). `--config FILE` takes another, `--config none` none
  (and keeps the service's options from before, as a plain install did). The page says so under
  Save config.json.
* A preset given without `--config` (`./install.sh --preset matrix`) draws that preset: the kept
  settings file is set aside as `config.json.before`, since config.json's values would otherwise
  cover it. A kept file replaced is backed up as before, and an older backup of one's own is kept
  dated rather than overwritten.
* A git checkout with a config.json of its own from before (the old way: saved into the folder,
  then `--config config.json`) stops `git pull` at this build: move it away first, pull, then put
  it in place of the new one.
* A page draft from before this build that says `pause_under` `maximized` (the default then) is
  read as no choice: the default now is config.json's.
* `tests/fixtures/operator_config.json` (build 35's file) is gone: config.json replaces it.

## The review of this build

Two agents that did not write it read it. The first confirmed the rest was the only cause of the
10 fps and found the crossfade gone everywhere. The second found the C, Qt and QML sound, and: a
preset given to the installer drew config.json's look under its name (now the file is set aside
for it), a second upgrade could lose a backup of one's own settings (now kept dated), a temporary
file left where the folder cannot be written, old page drafts carrying `maximized`, and
`--write-config` reading the kept file first; all fixed above. Not changed: a `lock_rest` under a
millisecond rounds to none on the lock screen.

## What the operator does

* Unpack, then `./install.sh` (it installs the config.json in the folder: yours, as sent).
* To change the settings: the page, Save config.json into the folder, `./install.sh` again.
* The lock screen picks the change up at its next lock.

## Verification

574 passed in 1557.52s (0:25:57)
