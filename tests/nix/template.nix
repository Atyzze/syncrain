# The flake template's system (nix/template/configuration.nix with syncrain.nixosModules.backdrop),
# evaluated from this tree against the local nixpkgs checkout, with stand-ins for the machine's
# hardware-configuration.nix and its own configuration.nix (machine/), as NixOS's graphical installer
# writes it: Plasma with SDDM (and LightDM, as another desktop's installer would have), a German
# keyboard, GRUB, a swap of its own, a user, an older release.
# Used by tests/nix/test_the_nix_side.py.
{ src, nixpkgs }:
let
  pkgs = import nixpkgs { system = "x86_64-linux"; };
  self = { packages.x86_64-linux.syncrain = pkgs.callPackage (src + "/nix/package.nix") { }; };
  # as flake.nix makes them: keyed, so importing both gives the module once
  default = { key = "syncrain"; imports = [ (import (src + "/nix/nixos-module.nix") self) ]; };
  backdrop = { key = "syncrain-backdrop"; imports = [ default (src + "/nix/backdrop.nix") ]; };
  sys = import (nixpkgs + "/nixos/lib/eval-config.nix") {
    system = "x86_64-linux";
    modules = [
      backdrop
      default
      # machine/configuration.nix, with the files it imports (its hardware file, one of its own)
      { imports = [
          { fileSystems."/" = { device = "/dev/disk/by-label/nixos"; fsType = "ext4"; };
            fileSystems."/boot" = { device = "/dev/disk/by-label/boot"; fsType = "vfat"; }; }
          { swapDevices = [ { device = "/dev/disk/by-label/swap"; } ]; }
        ];
        boot.loader.grub = { enable = true; device = "/dev/sda"; };
        services.xserver.enable = true;
        services.xserver.displayManager.lightdm.enable = true;
        networking.hostName = "backdrop";
        services.xserver.xkb.layout = "de";
        console.keyMap = "de";
        services.desktopManager.plasma6.enable = true;
        services.displayManager.sddm.enable = true;
        users.users.alice = { isNormalUser = true; extraGroups = [ "wheel" ]; };
        system.stateVersion = "24.11"; }
      (src + "/nix/template/configuration.nix")
    ];
  };
  c = sys.config;
in
{
  toplevel = c.system.build.toplevel.drvPath;
  failed = map (a: a.message) (builtins.filter (a: !a.assertion) c.assertions);
  plasma = c.services.desktopManager.plasma6.enable;
  sddm = c.services.displayManager.sddm.enable;
  greetd = c.services.greetd.enable;
  login = c.services.syncrain.loginScreen.enable;
  loginUser = c.services.syncrain.loginScreen.user;
  lock = c.services.syncrain.lockScreen.enable;
  plymouth = c.boot.plymouth.enable;
  kwinDropin = c.systemd.user.units."plasma-kwin_wayland.service".text;
  keyboard = c.services.xserver.xkb.layout;
  grub = c.boot.loader.grub.enable;
  systemdBoot = c.boot.loader.systemd-boot.enable;
  stateVersion = c.system.stateVersion;
  alice = c.users.users.alice.isNormalUser;
  swap = c.swapDevices != [ ];
  lightdm = c.services.xserver.displayManager.lightdm.enable;
  git = c.programs.git.enable;
}
