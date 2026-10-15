# syncrain backdrop on NixOS

A NixOS desktop where the rain is everything behind you: the wallpaper, the login screen and the
lock screen. KDE Plasma 6 on Wayland; boot stays plain text.

On a machine with NixOS installed:

```sh
mkdir ~/backdrop && cd ~/backdrop
nix --extra-experimental-features 'nix-command flakes' flake init -t github:Atyzze/syncrain
cp -r /etc/nixos machine         # your machine as it is: boot loader, users, keyboard, hardware
$EDITOR configuration.nix        # your user name (the line marked CHANGE)
nix-shell -p git --run 'git init && git add .'    # a flake sees only what git knows
sudo nixos-rebuild switch --flake .#backdrop
```

`machine/` is your machine's own configuration, unchanged, with every file it imports: syncrain's
lines are in `configuration.nix` alone, so nothing of yours (a second user, an encrypted swap, the
keyboard layout, a graphics driver) is lost. The one thing they decide over it: the login screen is
the rain, so SDDM, LightDM and GDM are off. Automatic login has to be off too (the switch says so
if it is on). The previous generation stays in the boot menu.

* An import written with angle brackets in your configuration (`<home-manager/nixos>`, a channel)
  does not work in a flake: add it as an input to `flake.nix` instead.
* From now on switch with `--flake .#backdrop` from this folder: a plain `nixos-rebuild switch`
  builds `/etc/nixos` again, without syncrain.
* For Plasma or a machine without a desktop. GNOME and Plasma 6 cannot be on together.

Reboot, and the login screen is the rain. Your look: open `index.html` from syncrain, press
Settings, Save config.json into this folder, set `settings = ./config.json;` and switch again.

What `syncrain.nixosModules.backdrop` turns on is in `nix/backdrop.nix` of syncrain; every option of
the rain in `nix/options.nix` and `docs/OPERATIONS.md`.
