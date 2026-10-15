# The NixOS module's login screen folder (login.sh, the app, login.json), built from this tree, and
# the KWin it would run. Used by tests/nix/test_the_nix_side.py to run it in a headless KWin.
{ src, nixpkgs }:
let
  pkgs = import nixpkgs { system = "x86_64-linux"; };
  self = { packages.x86_64-linux.syncrain = pkgs.callPackage (src + "/nix/package.nix") { }; };
  sys = import (nixpkgs + "/nixos/lib/eval-config.nix") {
    modules = [
      (import (src + "/nix/nixos-module.nix") self)
      {
        nixpkgs.hostPlatform = "x86_64-linux";
        boot.isContainer = true;
        system.stateVersion = "25.11";
        services.syncrain = { enable = true; theme = "matrix"; fps = 10;
                              loginScreen = { enable = true; user = "op"; }; };
      }
    ];
  };
in
pkgs.linkFarm "syncrain-nixos-login" [
  { name = "folder"; path = sys.config.services.syncrain.loginScreen.folder; }
  { name = "package"; path = self.packages.x86_64-linux.syncrain; }
]
