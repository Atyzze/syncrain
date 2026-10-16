# What tests/lockscreen/ runs: syncrain's lock screen built from this tree (nix/lockscreen.nix), and
# one tree of Plasma 6's lock screen around it (kscreenlocker_greet, Qt's Wayland plugin and QML
# modules, Plasma's shell package to fall back to), against a local nixpkgs checkout.
{ src, nixpkgs }:
let
  pkgs = import nixpkgs { system = "x86_64-linux"; };
  kde = pkgs.kdePackages;
in
{
  lockscreen = pkgs.callPackage (src + "/nix/lockscreen.nix") { };
  # the native wallpaper from the same nixpkgs: the same Mesa as the lock screen's Qt, so the two
  # frames can be compared to the pixel (two Mesa versions' llvmpipe differ by a percent or two)
  wallpaper = pkgs.callPackage (src + "/nix/package.nix") { };
  qtdeclarative = pkgs.qt6.qtdeclarative;
  libei = pkgs.libei;
  plasma = pkgs.symlinkJoin {
    name = "syncrain-test-plasma";
    paths = [
      kde.kscreenlocker kde.qtbase kde.qtdeclarative kde.qtwayland kde.qtsvg kde.layer-shell-qt
      kde.libplasma kde.kirigami.unwrapped kde.plasma-workspace kde.plasma-desktop kde.ksvg
      kde.kdeclarative kde.kitemmodels
    ];
  };
}
