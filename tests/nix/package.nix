# The package itself, built from this tree against a local nixpkgs checkout.
{ src, nixpkgs }:
(import nixpkgs { system = "x86_64-linux"; }).callPackage (src + "/nix/package.nix") { }
