# The package's name and both services, evaluated from this tree against local checkouts of
# nixpkgs and home-manager (no flake inputs fetched). Used by tests/nix/test_the_nix_side.py.
{ src, nixpkgs, homeManager, channel }:
let
  pkgs = import nixpkgs { system = "x86_64-linux"; };
  self = { packages.x86_64-linux.syncrain = pkgs.callPackage (src + "/nix/package.nix") { }; };
  nixos = import (nixpkgs + "/nixos/lib/eval-config.nix") {
    modules = [
      (import (src + "/nix/nixos-module.nix") self)
      {
        nixpkgs.hostPlatform = "x86_64-linux";
        boot.isContainer = true;
        system.stateVersion = "25.11";
        services.syncrain = { enable = true; inherit channel; rainbow = "all"; spin = 240; drift = 0.05;
                              pauseUnder = "fullscreen"; speed = 0.5; glow = 0.0; snow = false;
                              hieroglyphs = 0.3; };
      }
    ];
  };
  hm = import (homeManager + "/modules") {
    inherit pkgs;
    configuration = {
      imports = [ (import (src + "/nix/hm-module.nix") self) ];
      home.username = "me";
      home.homeDirectory = "/home/me";
      home.stateVersion = "25.11";
      services.syncrain = { enable = true; inherit channel; theme = "matrix"; };
    };
  };
  nixosService = nixos.config.systemd.user.services.syncrain.serviceConfig;
  hmService = hm.config.systemd.user.services.syncrain.Service;
in
{
  version = self.packages.x86_64-linux.syncrain.version;
  web = (pkgs.callPackage (src + "/nix/web.nix") { }).name;
  nixos = { exec = nixosService.ExecStart; prevent = nixosService.RestartPreventExitStatus; };
  hm = { exec = hmService.ExecStart; prevent = hmService.RestartPreventExitStatus; };
}
