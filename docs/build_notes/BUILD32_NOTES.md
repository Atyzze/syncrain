# Build 32: the login and lock screens on NixOS

**Type: feature; the picture does not change** (stream `822ea58a`). Made on 2026-10-15: the first
step to the NixOS image the operator plans ("a nix flavor that anyone can 1 click image apply to
their box"), NixOS being "the default/base".

## The NixOS module

* `services.syncrain.loginScreen = { enable = true; user = "alice"; }`: greetd runs syncrain's
  login screen as `greeter`: the rain and the box on every screen, then the session (`plasma` by
  default, `session` to change it), greetd's text login if the box fails. The module builds the
  login screen's folder (the app, its build, `login.json` with the wallpaper's options) and gives
  greetd one command with everything from the store: Plasma's KWin, the package's Python and
  agreety. SDDM and Plasma Login must be off; it says so if not.
* `services.syncrain.lockScreen.enable = true`: Plasma's locker shows syncrain's screen. A drop-in
  for KWin's unit alone names the shell package and the QML module (written as text, as NixOS
  would otherwise add a PATH of its own to KWin's environment); the wallpaper writes the lock
  screen's scene before every start. It needs the wallpaper on; it says so if not.
* The package has a Python for the login screen (`libexec/syncrain/python3`: the app, GTK,
  gtk4-layer-shell and the native wallpaper, from the package's own wrapper), and ships `login.sh`.

## Tests

* The nix lane builds the module's login folder and runs it as greetd would, in a headless KWin with
  two screens: the Nix-built rain draws natively, a box on each screen, a wrong and then the right
  password, Plasma asked for. A first run found the package's app on PYTHONPATH ahead of the
  folder, which hid `login.json` (the box had no user and never logged in): it comes last now.
* The module evaluated on a Plasma 6 system: greetd's command and user, the state folder, KWin's
  drop-in (no PATH), the scene written first with the wallpaper's options; the messages with SDDM on
  or the wallpaper off.

## From the review (an agent that did not write it)

* The app is found where the package put it, whatever Python the system has (stable NixOS with
  this flake's package would have failed to rebuild); the box's Power off and Restart find
  `systemctl`; `session` is a session's name as NixOS names them (`hyprland` was ignored), taken
  from `services.displayManager.defaultSession` and checked; automatic login is said to be
  missing; the login screen sees the system's share folder (icons); its folder is the greeter's
  alone; greetd's text login comes from greetd's own package.
* Said in `docs/OPERATIONS.md`: a `plasmashellrc` naming a shell package wins over the lock screen;
  follow the system's nixpkgs.

## Not yet

* No NixOS machine or VM has booted it (no KVM here). The still frame after a login is
  `install.sh`'s only; the home-manager module has the wallpaper only.

## What the operator does

* Nothing on CachyOS. On NixOS: the flake's module with the options above, Plasma 6, SDDM off.

## Verification

476 passed in 1117.25s (0:18:37)
