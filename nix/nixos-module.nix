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
        # exit status 69 means no OpenGL here; restarting would only cover the desktop again (`syncrain --diagnose`)
        RestartPreventExitStatus = 69;
      };
    };
  };
}
