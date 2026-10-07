{ lib, runCommand }:

# The self-contained web runner (same shaders and clock), for browsers and web-wallpaper hosts.
runCommand "syncrain-web-${lib.fileContents ../BUILD_NUMBER}"
  {
    meta = {
      description = "Web version of the syncrain clock-synchronised code-rain wallpaper";
      license = lib.licenses.mit;
    };
  }
  ''
    install -Dm644 ${../web/index.html} $out/share/syncrain/index.html
  ''
