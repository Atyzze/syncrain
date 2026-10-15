self:
{ config, lib, pkgs, ... }:
let
  cfg = config.services.syncrain;
  args = import ./args.nix { inherit lib cfg; };
  # systemd splits ExecStart like a shell, but reads backslashes as escapes even inside single
  # quotes, expands %-specifiers before splitting and $VARIABLES after: double all three, then quote
  systemdArgs = lib.concatMapStringsSep " "
    (a: lib.escapeShellArg (lib.replaceStrings [ "\\" "%" "$" ] [ "\\\\" "%%" "$$" ] a));
  exec = systemdArgs args;

  # The login screen's folder, as install.sh --login-screen makes /usr/local/lib/syncrain: the app,
  # its build and login.json (who logs in by default, which session, the rain's options).
  login = cfg.loginScreen;
  # the greeter names a session by its file in wayland-sessions; NixOS by the name without .desktop
  loginJson = pkgs.writeText "syncrain-login.json"
    (builtins.toJSON { user = login.user; session = "${login.session}.desktop"; rain = args; });
  sitePackages = cfg.package.sitePackages or pkgs.python3.sitePackages;
  loginLib = pkgs.runCommand "syncrain-login-${cfg.package.version}" { } ''
    mkdir -p $out
    cp -r ${cfg.package}/${sitePackages}/syncrain $out/syncrain
    printf '%s\n' ${lib.escapeShellArg cfg.package.version} > $out/BUILD_NUMBER
    cp ${loginJson} $out/login.json
  '';
  kwin = pkgs.kdePackages.kwin;
  # greetd splits its command like a shell: `env` sets what login.sh needs, from the store first
  # (kwin_wayland from Plasma's wrapper, which holds the capability it asks for; systemctl for the
  # box's power buttons), then the system's
  loginCommand = lib.escapeShellArgs [
    "${pkgs.coreutils}/bin/env"
    ("PATH=/run/wrappers/bin:${lib.makeBinPath [ kwin pkgs.dbus pkgs.util-linux pkgs.coreutils pkgs.gnugrep
                                                 config.systemd.package ]}:/run/current-system/sw/bin")
    "SYNCRAIN_PYTHON=${cfg.package}/libexec/syncrain/python3"
    "SYNCRAIN_LOGIN_TEXT=${config.services.greetd.package}/bin/agreety"
    "XDG_DATA_DIRS=${config.services.displayManager.sessionData.desktops}/share:/run/current-system/sw/share"
    "${loginLib}/syncrain/login/login.sh"
  ];

  lockScreen = pkgs.callPackage ./lockscreen.nix { };
  lockScene = "%h/.local/state/syncrain/lock-screen.scene";
