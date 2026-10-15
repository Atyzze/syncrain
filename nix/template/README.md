# syncrain backdrop on NixOS

A NixOS desktop where the rain is everything behind you: the wallpaper, the login screen and the
lock screen. KDE Plasma 6 on Wayland; boot stays plain text.

On a machine with NixOS installed:

```sh
mkdir ~/backdrop && cd ~/backdrop
nix --extra-experimental-features 'nix-command flakes' flake init -t github:Atyzze/syncrain
cp /etc/nixos/hardware-configuration.nix .
$EDITOR configuration.nix        # your boot loader, name, user (the lines marked CHANGE)
git init && git add .            # a flake sees only what git knows
sudo nixos-rebuild switch --flake .#backdrop
```

Reboot, and the login screen is the rain. Your look: open `index.html` from syncrain, press
Settings, Save config.json into this folder, set `settings = ./config.json;` and switch again.

What `syncrain.nixosModules.backdrop` turns on is in `nix/backdrop.nix` of syncrain; every option of
the rain in `nix/options.nix` and `docs/OPERATIONS.md`.
