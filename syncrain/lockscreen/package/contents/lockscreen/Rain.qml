/*
    The rain, drawn by syncrain's QML module (syncrain/lockscreen/rainitem.cpp) from the scene that
    install.sh --lock-screen and each start of the wallpaper write. In a file of its own so that
    LockScreen.qml loads without it when the module is missing.
*/
import QtQuick
import org.syncrain

SyncRain {
    objectName: "rain"
    fps: Shared.fps
    // the settings file's lock_rest, carried in the scene; 0 (the default): the rain never rests
    onRestChanged: Shared.restMs = Math.round(rest * 1000)
}
