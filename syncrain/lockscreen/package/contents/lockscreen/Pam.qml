/*
    The conversation with PAM, one for every screen (a singleton: kscreenlocker draws each screen in
    its own view on one QML engine, and PAM's conversation is the locker's, not a screen's). Each
    screen's LockScreen.qml shows it and hands it what is typed; a screen plugged in while locked
    finds it as it is.

    By Plasma 6.7's own lock screen's rules: PAM is started when a screen comes up and on any key or
    click, and after a refused password only once 3 s (or the delay PAM asked for) have passed;
    started sooner, kscreenlocker refuses at once ("too soon"). A password goes to PAM while PAM is
    asking (`waiting`); one typed inside a refusal's delay is kept and goes to the first secret
    question of the next conversation, and to nothing else (never a second factor, never a question
    whose answer shows). Nothing here can unlock: kscreenlocker quits only once PAM has said yes.

    When every screen goes while locked, kscreenlocker 6.7 drops its views and with them this QML
    engine; the screen that comes back gets a new engine, and so a new singleton, while PAM's
    question may still be open. `attach` reads what it can of that from the authenticator, so the
    password typed there reaches an open question (as Plasma's own lock screen, which answers
    whatever is open, would) and a yes said while no screen was there still unlocks. While PAM is
    still checking an answer, nothing is sent: kscreenlocker 6.7 would hand it to the next
    question, which may be a second factor.
*/
pragma Singleton

import QtQuick

