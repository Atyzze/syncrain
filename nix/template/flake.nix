{
  description = "A NixOS desktop with syncrain backdrop: the rain as wallpaper, login screen and lock screen";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    syncrain = {
      url = "github:Atyzze/syncrain";
      inputs.nixpkgs.follows = "nixpkgs";       # the same graphics libraries as the system's driver
    };
  };

  outputs = { nixpkgs, syncrain, ... }: {
    # sudo nixos-rebuild switch --flake .#backdrop
    nixosConfigurations.backdrop = nixpkgs.lib.nixosSystem {
      modules = [
        syncrain.nixosModules.backdrop
        ./machine/configuration.nix             # your /etc/nixos, as it was (its hardware file with it)
        ./configuration.nix
      ];
    };
  };
}
