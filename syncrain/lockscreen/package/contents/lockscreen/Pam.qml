/*
    The conversation with PAM, one for every screen (a singleton: kscreenlocker draws each screen in
    its own view on one QML engine, and PAM's conversation is the locker's, not a screen's). Each
    screen's LockScreen.qml shows it and hands it what is typed; a screen plugged in while locked
    finds it as it is.

    By Plasma 6.7's own lock screen's rules: PAM is started when a screen comes up and on any key or
    click, and after a refused password only once 3 s (or the delay PAM asked for) have passed;
    started sooner, kscreenlocker refuses at once ("too soon"). A password goes to PAM only while
    PAM is asking (`waiting`); one typed at any other moment is kept and goes at the next question.
    Nothing here can unlock: kscreenlocker quits only once PAM has said yes.
*/
pragma Singleton

import QtQuick

QtObject {
    id: pam

    property var auth: null                  // kscreenlocker's `authenticator`, given by LockScreen.qml
    property bool waiting: false             // PAM has asked a question and not yet had its answer
    property string pending: ""              // typed while PAM was not asking
    property bool passwordless: false        // PAM let us in without asking: Unlock is a click
    property string message: ""
    property bool failing: false
    property bool erredThisTry: false        // PAM said why it refused (faillock's minutes, say)

    signal refused()                         // each screen's box shakes
    signal asked()                           // each screen's box takes the keyboard

    readonly property bool paused: auth !== null && auth.pamTimeout === true   // Plasma 6.8 and later

    function say(text, failing) {
        if (text && text.length > 0) {
            pam.message = text;
            pam.failing = failing;
        }
    }

    function start() {
        if (pam.auth && !retry.running && !pam.auth.unlocked)
            pam.auth.startAuthenticating();
    }

    function hand(password) {
        pam.message = "";
        pam.failing = false;
        pam.erredThisTry = false;
        if (pam.waiting && !pam.paused) {
            pam.waiting = false;
            pam.auth.respond(password);
        } else {
            pam.pending = password;
            pam.start();
        }
    }

    function question() {
        pam.waiting = true;
        pam.asked();
        if (pam.pending.length > 0 && !pam.paused) {
            const p = pam.pending;
            pam.pending = "";
            pam.hand(p);
        }
    }

    property Timer retry: Timer {
        interval: 3000
        onTriggered: pam.start()
    }

    property Connections watch: Connections {
        target: pam.auth
        function onFailed(kind) {
            if (kind != 0)                     // a fingerprint or smartcard reader's, not the password's
                return;
            pam.waiting = false;
            // a password typed while this one was checked stays pending, for the next question
            const said = qsTr("Unlocking failed");
            if (pam.erredThisTry && pam.message.length > 0)
                pam.say(pam.message + "\n" + said, true);
            else
                pam.say(said, true);
            pam.erredThisTry = false;
            retry.restart();
            pam.refused();
        }
        function onLoginFailedDelayStarted(kind, who, uSecDelay) {
            if (kind == 0 && uSecDelay / 1000 > retry.interval)
                retry.interval = Math.ceil(uSecDelay / 1000) + 100;
        }
        function onSucceeded() {
            pam.waiting = false;
            if (pam.auth.hadPrompt) {
                pam.auth.stopAuthenticating();
                Qt.quit();
            } else {                           // no password asked (none set, or a reader): a click
                pam.passwordless = true;
                pam.say(qsTr("Unlock: no password is needed"), false);
            }
        }
        function onInfoMessageChanged() { pam.say(pam.auth.infoMessage, false); }
        function onErrorMessageChanged() {
            pam.say(pam.auth.errorMessage, true);
            pam.erredThisTry = true;
        }
        // a question whose answer shows (a one-time code, say): asked and answered like the password
        function onPromptChanged() {
            pam.say(pam.auth.prompt, false);
            pam.question();
        }
        // the field already asks for the password, in any language PAM asks in
        function onPromptForSecretChanged() { pam.question(); }
        function onPamTimeoutChanged() {
            if (!pam.paused && pam.waiting && pam.pending.length > 0)
                pam.question();
        }
        function onNoninteractiveInfo(kind, who) { if (who) pam.say(who.infoMessage, false); }
        function onNoninteractiveError(kind, who) { if (who) pam.say(who.errorMessage, true); }
    }
}
