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
++ optionals (cfg.speed != null) [ "--speed" (toString cfg.speed) ]
++ optionals (cfg.density != null) [ "--density" (toString cfg.density) ]
++ optionals (cfg.glow != null) [ "--glow" (toString cfg.glow) ]
++ optionals (cfg.bloom != null) [ "--bloom" (toString cfg.bloom) ]
++ optionals (cfg.bgGain != null) [ "--bg-gain" (toString cfg.bgGain) ]
++ optionals (!cfg.snow) [ "--snow" "off" ]
++ optionals (cfg.hieroglyphs != null) [ "--hieroglyphs" (toString cfg.hieroglyphs) ]
++ cfg.extraArgs
