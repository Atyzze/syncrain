// qml package.qml -- OUT.png MAIN.qml JSON: the wallpaper package's main.qml with that
// configuration (the stub WallpaperItem stands in for libplasma's), one frame saved.
import QtQuick
import QtQuick.Window

Window {
    id: win
    width: 640; height: 360; visible: true; color: "black"
    readonly property var given: Qt.application.arguments.slice(Qt.application.arguments.indexOf("--") + 1)
    property var rain: null

    function find(item) {
        if (item.renderScale !== undefined && item.frames !== undefined)
            return item
        for (let i = 0; i < item.children.length; i++) {
            const found = find(item.children[i])
            if (found)
                return found
        }
        return null
    }

    Loader {
        id: wallpaper
        anchors.fill: parent
        Component.onCompleted: setSource(win.given[1], { configuration: JSON.parse(win.given[2]) })
        onLoaded: { win.rain = win.find(item); console.warn("arguments:", JSON.stringify(win.rain.arguments)) }
    }
    Timer {
        interval: 200; repeat: true; running: true
        onTriggered: if (win.rain && win.rain.frames >= 1) { stop(); grab.start() }
    }
    Timer { id: grab; interval: 300; onTriggered: win.contentItem.grabToImage(r => { r.saveToFile(win.given[0]); Qt.quit() }) }
    Timer { interval: 90000; running: true; onTriggered: Qt.exit(2) }
}