QtObject {
    id: pam

    property var auth: null                  // kscreenlocker's `authenticator`, given by LockScreen.qml
    property bool waiting: false             // PAM has asked a question and not yet had its answer
    property bool secret: true               // the question asked is a secret one (the password)
    property string pending: ""              // typed inside a refusal's delay, for the next conversation
    property bool fresh: false               // this screen started the conversation PAM asks in now
    property bool conversing: false          // a conversation this engine knows of is under way
    property bool passwordless: false        // PAM let us in without asking: Unlock is a click
    property string message: ""
    property bool failing: false
    property bool erredThisTry: false        // PAM said why it refused (faillock's minutes, say)
    property bool delayGiven: false          // PAM asked for a delay of its own after this refusal
    property int answers: 0                  // answers given in this conversation
    property bool firstOpen: false           // the open question is the first secret one this screen started

    signal refused()                         // each screen's box shakes
    signal asked()                           // each screen's box takes the keyboard
    signal notice()                          // worth showing the box for: a reader's words, no password needed

    // PAM's delay after a refusal (Plasma 6.8 and later; undefined, so never, before)
    readonly property bool paused: auth !== null && auth.inPasswordDelay === true

    function say(text, failing) {
        if (text && text.length > 0) {
            pam.message = text;
            pam.failing = failing;
        }
    }

    // The first screen's LockScreen.qml gives the authenticator. A new engine can meet a conversation
    // already under way (every screen went and one came back): a question asked before may be open,
    // and a yes may already have been said.
    function attach(authenticator) {
        pam.auth = authenticator;
        if (authenticator.unlocked) {
            pam.unlocked();
            return;
        }
        if (authenticator.hadPrompt !== true)    // nothing asked yet (or a kscreenlocker without it)
            return;
        // hadPrompt stays true for the greeter's life: a conversation is under way only while the
        // authenticators are Authenticating (1), and a question is open only while PAM is not busy
        // checking an answer
        if (authenticator.state !== 1) {
            // after a refusal: a start inside its delay is refused at once ("too soon")
            retry.interval = 3000;
            retry.restart();
            return;
        }
        pam.conversing = true;
        pam.fresh = false;
        pam.answers = 1;                         // not known to be the first: later questions are said
        if (authenticator.busy === true)
            return;
        const visible = authenticator.prompt ? authenticator.prompt : "";
        const hidden = authenticator.promptForSecret ? authenticator.promptForSecret : "";
        pam.waiting = true;
        pam.secret = !(visible.length > 0 && hidden.length === 0);
        // the words of the open question, where they are certain (a stack that asked both kinds
        // leaves both, and which is open is not known)
        if (visible.length === 0 || hidden.length === 0)
            pam.say(hidden.length > 0 ? hidden : visible, false);
    }

    function start() {
        if (pam.auth && !retry.running && !pam.auth.unlocked) {
            if (!pam.conversing) {
                pam.conversing = true;
                pam.fresh = true;
                pam.answers = 0;
            }
            pam.auth.startAuthenticating();
        }
    }

    function hand(password) {
        pam.message = "";
        pam.failing = false;
        pam.erredThisTry = false;
        if (pam.waiting && !pam.paused) {
            pam.waiting = false;
            pam.firstOpen = false;
            pam.answers++;
            pam.auth.respond(password);
        } else {
            pam.pending = password;
            pam.start();
        }
    }

    // the box sent away (Escape, a minute idle, a suspend): a password typed but not yet sent goes
    // with it, so it is not tried later behind the person's back
    function forget() {
        pam.pending = "";
    }

    function question(isSecret) {
        const first = pam.fresh;
        pam.fresh = false;
        pam.conversing = true;
        pam.waiting = true;
        pam.secret = isSecret;
        // a password kept goes only where it was typed for: the first secret question of a
        // conversation this screen started (a second factor asked after it gets nothing)
        pam.firstOpen = first && isSecret;
        pam.asked();
        if (pam.pending.length > 0 && !pam.paused) {
            const p = pam.pending;
            pam.pending = "";
            if (pam.firstOpen)
                pam.hand(p);
        }
    }

    function unlocked() {
        pam.waiting = false;
        pam.conversing = false;
        if (pam.auth.hadPrompt) {
            pam.auth.stopAuthenticating();
            Qt.quit();
        } else {                               // no password asked (none set, or a reader): a click
            pam.passwordless = true;
            pam.say(qsTr("Unlock: no password is needed"), false);
            pam.notice();
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
            pam.conversing = false;
            pam.fresh = false;
            pam.firstOpen = false;
            pam.answers = 0;
            // a password typed while this one was checked stays pending, for the next question
            const said = qsTr("Unlocking failed");
            if (pam.erredThisTry && pam.message.length > 0)
                pam.say(pam.message + "\n" + said, true);
            else
                pam.say(said, true);
            pam.erredThisTry = false;
            // PAM's own delay for this refusal, else the usual 3 s: a long delay once is not every time's
            if (!pam.delayGiven)
                retry.interval = 3000;
            pam.delayGiven = false;
            retry.restart();
            pam.refused();
        }
        function onLoginFailedDelayStarted(kind, who, uSecDelay) {
            if (kind != 0)
                return;
            retry.interval = Math.max(3000, Math.ceil(uSecDelay / 1000) + 100);
            pam.delayGiven = true;
        }
        function onSucceeded() { pam.unlocked(); }
        function onInfoMessageChanged() { pam.say(pam.auth.infoMessage, false); }
        function onErrorMessageChanged() {
            pam.say(pam.auth.errorMessage, true);
            pam.erredThisTry = true;
        }
        // a question whose answer shows (a one-time code, say): asked and answered like the password.
        // An empty one is no question: kscreenlocker clears the words when a conversation ends, and
        // 6.8 says them empty as it starts.
        function onPromptChanged() {
            if (!pam.auth.prompt)
                return;
            pam.say(pam.auth.prompt, false);
            pam.question(false);
        }
        // the field already asks for the password, in any language PAM asks in; a secret question
        // after an answer (a second factor) is said, so the person knows what the field wants now
        function onPromptForSecretChanged() {
            if (!pam.auth.promptForSecret)
                return;
            if (pam.answers > 0)
                pam.say(pam.auth.promptForSecret, false);
            pam.question(true);
        }
        // PAM's delay over (6.8): a password kept through it goes to the question it was typed for
        function onInPasswordDelayChanged() {
            if (!pam.paused && pam.waiting && pam.firstOpen && pam.pending.length > 0) {
                const p = pam.pending;
                pam.pending = "";
                pam.hand(p);
            }
        }
        function onNoninteractiveInfo(kind, who) { if (who) { pam.say(who.infoMessage, false); pam.notice(); } }
        function onNoninteractiveError(kind, who) { if (who) { pam.say(who.errorMessage, true); pam.notice(); } }
    }
}
