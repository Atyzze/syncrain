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
    home.packages = [ cfg.package ];
    systemd.user.services.syncrain = {
      Unit = {
        Description = "syncrain live wallpaper";
        PartOf = [ "graphical-session.target" ];
        After = [ "graphical-session.target" ];
      };
      Service = {
        ExecStart = "${lib.getExe cfg.package} ${exec}";
        Restart = "on-failure";
        RestartSec = 3;
        # exit status 69 means no OpenGL here; restarting would only cover the desktop again (`syncrain --diagnose`)
        RestartPreventExitStatus = 69;
      };
      Install.WantedBy = [ "graphical-session.target" ];
    };
  };
}
