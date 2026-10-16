// What KWin knows: the layouts configured and the one in use (tests set them).
pragma Singleton
import QtQuick

QtObject {
    property var layouts: [{ shortName: "us", displayName: "", longName: "English (US)" }]
    property int current: 0
}
