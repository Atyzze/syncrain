/*
    syncrain's box on the lock screen: the login screen's box (syncrain/greeter.py, its CSS) in QML.
    The user's name, the password, Unlock, and what PAM or the lock screen says. What is typed and
    whether it shows come from outside (`shared`, `peeking`: Shared.qml, the same on every screen);
    the box says what the person did (`typed`, `peekSet`, `activity`, `dismissed`, `submitted`).
*/
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    id: box

    property string title: ""
    property string message: ""
    property bool failing: false
    property bool allowEmpty: false          // PAM needs no password: Unlock with an empty field
    property string shared: ""               // what is typed, on every screen
    property bool peeking: false             // the password shown, on every screen
    signal submitted(string password)
    signal typed(string text)                // the person changed what is typed
    signal peekSet(bool on)
    signal activity()                        // any key
    signal dismissed()                       // Escape

    function focusPassword() { password.forceActiveFocus(); }

    // another screen's typing (or the box going away) comes in here; the cursor goes to the end
    onSharedChanged: {
        if (password.text !== box.shared) {
            password.text = box.shared;
            password.cursorPosition = box.shared.length;
        }
    }

    readonly property color ink: "#e8f1ff"
    readonly property color edge: Qt.rgba(126 / 255, 182 / 255, 1, 0.30)

    width: column.implicitWidth + 52
    height: column.implicitHeight + 32
    radius: 14
    color: Qt.rgba(3 / 255, 8 / 255, 18 / 255, 0.80)
    border.color: Qt.rgba(126 / 255, 182 / 255, 1, 0.40)
    border.width: 1

    function send() {
        if (password.text.length === 0 && !box.allowEmpty)
            return;
        const sent = password.text;
        password.text = "";
        box.typed("");
        box.submitted(sent);
    }

    ColumnLayout {
        id: column
        anchors.centerIn: parent
        spacing: 10

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: box.title
            visible: text.length > 0
            color: "#cfe3ff"
            font.pixelSize: 17
            font.bold: true
        }

        TextField {
            id: password
            objectName: "password"
            Layout.preferredWidth: 260
            echoMode: box.peeking ? TextInput.Normal : TextInput.Password
            placeholderText: qsTr("Password")
            placeholderTextColor: Qt.rgba(232 / 255, 241 / 255, 1, 0.45)
            color: box.ink
            selectByMouse: true
            inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText
            rightPadding: peek.width + 8
            background: Rectangle {
                radius: 6
                color: Qt.rgba(1, 1, 1, 0.07)
                border.width: 1
                border.color: password.activeFocus ? Qt.rgba(126 / 255, 182 / 255, 1, 0.85) : box.edge
            }
            onAccepted: box.send()
            onTextEdited: box.typed(text)
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Escape) {
                    box.dismissed();
                    event.accepted = true;
                    return;
                }
                box.activity();                  // and the field still gets the key
                event.accepted = false;
            }

            AbstractButton {
                id: peek
                objectName: "peek"
                focusPolicy: Qt.NoFocus
                onClicked: box.peekSet(!box.peeking)
                anchors.right: parent.right
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                width: 24
                height: 24
                contentItem: Text {
                    text: box.peeking ? "◉" : "◎"       // an eye, open or shut
                    color: Qt.rgba(232 / 255, 241 / 255, 1, peek.hovered ? 0.95 : 0.6)
                    font.pixelSize: 16
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: null
            }
        }

        Button {
            id: unlock
            objectName: "unlock"
            Layout.fillWidth: true
            text: qsTr("Unlock")
            focusPolicy: Qt.NoFocus
            onClicked: box.send()
            contentItem: Text {
                text: unlock.text
                color: "white"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 14
            }
            background: Rectangle {
                radius: 6
                color: unlock.hovered ? Qt.rgba(90 / 255, 150 / 255, 240 / 255, 0.95)
                                      : Qt.rgba(70 / 255, 130 / 255, 220 / 255, 0.85)
            }
        }

        Label {
            objectName: "message"
            Layout.preferredWidth: 260
            Layout.alignment: Qt.AlignHCenter
            visible: text.length > 0
            text: box.message
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
            color: box.failing ? "#ff9a8a" : "#cfe3ff"
        }
    }
}
