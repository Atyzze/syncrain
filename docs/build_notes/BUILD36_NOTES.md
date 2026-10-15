# Build 36: the login screen changes only what it set, and reads greetd's config as greetd does

**Type: fix; the picture does not change** (stream `1ad0a2dd`). Made on 2026-10-15, the third of the
builds that fix what the review of build 33 found. This one takes the login screen's items: 4 to 7
and 31 to 38, and the greetd stand-in of the tests (23).

## The way back (4)

* `--login-screen-off` used to put back whole copies of greetd's config and PAM file, made at
  `--login-screen`: anything changed in between (a second factor, faillock) was lost. Now it takes
  out only the wallet lines it added (they are marked) and puts back only `[default_session]`'s
  command and user as they were written (from the config's copy, which is all the copy is still
  for). The PAM file's copy is no longer made, and an old one goes.
* greetd's greeter's own PAM file is greetd's file without the wallet lines, made again at each
  install, so a change to greetd's file reaches it (37).

## greetd's config, read as greetd reads it (6, 35)

* greetd 0.10 does not read TOML: it goes line by line, the last of a section named twice wins, and
  there are no values over several lines. `syncrain/greetdconf.py` now reads it that way: the
  `[default_session]` greetd uses is the one changed (two of them left greetd with no command and
  no login), a `'''` in a value is just characters, and each edit is read back as greetd would
  before it is written: the command and user as meant, every other section as it was. A config
  greetd itself cannot read is left alone, and said so.

## The text login always comes (5, 36)

* greetd's command reads `login.sh` with `sh` instead of running it, after `sh -n` has read it
  once: a policy that refuses to run or to read the file (SELinux, fapolicyd) now leaves greetd's
  text login; before, the failed exec ended the shell with no login at all.
* A box that died in the middle of a login left greetd holding that conversation, and the text
  login's first try was refused. `login.sh` drops it first. The test stand-in for greetd now holds
  one conversation for every connection and refuses a second, as greetd does (23), and a greetd
  that stops answering is tested: the box gives up after its timeout and drops the conversation.

## Debian and Ubuntu (7)

* `/etc/X11/default-display-manager` names greetd while the login screen is on and what it named
  before after `--login-screen-off`: greetd's package points what starts at boot at that file's
  choice on every upgrade, and Ubuntu's SDDM does not start unless it names SDDM. What it named is
  read before greetd's package is installed (its question can make it name greetd), recorded again
  whenever another display manager starts at boot, and put back also when the operator switched
  back by hand first (the recovery hint now says how); a choice made in it since stays theirs.

## Smaller

* Ctrl+Z no longer brings a refused password back into the box, and the eye turns off after a
  refusal (31).
* `/var/lib/syncrain-login` is greetd's user's alone (0700, as on NixOS): its log says who logged
  in, and when. `syncrain --diagnose` says how to read it (32).
* `--login-screen` run again leaves a splash or a wallpaper chosen since the first run alone; a
  desktop added since gets the still frame (33).
* The app copied for the login screen holds no links: a link is followed on the operator's side,
  so greetd's user never runs code the operator can still change (34).
* The login screen's cache (compiled shaders and QML) is kept while the build stays, and goes with
  a new one (38).

## The review of this build

* An agent that did not write it read it against greetd's own parser (built from its source) and
  ran the installer through the cases above. From it: `sh -n`; Debian's file read before the
  package, recorded again, put back after a switch by hand; the way back keeps a greeter chosen
  since, restores greetd's bare-word values, and refuses a config with no command (syncrain's stays,
  which runs greetd's text login); quotes and escapes exactly as greetd's enquote; lines split as
  greetd splits them; the greeter's PAM file written only once whole; the greetd stand-in keeps a
  session already started.
* An upgrade brings a login screen set up before this build up to it: Debian's file, the private
  state folder.

## What the operator does

* With the login screen on: `./install.sh` as usual. Nothing to do otherwise.

## Verification

517 passed in 1162.05s (0:19:22)
