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
        # statuses a restart cannot change: 69 no OpenGL here, 2 no wallpaper layer (GNOME) or an
        # unknown option, 70 a native wallpaper from another build (`syncrain --diagnose`)
        RestartPreventExitStatus = "2 69 70";
      };
      Install.WantedBy = [ "graphical-session.target" ];
    };
  };
}
