# The Plasma wallpaper: the QML module org.syncrain (syncrain/plasma/) and the wallpaper package.
# On NixOS, put it in environment.systemPackages next to syncrain, then pick "syncrain" in
# Desktop and Wallpaper (and in Screen Locking > Appearance for the lock screen).
{
  lib,
  stdenv,
  cmake,
  pkg-config,
  qt6,
  dbus,
  syncrain ? null,
}:

stdenv.mkDerivation {
  pname = "syncrain-plasma";
  version = lib.fileContents ../BUILD_NUMBER;

  src = lib.cleanSourceWith {
    src = ../syncrain;
    filter = path: _type: !(lib.hasSuffix ".py" path) && !(lib.hasInfix "/data" path);
  };

  nativeBuildInputs = [ cmake pkg-config ];
  buildInputs = [ qt6.qtbase qt6.qtdeclarative dbus ];
  dontWrapQtApps = true;

  cmakeDir = "../plasma";
  cmakeFlags = lib.optional (syncrain != null) "-DSYNCRAIN_COMMAND=${syncrain}/bin/syncrain";

  installPhase = ''
    runHook preInstall
    install -Dm644 -t $out/lib/qt-6/qml/org/syncrain qml/org/syncrain/qmldir qml/org/syncrain/*.qmltypes
    install -Dm755 -t $out/lib/qt-6/qml/org/syncrain qml/org/syncrain/*.so
    mkdir -p $out/share/plasma/wallpapers
    cp -r ../plasma/package $out/share/plasma/wallpapers/org.syncrain.wallpaper
    runHook postInstall
  '';

  meta = {
    description = "syncrain as a Plasma 6 wallpaper, for the desktop and the lock screen";
    homepage = "https://github.com/Atyzze/syncrain";
    license = lib.licenses.mit;
    platforms = lib.platforms.linux;
  };
}
