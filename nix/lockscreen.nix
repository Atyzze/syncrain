# The lock screen: the QML module org.syncrain (syncrain/lockscreen/) and the shell package
# org.syncrain.lockscreen that kscreenlocker_greet loads. On NixOS the lock screen still has to be
# pointed at it (install.sh --lock-screen does that on Arch); tests/lockscreen/ builds it with this.
{
  lib,
  stdenv,
  cmake,
  qt6,
}:

stdenv.mkDerivation {
  pname = "syncrain-lockscreen";
  version = lib.fileContents ../BUILD_NUMBER;

  src = lib.cleanSourceWith {
    src = ../syncrain;
    filter = path: _type: !(lib.hasSuffix ".py" path) && !(lib.hasInfix "/data" path);
  };

  nativeBuildInputs = [ cmake ];
  buildInputs = [ qt6.qtbase qt6.qtdeclarative ];
  dontWrapQtApps = true;

  cmakeDir = "../lockscreen";

  installPhase = ''
    runHook preInstall
    install -Dm644 -t $out/lib/qt-6/qml/org/syncrain qml/org/syncrain/qmldir qml/org/syncrain/*.qmltypes
    install -Dm755 -t $out/lib/qt-6/qml/org/syncrain qml/org/syncrain/*.so
    mkdir -p $out/share/plasma/shells
    cp -r ../lockscreen/package $out/share/plasma/shells/org.syncrain.lockscreen
    runHook postInstall
  '';

  meta = {
    description = "syncrain's lock screen for KDE Plasma 6: the rain behind syncrain's box";
    homepage = "https://github.com/Atyzze/syncrain";
    license = lib.licenses.mit;
    platforms = lib.platforms.linux;
  };
}
