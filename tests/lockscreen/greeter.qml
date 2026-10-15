/*
    kscreenlocker_greet, as far as LockScreen.qml sees it: a window, the `authenticator` it gives the
    lock screen (here a stand-in whose password is "right"), and the lock screen loaded into it.
    Run by Qt's qml tool: greeter.qml -- <LockScreen.qml URL> <what> [<png>]
      shot <png>: once the rain has drawn (or failed), the window as a PNG, then exit 0
      flow:       types a wrong password, then the right one; says each step; exit 0 when unlocked
*/
import QtQuick
import QtQuick.Window

Window {
    id: win
    width: 640
    height: 360
    visible: true
    color: "black"

    readonly property var argv: Qt.application.arguments.slice(Qt.application.arguments.indexOf("--") + 1)

    QtObject {
        id: authenticator
        property bool unlocked: false
        property bool hadPrompt: false
        property string prompt: ""
        property string promptForSecret: ""
        property string infoMessage: ""
        property string errorMessage: ""
        property int starts: 0
        signal failed(int kind)
        signal succeeded()
        function startAuthenticating() {
            starts++;
            if (promptForSecret === "")
                promptForSecret = "Password: ";
        }
        function stopAuthenticating() { console.log("flow: stopped"); }
        function respond(text) {
            hadPrompt = true;
            console.log("flow: responded " + text);
            if (String(text) === "right") {
                unlocked = true;
                succeeded();
            } else {
                failed(0);
            }
        }
    }

    Loader {
        id: screen
        anchors.fill: parent
        source: win.argv[0]
        onStatusChanged: {
            if (status === Loader.Error) {
                console.log("flow: the lock screen did not load");
                Qt.exit(4);
            }
        }
        onLoaded: run.start()
    }

    function find(item, name) {
        if (!item)
            return null;
        if (item.objectName === name)
            return item;
        for (let i = 0; i < item.children.length; i++) {
            const found = find(item.children[i], name);
            if (found)
                return found;
        }
        return null;
    }

    Timer {
        id: run
        interval: 300
        repeat: true
        property int tries: 0
        property int step: 0
        onTriggered: {
            tries++;
            const what = win.argv[1];
            if (what === "shot") {
                const rain = win.find(screen.item, "rain");
                const status = rain ? rain.status : "no item";
                if (status === "preparing" && tries < 60)
                    return;
                stop();
                console.log("flow: rain " + status + (rain ? ", frames " + rain.frames : ""));
                screen.grabToImage(r => { r.saveToFile(win.argv[2]); Qt.exit(status === "drawing" ? 0 : 3); });
                return;
            }
            const field = win.find(screen.item, "password");
            const message = win.find(screen.item, "message");
            if (!field) {
                if (tries > 20) { console.log("flow: no password field"); Qt.exit(5); }
                return;
            }
            if (step === 0) {
                console.log("flow: asked " + authenticator.starts + " times, focus " + field.activeFocus);
                field.text = "wrong";
                field.accepted();
                step = 1;
            } else if (step === 1) {
                console.log("flow: after the wrong one, field '" + field.text + "', message '" + message.text + "'");
                field.text = "right";
                field.accepted();
                step = 2;
            } else if (tries > 40) {
                console.log("flow: still locked");
                Qt.exit(6);
            }
        }
    }
}
