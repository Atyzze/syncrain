# Build 31: the installer for four families

**Type: feature; the picture does not change** (stream `822ea58a`). Made on 2026-10-15, as the
operator asked at 13:30: "make it work on debian based, and fedora based as well? so its not just
arch supported but the top 4 ... and then all the others can figure it out themselves from there,
leave the invitation open to .... copy/hand this repo to your ai-agent".

## install.sh

* It knows the family from os-release (`ID`, then `ID_LIKE`: CachyOS, Mint, Pop!_OS, Nobara and
  the rest fall in theirs), else from the package tool there is; `SYNCRAIN_FAMILY` overrides it.
* Each family's packages, asked of its own tool through sudo: pacman, apt-get, dnf, zypper (the
  table in `docs/OPERATIONS.md`, "Install"). `--yes` answers each tool's questions; a tool that
  cannot install says what to try first.
* gtk4-layer-shell is asked for on its own: Ubuntu 24.04 and openSUSE Leap 16.0 have none, and the
  install goes on with the native wallpaper.
* The login screen: greetd's user as the family's package names it (`greeter`, `_greetd`,
  `greetd`), its text login wherever it is (`/usr/sbin/agreety` on Debian), given to the login
  screen too. What started at boot is seen before greetd is installed (Debian's package makes
  itself what starts at boot where nothing did) and recorded once greetd is in.
* The lock screen's packages now include `make` and a C++ compiler: a minimal Arch has no `make`,
  Debian's and openSUSE's Qt bring no C++ compiler.
* Anything else: it names what to install by hand for `--no-deps`, and invites its user to hand
  the repository to their AI agent.

## Tried for real

* A root each of Debian 13, Fedora 44, openSUSE Tumbleweed and Arch: `./install.sh --yes` as a user
  with sudo installed the packages, built the native wallpaper and the launcher; under Xvfb the app
  drew the frame this machine draws (Debian to the pixel; the others within 4 of 255 with the bloom
  off, their newer Mesa's rounding); the lock screen's module built with the family's Qt;
  `--login-screen` over a stand-in SDDM made greetd run the rain as the family's greetd user, and
  `--login-screen-off` put SDDM back. How: `docs/agent/ENVIRONMENT.md`.
* Not booted: no one has yet logged in or locked a desktop on Debian, Fedora or openSUSE, and
  Fedora's SELinux is untried (`docs/ROADMAP.md`, "Open items").

## From the review (an agent that did not write it)

* Debian's gtk4-layer-shell typelib comes without its library: the installer now asks for both,
  and the GTK host, the login box and `--diagnose` take a typelib that cannot load as none (the
  box had died before showing, every boot ending in the text login). The installer's check loads
  the library.
* The record of what started at boot is written only once greetd is installed, so a refused or
  failed install leaves none behind.
* A text login on PATH counts only if it is root's, outside the home and plain; the system's comes
  first. An upgrade that cannot find greetd's user or text login leaves greetd's config as it is.
* A tool that fails after installing everything (zypper's 107) is no failure; image-based systems
  (rpm-ostree, transactional-update) are told how to add the packages; RHEL-likes are pointed at
  EPEL.
* Seen on Arch by installing build 30 with the login screen, then this build over it: greetd's
  config keeps `user = "greeter"`, the text login now named by its path.

## The README

* Install for four families, what was tried on each, and the invitation: hand this repository to
  your AI agent and let it adapt `install.sh` to your system.

## Tests

* `tests/unit/test_the_families.py`: the family of 13 systems' os-release and of each package tool;
  each tool asked for its packages with `--yes`; without gtk4-layer-shell the install goes on; a
  tool that cannot install says what to try, one that warns after installing goes on; a system of
  no known family is told what to install; the lock screen's packages; greetd's user per family,
  into its config end to end; which text login counts; what started at boot seen before Debian's
  greetd takes it, and no record when greetd cannot be installed.

## What the operator does

* Nothing on CachyOS: `./install.sh` from `syncrain_build_31/` works as before.
* To try another family: unpack it there and `./install.sh`.

## Verification

474 passed in 1189.05s (0:19:49)
