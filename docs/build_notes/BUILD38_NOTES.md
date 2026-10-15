# Build 38: the NixOS template keeps the machine's own configuration, and the tests fail rather than hang

**Type: fix; the picture does not change** (stream `1ad0a2dd`). Made on 2026-10-15, the fifth of the
builds that fix what the review of build 33 found. This one takes Nix and the test harness: items
2, 12, 16 to 18, 20 to 22 and 47 (19 goes with the builds whose fixes its new cases test).

## The NixOS template (2)

* It no longer replaces the machine's `configuration.nix`: the README copies `/etc/nixos` whole as
  `machine/` (with every file its configuration imports), which the template's flake imports, and the template's own `configuration.nix` holds
  syncrain's lines alone (the user offered first on the login screen, the settings file, flakes on,
  git for the flake, SDDM, LightDM and GDM off). The boot loader, the users, the keyboard, an encrypted swap, a graphics driver and the
  release first installed are the machine's, as they were. Before, they were dropped or forced (a
  US keyboard, systemd-boot, release 25.11, a user `alice` with a known password).
* The nix lane evaluates the template over a stand-in for what NixOS's graphical installer writes
  (GRUB, a German keyboard, a swap in a file of its own, SDDM and LightDM, a user, release 24.11):
  all of it stays, the other login screens go.
* The rain's login screen refuses any other beside it (LightDM, GDM, ly, lemurs, COSMIC's, as it did
  SDDM and Plasma Login): two would share one terminal.
* What `nix flake init` prints first says the same steps as the README (it still said to copy the
  hardware file alone). The README says a plain `nixos-rebuild switch` builds `/etc/nixos` again,
  and that an import in angle brackets becomes a flake input.

## Nix

* `flake.lock` pins nixpkgs (55bfb4d7437b, the revision the nix lane tests), so `nix run
  github:Atyzze/syncrain` builds against what was tested, until the lock is updated on purpose (12).
  The nix lane checks the revision and the hash.
* The lock screen's derivation filtered its source by the absolute path: a checkout kept under any
  folder named `data` built from nothing (47).

## The tests

* An assertion whose message read the output of a process still running waited for that process
  for good: the lane hung instead of failing. The process is stopped first (16), and each lane has
  a time limit (an hour for all of them, half an hour for one).
* A stopped test run interrupts pytest first, so its teardowns stop Xvfb, Sway and KWin, and only
  then ends the rest (17). Started from a shell's `&`, as the release is, pytest would have
  inherited SIGINT ignored: the lane gets it back, and a SIGTERM interrupts it the same way. The lock screen's real-PAM test no longer writes `/etc/pam.d/kde`: its
  PAM service lives in a copy of `/etc/pam.d` that only its KWin sees (a mount namespace), so a
  stopped run leaves nothing that unlocks with "right". One an earlier build's stopped run left is
  taken away.
* The one-flavour browser test compared nixos with its own values; it now compares the page with the
  desktop over the syncrain preset (18).
* The native and GTK hosts' frames are compared once the picture stands, not after a fixed 2 s
  (20).
* Every test that needs something of the machine says so with `need()`, so `--require-all` fails
  rather than skips it: ffmpeg, an older Python, greetd's own text login (21).
* The page's symbol sets (`checkGlyphs`, `setShares`, taken from `index.html` as they are) run in
  Node on the same sets as Python's: what one takes the other takes, said the same way, with the
  same shares (22). It found one wording, now the same, and the page now says any value as
  Python's repr does (`True`, `None`, escapes).

## The review of this build

An agent that did not write it read it: nothing that can break a machine on switch; two major
findings (SIGINT ignored under the release's `&`; the welcome text of `nix flake init`) and the
display managers and imports the template did not yet keep in mind, all fixed above.

## What the operator does

* On NixOS with the template: `cp -r /etc/nixos machine` in the flake's folder, take the new
  template's `configuration.nix` and `flake.nix`, `git add .`, switch. Elsewhere: nothing.

## Verification

536 passed in 1180.64s (0:19:40)
