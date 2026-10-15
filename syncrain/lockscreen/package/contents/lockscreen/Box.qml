/*
    syncrain's box on the lock screen: the login screen's box (syncrain/greeter.py, its CSS) in QML.
    The user's name, the password, Unlock, and what PAM or the lock screen says.
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
    signal submitted(string password)
    signal edited()

    function clear() { password.text = ""; focusPassword(); }
    function focusPassword() { password.forceActiveFocus(); }

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
        const typed = password.text;
        password.text = "";
        box.submitted(typed);
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
            echoMode: peek.checked ? TextInput.Normal : TextInput.Password
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
            onTextEdited: box.edited()
            Keys.onEscapePressed: text = ""

            AbstractButton {
                id: peek
                objectName: "peek"
                checkable: true
                focusPolicy: Qt.NoFocus
                anchors.right: parent.right
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                width: 24
                height: 24
                contentItem: Text {
                    text: peek.checked ? "◉" : "◎"       // an eye, open or shut
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
