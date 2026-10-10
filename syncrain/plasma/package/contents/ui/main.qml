// syncrain as a Plasma wallpaper: the desktop's, and the lock screen's when chosen there.
import QtQuick
import org.kde.plasma.plasmoid
import org.syncrain

WallpaperItem {
    id: root

    // The lock screen draws wallpapers too; windows never cover it there.
    readonly property bool onDesktop: Qt.application.name === "plasmashell"

    function words() {
        const c = root.configuration
        let a = ["--theme", c.Theme, "--channel", c.Channel, "--rainbow", c.Rainbow,
                 "--glow", String(c.Glow), "--bloom", String(c.Bloom), "--bg-gain", String(c.BgGain),
                 "--speed", String(c.Speed), "--density", String(c.Density),
                 "--hieroglyphs", String(c.Hieroglyphs)]
        if (c.Logo)
            a.push("--logo", c.Logo)
        if (!c.Snow)
            a.push("--snow", "off")
        if (c.ExtraArgs)
            a = a.concat(c.ExtraArgs.split(" ").filter(w => w.length > 0))
        return a
    }

    SyncRain {
        anchors.fill: parent
        arguments: root.words()
        fps: root.configuration.Fps
        renderScale: root.configuration.Scale
        pauseUnder: root.configuration.PauseUnder
        watchWindows: root.onDesktop
    }
}
