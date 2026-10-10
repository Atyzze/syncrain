# The Plasma wallpaper built from this tree, and what tests/plasma/ runs it with: Qt's qml tool
# and Kirigami for the settings page. Against a local nixpkgs checkout.
{ src, nixpkgs }:
let
  pkgs = import nixpkgs { system = "x86_64-linux"; };
in
{
  plugin = pkgs.callPackage (src + "/nix/plasma.nix") { };
  qtdeclarative = pkgs.qt6.qtdeclarative;
  kirigami = pkgs.kdePackages.kirigami.unwrapped or pkgs.kdePackages.kirigami;
}
