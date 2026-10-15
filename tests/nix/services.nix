# The package's name and both services, evaluated from this tree against local checkouts of
# nixpkgs and home-manager (no flake inputs fetched). Used by tests/nix/test_the_nix_side.py.
{ src, nixpkgs, homeManager, channel }:
let
  pkgs = import nixpkgs { system = "x86_64-linux"; };
  self = { packages.x86_64-linux.syncrain = pkgs.callPackage (src + "/nix/package.nix") { }; };
  system = extra: import (nixpkgs + "/nixos/lib/eval-config.nix") {
    modules = [
      (import (src + "/nix/nixos-module.nix") self)
      {
        nixpkgs.hostPlatform = "x86_64-linux";
        boot.isContainer = true;
        system.stateVersion = "25.11";
      }
      extra
    ];
  };
  nixos = system {
    services.syncrain = { enable = true; inherit channel; rainbow = "all"; spin = 240; drift = 0.05;
                          pauseUnder = "fullscreen"; speed = 0.5; glow = 0.0; snow = false;
                          hieroglyphs = 0.3; flavours = 9; flavourLayout = "wave"; cycle = 30;
                          rainColors = [ "#202040" "#8040c0" "#e0c0ff" "#ffffff" ]; words = [ "HI" "THERE" ]; };
  };
  # the login and lock screens on a Plasma 6 system without SDDM
  screens = system {
    services.desktopManager.plasma6.enable = true;
    services.syncrain = { enable = true; theme = "matrix"; inherit channel;
                          loginScreen = { enable = true; user = "op"; };
                          lockScreen.enable = true; };
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
  sc = screens.config;
  failed = map (a: a.message) (builtins.filter (a: !a.assertion) sc.assertions);
in
{
  version = self.packages.x86_64-linux.syncrain.version;
  web = (pkgs.callPackage (src + "/nix/web.nix") { }).name;
  nixos = { exec = nixosService.ExecStart; prevent = nixosService.RestartPreventExitStatus;
            pre = nixosService.ExecStartPre or null; };
  hm = { exec = hmService.ExecStart; prevent = hmService.RestartPreventExitStatus; };
  screens = {
    inherit failed;
    greetd = sc.services.greetd.enable;
    command = sc.services.greetd.settings.default_session.command;
    greeter = sc.services.greetd.settings.default_session.user;
    tmpfiles = sc.systemd.tmpfiles.rules;
    kwinDropin = sc.systemd.user.units."plasma-kwin_wayland.service".text;
    pre = sc.systemd.user.services.syncrain.serviceConfig.ExecStartPre;
    exec = sc.systemd.user.services.syncrain.serviceConfig.ExecStart;
    shells = builtins.any (p: (p.pname or "") == "syncrain-lockscreen") sc.environment.systemPackages;
    # with SDDM on as well, the assertion says what to turn off
    session = sc.services.syncrain.loginScreen.session;
    badSession = map (a: a.message) (builtins.filter (a: !a.assertion) (system {
      services.desktopManager.plasma6.enable = true;
      services.syncrain = { enable = true; loginScreen = { enable = true; session = "nope"; }; };
    }).config.assertions);
    sddm = map (a: a.message) (builtins.filter (a: !a.assertion) (system {
      services.desktopManager.plasma6.enable = true;
      services.displayManager.sddm.enable = true;
      services.syncrain = { enable = true; loginScreen.enable = true; };
    }).config.assertions);
    noWallpaper = map (a: a.message) (builtins.filter (a: !a.assertion) (system {
      services.desktopManager.plasma6.enable = true;
      services.syncrain.lockScreen.enable = true;
    }).config.assertions);
  };
}
