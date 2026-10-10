// qml settings.qml -- CONFIG.qml: the settings page loads and its controls set the cfg_ values.
import QtQuick
import QtQuick.Controls

ApplicationWindow {
    id: win
    width: 640; height: 800; visible: true
    readonly property var given: Qt.application.arguments.slice(Qt.application.arguments.indexOf("--") + 1)
    Loader {
        id: page
        anchors.fill: parent
        Component.onCompleted: setSource(win.given[0], {
            cfg_Theme: "matrix", cfg_Channel: "friends", cfg_Fps: 20, cfg_Logo: "", cfg_Rainbow: "off",
            cfg_Glow: 0.5, cfg_Bloom: 1, cfg_BgGain: 0.6, cfg_Speed: 1, cfg_Density: 1, cfg_Hieroglyphs: 0.15,
            cfg_Snow: false, cfg_PauseUnder: "fullscreen", cfg_Scale: 1, cfg_ExtraArgs: "" })
        onStatusChanged: {
            if (status === Loader.Error) Qt.exit(3)
            if (status === Loader.Ready) done.start()
        }
    }
    Timer { id: done; interval: 1000; onTriggered: { console.warn("loaded:", page.item.cfg_Theme, page.item.cfg_Fps); Qt.quit() } }
    Timer { interval: 60000; running: true; onTriggered: Qt.exit(2) }
}
