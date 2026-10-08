{
  lib,
  python3Packages,
  wrapGAppsHook4,
  gobject-introspection,
  gtk4,
  gtk4-layer-shell,
}:

python3Packages.buildPythonApplication {
  pname = "syncrain";
  # the build number is the only identity a tree has; tools/package_release.py writes it
  version = lib.fileContents ../BUILD_NUMBER;
  pyproject = true;

  src = lib.cleanSourceWith {
    src = ../.;
    filter = path: _type: !(lib.hasSuffix ".nix" path) && baseNameOf path != "flake.lock";
  };

  build-system = [ python3Packages.setuptools ];

  nativeBuildInputs = [
    wrapGAppsHook4
    gobject-introspection
  ];

  buildInputs = [
    gtk4
    gtk4-layer-shell
  ];

  dependencies = with python3Packages; [
    pygobject3
    pyopengl
    pillow
  ];

  # one wrapper: GTK/GI paths from wrapGAppsHook4, plus gtk4-layer-shell loaded before libwayland-client
  dontWrapGApps = true;
  preFixup = ''
    makeWrapperArgs+=(
      "''${gappsWrapperArgs[@]}"
      --prefix LD_PRELOAD : ${gtk4-layer-shell}/lib/libgtk4-layer-shell.so
    )
  '';

  pythonImportsCheck = [ "syncrain.engine" "syncrain.build" ];

  meta = {
    description = "Never-repeating, clock-synchronised code-rain live wallpaper (Wayland layer-shell and X11)";
    homepage = "https://github.com/Atyzze/syncrain";
    license = lib.licenses.mit;
    mainProgram = "syncrain";
    platforms = lib.platforms.linux;
  };
}
