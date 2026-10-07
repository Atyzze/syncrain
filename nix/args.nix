# Command line for the configured options.
{ lib, cfg }:
let
  inherit (lib) optionals;
in
[ "--theme" cfg.theme "--channel" cfg.channel "--fps" (toString cfg.fps) "--scale" (toString cfg.scale) ]
++ optionals (cfg.logo != null) [ "--logo" cfg.logo ]
++ optionals (cfg.background != null) [ "--background" "${cfg.background}" ]
++ optionals (cfg.mask != null) [ "--mask" "${cfg.mask}" ]
++ optionals (cfg.layer != null) [ "--layer" cfg.layer ]
++ optionals (cfg.pauseUnder != "maximized") [ "--pause-under" cfg.pauseUnder ]
++ optionals (cfg.rainbow != null) [ "--rainbow" cfg.rainbow ]
++ optionals (cfg.spin != null) [ "--spin" (toString cfg.spin) ]
++ optionals (cfg.drift != null) [ "--drift" (toString cfg.drift) ]
++ cfg.extraArgs
