{
  description = "syncrain: a never-repeating, clock-synchronised code-rain live wallpaper";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      packages = forAllSystems (pkgs: rec {
        syncrain = pkgs.callPackage ./nix/package.nix { };
        syncrain-web = pkgs.callPackage ./nix/web.nix { };
        default = syncrain;
      });

      apps = forAllSystems (pkgs: {
        default = {
          type = "app";
          program = "${self.packages.${pkgs.stdenv.hostPlatform.system}.syncrain}/bin/syncrain";
        };
      });

      overlays.default = final: _prev: {
        syncrain = final.callPackage ./nix/package.nix { };
        syncrain-web = final.callPackage ./nix/web.nix { };
      };

      nixosModules.default = import ./nix/nixos-module.nix self;
      homeManagerModules.default = import ./nix/hm-module.nix self;

      # `nix flake check` evaluates a NixOS system with the service enabled
      checks = forAllSystems (pkgs:
        let
          sys = nixpkgs.lib.nixosSystem {
            modules = [
              self.nixosModules.default
              {
                nixpkgs.hostPlatform = pkgs.stdenv.hostPlatform.system;
                boot.isContainer = true;
                system.stateVersion = "25.11";
                services.syncrain = { enable = true; theme = "nixos"; channel = "public"; };
              }
            ];
          };
        in
        {
          module-eval = pkgs.writeText "syncrain-module-eval"
            sys.config.systemd.user.services.syncrain.serviceConfig.ExecStart;
        });
    };
}
