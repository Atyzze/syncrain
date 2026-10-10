// qml covered.qml: the SyncRain item, saying when KWin reports its screen covered and how many
// frames it has drawn, every half second.
import QtQuick
import QtQuick.Window
import org.syncrain

Window {
    width: 320; height: 180; visible: true; color: "black"
    SyncRain {
        id: rain
        anchors.fill: parent
        pauseUnder: "maximized"
        onCoveredChanged: console.warn("covered:", covered)
        onStatusChanged: console.warn("status:", status)
    }
    Timer { interval: 500; repeat: true; running: true; onTriggered: console.warn("frames:", rain.frames) }
}
