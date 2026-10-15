/*
    syncrain's lock screen: the rain behind syncrain's own box, on every screen.

    kscreenlocker_greet loads this file, once for each screen, from the shell package
    org.syncrain.lockscreen (install.sh --lock-screen points KWin's lock screen at it) and gives it
    `authenticator` (PAM), `kscreenlocker_userName` and the property `locked`. The conversation with
    PAM is Pam.qml's, one for all the screens; nothing here can unlock but PAM saying yes.
    The rain (Rain.qml) and the Caps Lock note (CapsLock.qml) come through Loaders: if either cannot
    load, the screen is black behind the box and unlocking works as before. If this file itself
    cannot load, kscreenlocker draws its own built-in lock screen.
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

    Connections {
        target: Pam
        function onRefused() { shake.restart(); }
        function onAsked() { box.focusPassword(); }
    }

    // the screen under the pointer takes the keyboard; a click starts PAM if it stopped
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        onPositionChanged: if (root.Window.window && !root.Window.window.active) root.Window.window.requestActivate()
        onPressed: { box.focusPassword(); Pam.start(); }
    }

    Box {
        id: box
        anchors.centerIn: parent
        title: typeof kscreenlocker_userName === "undefined" ? "" : kscreenlocker_userName
        message: [caps.item && caps.item.on ? qsTr("Caps Lock is on") : "", Pam.message].filter(s => s).join("\n")
        failing: Pam.failing
        allowEmpty: Pam.passwordless
        onEdited: { if (Pam.failing) Pam.message = ""; Pam.start(); }
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
