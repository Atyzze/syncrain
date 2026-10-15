/*
    The rain, drawn by syncrain's QML module (syncrain/lockscreen/rainitem.cpp) from the scene that
    install.sh --lock-screen and each start of the wallpaper write. In a file of its own so that
    LockScreen.qml loads without it when the module is missing.
*/
import QtQuick
import org.syncrain

SyncRain {
    objectName: "rain"
}
