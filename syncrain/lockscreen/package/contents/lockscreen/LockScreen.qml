/*
    syncrain's lock screen: the rain behind syncrain's own box, on every screen.

    kscreenlocker_greet loads this file, once for each screen, from the shell package
    org.syncrain.lockscreen (install.sh --lock-screen points KWin's lock screen at it) and gives it
    `authenticator` (PAM), `kscreenlocker_userName` and the property `locked`. The conversation with
    PAM is Pam.qml's, and what the boxes show is Shared.qml's, one for all the screens: the box comes
    up on a key or a moved pointer, goes after a minute without either, and shows on every screen
    what is typed on any. Nothing here can unlock but PAM saying yes.
    The rain (Rain.qml), the Caps Lock note (CapsLock.qml) and the suspend hook (Suspend.qml) come
    through Loaders: if one cannot load, the screen is black behind the box (or the note or the
    hook is missing) and unlocking works as before. If this file itself cannot load, kscreenlocker
    draws its own built-in lock screen.
*/
import QtQuick
import QtQuick.Window

Item {
    id: root

    // what kscreenlocker sets and reads
    property bool locked: false
    property bool viewVisible: false
    property bool suspendToRamSupported: false
    property bool suspendToDiskSupported: false
    signal suspendToRam()
    signal suspendToDisk()

    implicitWidth: 800
    implicitHeight: 600

    Rectangle {
        anchors.fill: parent
        color: "black"
    }

    Loader {
        id: rain
        anchors.fill: parent
        source: Qt.resolvedUrl("Rain.qml")
        onStatusChanged: if (status === Loader.Error) console.warn("syncrain: the lock screen draws no rain (its QML module did not load)")
    }

    Loader {
        id: caps
        source: Qt.resolvedUrl("CapsLock.qml")
    }

    Loader {
        source: Qt.resolvedUrl("Suspend.qml")
    }

    Connections {
        target: Pam
        function onRefused() { Shared.wake(); shake.restart(); }
        function onAsked() { box.focusPassword(); }
        function onNotice() { Shared.wake(); }
    }

    function woke() {
        Shared.wake();
        Pam.start();
    }

    // A pointer moved by the person brings the box up, and its screen takes the keyboard: anywhere
    // on the screen, over the box too (a HoverHandler sees what its children are hovered by). The
    // first point a screen reports is KWin placing the pointer as the lock comes up; and Qt reports
    // a still pointer again whenever what lies under it changes (the box resizing for a message, a
    // screen going): so only a move of more than a few pixels from the last point counts.
    property point lastPoint
    property bool seenPoint: false
    HoverHandler {
        id: hover
        cursorShape: Shared.shown ? Qt.ArrowCursor : Qt.BlankCursor
        onPointChanged: {
            const p = hover.point.scenePosition;
            if (!hover.hovered)
                return;
            if (!root.seenPoint) {
                root.seenPoint = true;
                root.lastPoint = p;
                return;
            }
            const moved = Math.abs(p.x - root.lastPoint.x) + Math.abs(p.y - root.lastPoint.y);
            if (moved < 4)
                return;
            root.lastPoint = p;
            if (root.Window.window && !root.Window.window.active)
                root.Window.window.requestActivate();
            root.woke();
        }
    }

    // a click outside the box brings it up and starts PAM if it stopped
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        onPressed: { box.focusPassword(); root.woke(); }
    }

    Box {
        id: box
        objectName: "box"
        anchors.centerIn: parent
        title: typeof kscreenlocker_userName === "undefined" ? "" : kscreenlocker_userName
        message: [caps.item && caps.item.on ? qsTr("Caps Lock is on") : "", Pam.message].filter(s => s).join("\n")
        failing: Pam.failing
        allowEmpty: Pam.passwordless
        shared: Shared.typed
        peeking: Shared.peek
        // away, the box still has the keyboard: the first key brings it up and goes into the field
        opacity: Shared.shown ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 250 } }
        onTyped: text => {
            Shared.typed = text;
            if (text.length > 0 && Pam.failing)
                Pam.message = "";
            root.woke();
        }
        onActivity: root.woke()
        onPeekSet: on => { Shared.peek = on; root.woke(); }
        onDismissed: Shared.sleep()        // and an unsent password goes with it (Pam.forget)
        onSubmitted: password => {
            if (Pam.passwordless) {            // PAM has already said yes, without a password
                Pam.auth.stopAuthenticating();
                Qt.quit();
                return;
            }
            Pam.hand(password);
        }

        SequentialAnimation {
            id: shake
            loops: 1
            NumberAnimation { target: box; property: "anchors.horizontalCenterOffset"; to: -14; duration: 50 }
            NumberAnimation { target: box; property: "anchors.horizontalCenterOffset"; to: 14; duration: 70 }
            NumberAnimation { target: box; property: "anchors.horizontalCenterOffset"; to: -8; duration: 60 }
            NumberAnimation { target: box; property: "anchors.horizontalCenterOffset"; to: 0; duration: 50 }
        }
    }

    Component.onCompleted: {
        if (!Pam.auth && typeof authenticator !== "undefined")
            Pam.auth = authenticator;
        box.focusPassword();
        Pam.start();
    }
}
