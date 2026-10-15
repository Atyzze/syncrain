# syncrain backdrop on your machine: Plasma 6, the rain as wallpaper, login screen and lock screen.
# Everything else stays as your machine has it, in machine/ (your /etc/nixos, copied): the boot
# loader, your users, the keyboard, the release you installed. Change what is marked.
{ lib, ... }:
{
  services.syncrain = {
    loginScreen.user = "";                       # CHANGE: your user name, offered first on the login screen
    # the look: open index.html from syncrain, press Settings, Save config.json next to this file
    # settings = ./config.json;
    # or options one by one (nix/options.nix in syncrain names them all):
    # theme = "nixos"; channel = "public"; snow = true;
  };

  # syncrain's login screen takes the place of the one the installer turned on (SDDM for Plasma,
  # LightDM or GDM for the others): two would share one terminal
  services.displayManager.sddm.enable = lib.mkForce false;
  services.xserver.displayManager.lightdm.enable = lib.mkForce false;
  services.displayManager.gdm.enable = lib.mkForce false;

  nix.settings.experimental-features = [ "nix-command" "flakes" ];
  # a flake sees only what git knows: `git add` needs git on the machine
  programs.git.enable = true;
}
