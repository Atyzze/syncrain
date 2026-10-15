# The flake template's system (nix/template/configuration.nix with syncrain.nixosModules.backdrop),
# evaluated from this tree against the local nixpkgs checkout, with a stand-in for the machine's
# hardware-configuration.nix. Used by tests/nix/test_the_nix_side.py.
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
      { fileSystems."/" = { device = "/dev/disk/by-label/nixos"; fsType = "ext4"; };
        fileSystems."/boot" = { device = "/dev/disk/by-label/boot"; fsType = "vfat"; }; }
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
}
