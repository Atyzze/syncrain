self:
{ config, lib, pkgs, ... }:
let
  cfg = config.services.syncrain;
  args = import ./args.nix { inherit lib cfg; };
  # systemd splits ExecStart like a shell, but reads backslashes as escapes even inside single
  # quotes, expands %-specifiers before splitting and $VARIABLES after: double all three, then quote
  exec = lib.concatMapStringsSep " "
    (a: lib.escapeShellArg (lib.replaceStrings [ "\\" "%" "$" ] [ "\\\\" "%%" "$$" ] a)) args;
in
{
  options.services.syncrain = import ./options.nix self { inherit lib pkgs; };

  config = lib.mkIf cfg.enable {
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
      serviceConfig = {
        ExecStart = "${lib.getExe cfg.package} ${exec}";
        Restart = "on-failure";
        RestartSec = 3;
        # statuses a restart cannot change: 69 no OpenGL here, 2 no wallpaper layer (GNOME) or an
        # option it cannot use, 70 a native wallpaper from another build, 78 a picture or font it
        # cannot use (`syncrain --diagnose`)
        RestartPreventExitStatus = "2 69 70 78";
      };
    };
  };
}
