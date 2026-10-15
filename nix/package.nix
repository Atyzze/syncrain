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
  fontconfig,
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
  # where the native wallpaper is, and fc-list (a service's PATH has none; symbols not shipped come
  # from the machine's fonts through it)
  dontWrapGApps = true;
  preFixup = ''
    makeWrapperArgs+=(
      "''${gappsWrapperArgs[@]}"
      --prefix LD_PRELOAD : ${gtk4-layer-shell}/lib/libgtk4-layer-shell.so
      --set-default SYNCRAIN_WALLPAPER $out/libexec/syncrain/syncrain-wallpaper
      --suffix PATH : ${lib.makeBinPath [ fontconfig ]}
    )
  '';

  # The login screen runs `python -m syncrain.greeter` and the rain as `python -m syncrain`: a Python
  # with the app and its libraries, and this wrapper's environment (the NixOS module's loginScreen).
  # The app comes last on PYTHONPATH: login.sh names its own folder first, with login.json beside it.
  postFixup = ''
    makeWrapper ${python3Packages.python.withPackages (ps: with ps; [ pygobject3 pillow pycairo ])}/bin/python3 \
      $out/libexec/syncrain/python3 "''${makeWrapperArgs[@]}" \
      --suffix PYTHONPATH : $out/${python3Packages.python.sitePackages}
  '';

  # where the app is, for the NixOS module's login screen (the system's Python may be another version)
  passthru.sitePackages = python3Packages.python.sitePackages;

  pythonImportsCheck = [ "syncrain.engine" "syncrain.build" ];

  meta = {
    description = "Never-repeating, clock-synchronised code-rain live wallpaper (Wayland layer-shell and X11)";
    homepage = "https://github.com/Atyzze/syncrain";
    license = lib.licenses.mit;
    mainProgram = "syncrain";
    platforms = lib.platforms.linux;
  };
}
