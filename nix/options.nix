# Options shared by the NixOS and home-manager modules.
self:
{ lib, pkgs, ... }:
let
  inherit (lib) mkEnableOption mkOption types;
  colour = types.strMatching "#[0-9a-fA-F]{6}";
in
{
  enable = mkEnableOption "syncrain, the clock-synchronised code-rain live wallpaper";

  package = mkOption {
    type = types.package;
    default = self.packages.${pkgs.stdenv.hostPlatform.system}.syncrain;
    defaultText = lib.literalExpression "syncrain.packages.\${system}.syncrain";
    description = "The syncrain package to run.";
  };

  settings = mkOption {
    type = types.nullOr types.path;
    default = null;
    description = ''
      A settings file the web page saved (`config.json`): every look and symbol set in it. The
      options below go over it.
    '';
  };

  theme = mkOption {
    type = types.nullOr (types.enum [ "syncrain" "nixos" "matrix" ]);
    default = null;
    description = ''
      The preset the look starts from: `syncrain` (white-tailed rain in 64 colours, a turning rainbow wave, the NixOS logo, snow),
      `nixos` (ice blue, snow, the NixOS logo) or `matrix` (green, no snow). Null: the settings file's, else syncrain.
    '';
  };

  rainColors = mkOption {
    type = types.nullOr (types.addCheck (types.listOf colour) (l: builtins.length l == 4));
    default = null;
    example = [ "#132a52" "#3d6ed2" "#8cc0ee" "#eef7ff" ];
    description = "The rain's gradient, dark to bright, then the leading symbol: four `#rrggbb` (null: the preset's).";
  };

  glowColor = mkOption {
    type = types.nullOr colour;
    default = null;
    description = "The glow round the rain, `#rrggbb` (null: the preset's).";
  };

  backgroundColors = mkOption {
    type = types.nullOr (types.addCheck (types.listOf colour) (l: builtins.length l == 3));
    default = null;
    description = "The background gradient: top, bottom and centre glow, three `#rrggbb` (null: the preset's).";
  };

  vignette = mkOption {
    type = types.nullOr (types.numbers.between 0.0 1.0);
    default = null;
    description = "How much darker the corners are (null: the preset's).";
  };

  flavours = mkOption {
    type = types.nullOr (types.ints.between 1 64);
    default = null;
    description = "Colours at once: each column of rain one of this many hues round the colour wheel (null: the preset's).";
  };

  flavourLayout = mkOption {
    type = types.nullOr (types.enum [ "random" "wave" ]);
    default = null;
    description = "How the flavours fall to the columns: `random` (by the channel) or `wave` (in order across the screen).";
  };

  cycle = mkOption {
    # 0 (off) or 10 s and more, as syncrain takes it: shorter would flash
    type = types.nullOr (types.addCheck types.ints.unsigned (n: n == 0 || n >= 10));
    default = null;
    description = "Seconds a turn of the rain's colour wheel, every flavour together (null: the preset's; 0: the colours stay).";
  };

  words = mkOption {
    # bytes, not characters, to Nix: room for 30 katakana (three bytes each); syncrain checks the rest
    type = types.nullOr (types.listOf (types.strMatching "[^,\t\n\r]{1,120}"));
    default = null;
    description = "The hidden words and sentences that fall now and then, up to 30 characters each, a space falling as a gap (null: the preset's; [ ]: none).";
  };

  channel = mkOption {
    type = types.nullOr types.str;
    default = null;
    description = ''
      Stream name. Every machine on the same channel with a synchronised clock renders the
      exact same frame at the same moment; a different name gives a different, equally endless stream
      (null: the settings file's, else `public`).
    '';
  };

  fps = mkOption {
    type = types.nullOr (types.ints.between 1 240);
    default = null;
    description = "Frame-rate cap (null: the settings file's, else 30).";
  };

  logo = mkOption {
    type = types.nullOr (types.either (types.enum [ "syncrain" "nixos" "white" "none" "nixos-colours" "colours" ]) types.path);
    default = null;
    description = "The logo: `syncrain`, `nixos`, `none` or a picture (null: the preset's). The older names `white`, `nixos-colours` and `colours` draw `nixos`.";
  };

  logoColor = mkOption {
    type = types.nullOr (types.either colour (types.enum [ "own" ]));
    default = null;
    description = "One colour over the logo's shape, `#rrggbb`, or `own` for its own colours (null: the preset's or the settings file's).";
  };

  logoSize = mkOption {
    type = types.nullOr (types.numbers.between 0.05 0.9);
    default = null;
    description = "The logo's height in screen heights (null: the preset's).";
  };

  logoCycle = mkOption {
    # 0 (off) or 10 s and more, as syncrain takes it: shorter would flash
    type = types.nullOr (types.addCheck types.ints.unsigned (n: n == 0 || n >= 10));
    default = null;
    description = "Seconds a turn of the logo's rainbow (null: the preset's; 0: the logo's own colours).";
  };

  background = mkOption {
    type = types.nullOr types.path;
    default = null;
    description = "Optional background image instead of the background gradient, darkened by bgGain (and --bg-gamma through extraArgs).";
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
      The earlier spelling of `logoCycle` and `cycle`: `logo` (as is), `all` (the rain cycles every
      600 s) or `off` (the logo's own colours). The logo keeps turning either way unless spin = 0.
    '';
  };

  spin = mkOption {
    # 0 (off) or 10 s and more, as syncrain takes it: shorter would flash
    type = types.nullOr (types.addCheck types.ints.unsigned (n: n == 0 || n >= 10));
    default = null;
    description = "Seconds per logo revolution (null: the preset's, 300 for syncrain, 180 for nixos and matrix; 0: still).";
  };

  drift = mkOption {
    type = types.nullOr (types.numbers.between 0.0 0.2);
    default = null;
    description = "Slow orbit of the logo, or pan of a background image, in screen heights (null: the preset's, 0 for syncrain, 0.03 for nixos and matrix; 0: fixed).";
  };

  speed = mkOption {
    type = types.nullOr (types.numbers.between 0.25 4.0);
    default = null;
    description = "How fast the symbols fall, times the preset's (null: where the preset puts it, 1).";
  };

  density = mkOption {
    type = types.nullOr (types.numbers.between 0.0 2.3);
    default = null;
    description = "How often a column starts a new stream, times the preset's (null: where the preset puts it: 1.15 for syncrain, 1 for nixos and matrix).";
  };

  glow = mkOption {
    type = types.nullOr (types.numbers.between 0.0 2.0);
    default = null;
    description = "The glow around the centre and the logo (null: where the preset puts it: 0.5 for syncrain, 1 for nixos and matrix; 0: none).";
  };

  bloom = mkOption {
    type = types.nullOr (types.numbers.between 0.0 2.0);
    default = null;
    description = "The glow around the falling symbols, times the preset's (null: 1; 0: none).";
  };

  bgGain = mkOption {
    type = types.nullOr (types.numbers.between 0.0 2.0);
    default = null;
    description = "Background brightness (null: the preset's for the gradient, 0.6 for syncrain and 1 for nixos and matrix; 0.42 for `background`; lower is darker).";
  };

  snow = mkOption {
    type = types.nullOr types.bool;
    default = null;
    description = "The falling snowflakes (null: the preset's, on for syncrain and nixos, off for matrix).";
  };

  hieroglyphs = mkOption {
    type = types.nullOr (types.numbers.between 0.0 1.0);
    default = null;
    description = "Share of the changing symbols that are Egyptian hieroglyphs (null: as the symbol sets say, 0.15 in the presets; 0: none).";
  };

  scale = mkOption {
    type = types.numbers.between 0.25 1.0;
    default = 1.0;
    description = "Render resolution scale; lower it on weak GPUs.";
  };

  pauseUnder = mkOption {
    type = types.nullOr (types.enum [ "maximized" "fullscreen" "never" ]);
    default = null;
    description = ''
      On KDE Plasma, stop drawing a screen while a maximized or full-screen window covers it
      (`maximized`), only while a full-screen one does (`fullscreen`), or never. Other compositors
      stop asking a hidden wallpaper for frames by themselves. null: the settings file's, else
      `never` (the default settings file's).
    '';
  };

  lockRest = mkOption {
    type = types.nullOr (types.numbers.between 0 86400);
    default = null;
    description = ''
      The lock screen draws 10 frames a second instead of 30 after this many seconds without a key
      or a moved pointer, and 30 again at the next one; 0: never. null: the settings file's, else 0.
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
