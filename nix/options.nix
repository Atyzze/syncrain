# Options shared by the NixOS and home-manager modules.
self:
{ lib, pkgs, ... }:
let
  inherit (lib) mkEnableOption mkOption types;
in
{
  enable = mkEnableOption "syncrain, the clock-synchronised code-rain live wallpaper";

  package = mkOption {
    type = types.package;
    default = self.packages.${pkgs.stdenv.hostPlatform.system}.syncrain;
    defaultText = lib.literalExpression "syncrain.packages.\${system}.syncrain";
    description = "The syncrain package to run.";
  };

  theme = mkOption {
    type = types.enum [ "nixos" "matrix" ];
    default = "nixos";
    description = "Colour theme: `nixos` (ice blue, snow, NixOS logo) or `matrix` (green).";
  };

  channel = mkOption {
    type = types.str;
    default = "public";
    description = ''
      Stream name. Every machine on the same channel with a synchronised clock renders the
      exact same frame at the same moment; a different name gives a different, equally endless stream.
    '';
  };

  fps = mkOption {
    type = types.ints.between 1 240;
    default = 30;
    description = "Frame-rate cap.";
  };

  logo = mkOption {
    type = types.nullOr (types.enum [ "white" "colours" "none" ]);
    default = null;
    description = "NixOS logo variant (null: theme default, which is `white` for the nixos theme).";
  };

  background = mkOption {
    type = types.nullOr types.path;
    default = null;
    description = "Optional background image (darkened with bgGamma/bgGain) instead of the theme gradient.";
  };

  mask = mkOption {
    type = types.nullOr types.path;
    default = null;
    description = "Greyscale mask for `background`: white areas stay at full brightness and the rain passes behind them.";
  };

  rainbow = mkOption {
    type = types.nullOr (types.enum [ "logo" "all" "off" ]);
    default = null;
    description = ''
      Colour cycling against burn-in: `logo` (the logo cycles through the rainbow; the default),
      `all` (the rain cycles too) or `off` (theme colours). The logo keeps turning either way unless spin = 0.
    '';
  };

  spin = mkOption {
    type = types.nullOr types.ints.unsigned;
    default = null;
    description = "Seconds per logo revolution (null: 180; 0: still).";
  };

  drift = mkOption {
    type = types.nullOr (types.numbers.between 0.0 0.2);
    default = null;
    description = "Slow orbit of the logo, or pan of a background image, in screen heights (null: 0.03; 0: fixed).";
  };

  scale = mkOption {
    type = types.numbers.between 0.25 1.0;
    default = 1.0;
    description = "Render resolution scale; lower it on weak GPUs.";
  };

  pauseUnder = mkOption {
    type = types.enum [ "maximized" "fullscreen" "never" ];
    default = "maximized";
    description = ''
      On KDE Plasma, stop drawing a screen while a maximized or full-screen window covers it
      (`maximized`), only while a full-screen one does (`fullscreen`), or never. Other compositors
      stop asking a hidden wallpaper for frames by themselves.
    '';
  };

  layer = mkOption {
    type = types.nullOr (types.enum [ "background" "bottom" ]);
    default = null;
    description = "Wayland layer (null: `bottom` on KDE Plasma, `background` elsewhere).";
  };

  extraArgs = mkOption {
    type = types.listOf types.str;
    default = [ ];
    description = "Extra command-line arguments for syncrain.";
  };
}
