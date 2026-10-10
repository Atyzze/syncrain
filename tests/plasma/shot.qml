// qml shot.qml -- OUT.png TIME [syncrain options...]: one frame of the SyncRain item, saved.
import QtQuick
import QtQuick.Window
import org.syncrain

Window {
    id: win
    width: 640; height: 360; visible: true; color: "black"
    readonly property var given: Qt.application.arguments.slice(Qt.application.arguments.indexOf("--") + 1)
    SyncRain {
        anchors.fill: parent
        arguments: win.given.slice(2)
        fixedTime: Number(win.given[1])
        onFramesChanged: if (frames === 1) grab.start()
        onStatusChanged: { console.log("status:", status); if (status.startsWith("error")) Qt.exit(3) }
    }
    Timer { id: grab; interval: 300; onTriggered: win.contentItem.grabToImage(r => { r.saveToFile(win.given[0]); Qt.quit() }) }
    Timer { interval: 90000; running: true; onTriggered: Qt.exit(2) }
}
