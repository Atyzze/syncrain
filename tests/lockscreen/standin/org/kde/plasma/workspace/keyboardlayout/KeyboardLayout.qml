// Plasma's keyboard layout module as KeyboardName.qml meets it (plasma-workspace 6.7): the layouts, the
// one in use, and switching to the next; every screen's object sees the same one (KWin's, over D-Bus
// in Plasma; a singleton here).
import QtQuick

QtObject {
    readonly property var layoutsList: LayoutState.layouts
    readonly property int layout: LayoutState.current
    function switchToNextLayout() { LayoutState.current = (LayoutState.current + 1) % LayoutState.layouts.length; }
}
