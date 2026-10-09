{
  lib,
  python3Packages,
  wrapGAppsHook4,
  gobject-introspection,
  gtk4,
  gtk4-layer-shell,
  pkg-config,
  wayland,
  wayland-scanner,
  dbus,
  libglvnd,
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
    pkg-config
    wayland-scanner
  ];

  buildInputs = [
    gtk4
    gtk4-layer-shell
    wayland
    dbus
  ];

  dependencies = with python3Packages; [
    pygobject3
    pillow
  ];

  # The native wallpaper (syncrain/native/): on Wayland it draws with neither Python nor GTK in
  # memory. It opens EGL when it starts; libglvnd's finds the system's driver (/run/opengl-driver).
  postBuild = ''
    SYNCRAIN_LIBEGL=${lib.getLib libglvnd}/lib/libEGL.so.1 sh syncrain/native/build.sh native/syncrain-wallpaper
  '';
  postInstall = ''
    install -Dm755 native/syncrain-wallpaper $out/libexec/syncrain/syncrain-wallpaper
  '';

  # one wrapper: GTK/GI paths from wrapGAppsHook4, gtk4-layer-shell loaded before libwayland-client,
  # and where the native wallpaper is
  dontWrapGApps = true;
  preFixup = ''
    makeWrapperArgs+=(
      "''${gappsWrapperArgs[@]}"
      --prefix LD_PRELOAD : ${gtk4-layer-shell}/lib/libgtk4-layer-shell.so
      --set-default SYNCRAIN_WALLPAPER $out/libexec/syncrain/syncrain-wallpaper
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