in
{
  options.services.syncrain = import ./options.nix self { inherit lib pkgs; } // {
    loginScreen = {
      enable = lib.mkEnableOption ''
        the rain as the login screen: greetd runs KWin with the rain and syncrain's login box on
        every screen, then the session picked there (greetd's text login if that fails). Takes the
        place of SDDM or Plasma Login, which must be off'';
      user = lib.mkOption {
        type = lib.types.str;
        default = "";
        example = "alice";
        description = "Who the login box offers first (empty: the name is typed; the last login is remembered).";
      };
      session = lib.mkOption {
        type = lib.types.str;
        default = if config.services.displayManager.defaultSession != null
                  then config.services.displayManager.defaultSession else "plasma";
        defaultText = lib.literalExpression ''config.services.displayManager.defaultSession, else "plasma"'';
        example = "hyprland";
        description = "The session offered first, by name as services.displayManager.defaultSession takes it (the box can pick another).";
      };
      folder = lib.mkOption {
        type = lib.types.package;
        internal = true;
        readOnly = true;
        default = loginLib;
        description = "The login screen's folder (login.sh, the app, login.json), for tests/nix/.";
      };
    };
    lockScreen.enable = lib.mkEnableOption ''
      the rain as KDE Plasma 6's lock screen: Plasma's own locker shows syncrain's screen, the rain
      behind syncrain's box on every screen; needs services.desktopManager.plasma6 and the wallpaper
      (services.syncrain.enable), whose every start writes the lock screen's scene'';
  };

  config = lib.mkMerge [
    (lib.mkIf cfg.enable {
      environment.systemPackages = [ cfg.package ];

      # frames are a function of the clock, so keep it synchronised (the NixOS default, made explicit)
      services.timesyncd.enable = lib.mkDefault true;

      # started for every graphical login; the compositor must reach graphical-session.target
      # (Plasma and GNOME do; for Hyprland/Sway use UWSM or `systemctl --user start graphical-session.target`)
      systemd.user.services.syncrain = {
        description = "syncrain live wallpaper";
        partOf = [ "graphical-session.target" ];
        after = [ "graphical-session.target" ];
        wantedBy = [ "graphical-session.target" ];
        # a compositor or GPU that comes back after minutes still gets its wallpaper (the restarts slow
        # down to one in two minutes); a failure no restart mends ends after 30 tries in ten minutes
        unitConfig = { StartLimitIntervalSec = 600; StartLimitBurst = 30; };
        serviceConfig = {
          # the lock screen draws the scene written here, with these options; "-": never in the way
          ExecStartPre = lib.mkIf cfg.lockScreen.enable
            "-${lib.getExe cfg.package} --write-scene ${lockScene} ${exec}";
          ExecStart = "${lib.getExe cfg.package} ${exec}";
          Restart = "on-failure";
          RestartSec = 3;
          RestartSteps = 10;
          RestartMaxDelaySec = 120;
          # statuses a restart cannot change: 69 no OpenGL here, 2 no wallpaper layer (GNOME) or an
          # option it cannot use, 70 a native wallpaper from another build, 78 a picture or font it
          # cannot use (`syncrain --diagnose`)
          RestartPreventExitStatus = "2 69 70 78";
        };
      };
    })

    (lib.mkIf login.enable {
      assertions = [
        { assertion = !config.services.displayManager.sddm.enable;
          message = "services.syncrain.loginScreen takes the place of SDDM: set services.displayManager.sddm.enable = false"; }
      ] ++ map (dm: {
        # two greeters would take one terminal (and display-manager.service) between them
        assertion = !(lib.attrByPath (dm ++ [ "enable" ]) false config);
        message = "services.syncrain.loginScreen takes the place of every other login screen: set ${lib.concatStringsSep "." dm}.enable = false";
      }) [
        [ "services" "displayManager" "plasma-login-manager" ]
        [ "services" "displayManager" "gdm" ]
        [ "services" "xserver" "displayManager" "lightdm" ]
        [ "services" "displayManager" "ly" ]
        [ "services" "displayManager" "lemurs" ]
        [ "services" "displayManager" "cosmic-greeter" ]
      ] ++ [
        { assertion = !config.services.displayManager.autoLogin.enable;
          message = "services.syncrain.loginScreen has no automatic login: set services.displayManager.autoLogin.enable = false, or leave the login screen off"; }
        { assertion = lib.elem login.session config.services.displayManager.sessionData.sessionNames;
          message = "services.syncrain.loginScreen.session = \"${login.session}\" is no session of this system (${lib.concatStringsSep ", " config.services.displayManager.sessionData.sessionNames})"; }
      ];
      services.greetd = {
        enable = true;
        settings.default_session = { command = loginCommand; user = "greeter"; };
      };
      # the login screen's own folder: KWin's and the box's settings start afresh there at each boot;
      # the greeter's alone (it keeps the last login's name)
      systemd.tmpfiles.rules = [ "d /var/lib/syncrain-login 0700 greeter greeter -" ];
    })

    (lib.mkIf cfg.lockScreen.enable {
      assertions = [
        { assertion = cfg.enable;
          message = "services.syncrain.lockScreen draws the scene the wallpaper writes: set services.syncrain.enable = true"; }
      ];
      # the shell package (share/plasma/shells) and the QML module the locker loads; the shell package
      # is named to KWin's unit alone, so Plasma's shell keeps its own package and layout. A
      # plasmashellrc that names a ShellPackage still wins (docs/OPERATIONS.md)
      environment.systemPackages = [ lockScreen ];
      # written as the unit's text: systemd.user.services would add a PATH, LOCALE_ARCHIVE and TZDIR
      # of its own to KWin's environment
      systemd.user.units."plasma-kwin_wayland.service" = {
        overrideStrategy = "asDropin";
        text = ''
          [Service]
          Environment="PLASMA_DEFAULT_SHELL=org.syncrain.lockscreen"
          Environment="QML_IMPORT_PATH=${lockScreen}/lib/qt-6/qml"
          Environment="SYNCRAIN_LOCK_SCENE=${lockScene}"
        '';
      };
    })
  ];
}
