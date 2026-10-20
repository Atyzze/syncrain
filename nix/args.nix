# Command line for the configured options.
{ lib, cfg }:
let
  inherit (lib) concatStringsSep optionals;
in
optionals (cfg.settings != null) [ "--config" "${cfg.settings}" ]
# what is not set is left to the settings file, else to the preset
++ optionals (cfg.theme != null) [ "--preset" cfg.theme ]
++ optionals (cfg.channel != null) [ "--channel" cfg.channel ]
++ optionals (cfg.fps != null) [ "--fps" (toString cfg.fps) ]
++ [ "--scale" (toString cfg.scale) ]
++ optionals (cfg.logo != null) [ "--logo" (if builtins.isPath cfg.logo then "${cfg.logo}" else cfg.logo) ]
++ optionals (cfg.logoColor != null) [ "--logo-color" cfg.logoColor ]
++ optionals (cfg.logoSize != null) [ "--logo-size" (toString cfg.logoSize) ]
++ optionals (cfg.logoCycle != null) [ "--logo-cycle" (toString cfg.logoCycle) ]
++ optionals (cfg.rainColors != null) [ "--rain-colors" (concatStringsSep "," cfg.rainColors) ]
++ optionals (cfg.glowColor != null) [ "--glow-color" cfg.glowColor ]
++ optionals (cfg.backgroundColors != null) [ "--background-colors" (concatStringsSep "," cfg.backgroundColors) ]
++ optionals (cfg.vignette != null) [ "--vignette" (toString cfg.vignette) ]
++ optionals (cfg.flavours != null) [ "--flavours" (toString cfg.flavours) ]
++ optionals (cfg.flavourLayout != null) [ "--flavour-layout" cfg.flavourLayout ]
++ optionals (cfg.cycle != null) [ "--cycle" (toString cfg.cycle) ]
++ optionals (cfg.words != null) [ "--words=${concatStringsSep "," cfg.words}" ]
++ optionals (cfg.background != null) [ "--background" "${cfg.background}" ]
++ optionals (cfg.mask != null) [ "--mask" "${cfg.mask}" ]
++ optionals (cfg.layer != null) [ "--layer" cfg.layer ]
++ optionals (cfg.pauseUnder != null) [ "--pause-under" cfg.pauseUnder ]
++ optionals (cfg.lockRest != null) [ "--lock-rest" (toString cfg.lockRest) ]
++ optionals (cfg.rainbow != null) [ "--rainbow" cfg.rainbow ]
++ optionals (cfg.spin != null) [ "--spin" (toString cfg.spin) ]
++ optionals (cfg.drift != null) [ "--drift" (toString cfg.drift) ]
++ optionals (cfg.speed != null) [ "--speed" (toString cfg.speed) ]
++ optionals (cfg.density != null) [ "--density" (toString cfg.density) ]
++ optionals (cfg.glow != null) [ "--glow" (toString cfg.glow) ]
++ optionals (cfg.bloom != null) [ "--bloom" (toString cfg.bloom) ]
++ optionals (cfg.bgGain != null) [ "--bg-gain" (toString cfg.bgGain) ]
++ optionals (cfg.snow != null) [ "--snow" (if cfg.snow then "on" else "off") ]
++ optionals (cfg.hieroglyphs != null) [ "--hieroglyphs" (toString cfg.hieroglyphs) ]
++ cfg.extraArgs
