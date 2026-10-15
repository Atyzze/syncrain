/*
    Whether Caps Lock is on, from Plasma's keyboard indicator (as Plasma's own lock screen asks). In
    a file of its own: where that module is missing, the box just does not say it.
*/
import QtQuick
import org.kde.plasma.private.keyboardindicator as KeyboardIndicator

KeyboardIndicator.KeyState {
    readonly property bool on: locked
    key: Qt.Key_CapsLock
}
