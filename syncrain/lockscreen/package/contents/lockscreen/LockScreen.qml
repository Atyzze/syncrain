/*
    syncrain's lock screen: the rain behind syncrain's own box, on every screen.

    kscreenlocker_greet loads this file from the shell package org.syncrain.lockscreen (install.sh
    --lock-screen points KWin's lock screen at it) and gives it `authenticator` (PAM),
    `kscreenlocker_userName` and the property `locked`. Nothing here can unlock but PAM saying yes.
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

    // what the box shows under the password field (PAM's words, or ours)
    property string message: ""
    property bool failing: false

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

    function say(text) {
        if (text && text.length > 0)
            root.message = text;
    }

    Connections {
        target: typeof authenticator === "undefined" ? null : authenticator
        function onFailed(kind) {
            if (kind != 0)                     // a fingerprint or smartcard reader's, not the password's
                return;
            root.failing = true;
            root.say(qsTr("Unlocking failed"));
            box.clear();
            authenticator.startAuthenticating();
            shake.restart();
        }
        function onSucceeded() {
            authenticator.stopAuthenticating();
            Qt.quit();
        }
        function onInfoMessageChanged() { root.failing = false; root.say(authenticator.infoMessage); }
        function onErrorMessageChanged() { root.failing = true; root.say(authenticator.errorMessage); }
        function onPromptChanged() { root.failing = false; root.say(authenticator.prompt); }
        function onPromptForSecretChanged() {
            box.focusPassword();
            const p = authenticator.promptForSecret;
            // PAM's plain "Password:" is what the field already says
            if (p && p.replace(/[:\s]+$/, "").toLowerCase() !== "password")
                root.say(p);
        }
    }

    // PAM is asked again every second while the screen is up (as Plasma's own lock screen does), so
    // a typed password always has a conversation to go to
    Timer {
        interval: 1000
        repeat: true
        triggeredOnStart: true
        running: typeof authenticator !== "undefined" && !authenticator.unlocked
        onTriggered: authenticator.startAuthenticating()
    }

    // the screen under the pointer takes the keyboard
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        onPositionChanged: if (root.Window.window && !root.Window.window.active) root.Window.window.requestActivate()
        onPressed: box.focusPassword()
    }

    Box {
        id: box
        anchors.centerIn: parent
        title: typeof kscreenlocker_userName === "undefined" ? "" : kscreenlocker_userName
        message: [caps.item && caps.item.on ? qsTr("Caps Lock is on") : "", root.message].filter(s => s).join("\n")
        failing: root.failing
        onSubmitted: password => {
            root.message = "";
            root.failing = false;
            authenticator.respond(password);
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

    Component.onCompleted: box.focusPassword()
}
