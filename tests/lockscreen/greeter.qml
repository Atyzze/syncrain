/*
    kscreenlocker_greet, as far as LockScreen.qml sees it: a window, the `authenticator` it gives the
    lock screen (here a stand-in whose password is "right"), and the lock screen loaded into it.
    Run by Qt's qml tool: greeter.qml -- <LockScreen.qml URL> <what> [<png>]
      shot <png>: once the rain has drawn (or failed), the window as a PNG, then exit 0
      flow:       types a wrong password, then at once the right one; says each step; exit 0 when unlocked
      again:      the same, the right one only once PAM asks again
      replug:     the screen made anew while PAM asks (a screen plugged in again), then the right one
      visible:    PAM asks a question whose answer shows (a one-time code); the right one answers it
      fresh:      PAM is asking before the lock screen loads (every screen went and one came back:
                  kscreenlocker's new view has a new engine); the right one still answers it
      unlocked:   PAM said yes before the lock screen loaded (no screen was there): it quits at once
      twofactor:  the password, then a second secret question; the password sent again while the
                  first is checked must not answer the second; the code does
      enter:      PAM asks a question whose answer shows and wants only Enter; Enter answers it
      checking:   the screen comes back while PAM checks the password of a two-factor stack; the
                  password sent again there must not reach the second question
      idle:       the screen comes back just after a refusal; it does not start PAM inside the delay
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

    // kscreenlocker 6.7's PamAuthenticators as the lock screen meets them: PAM asks a little later,
    // in Dutch, as on the operator's machine; a response while PAM checks the last one waits for
    // the next question (6.7's worker takes it there), one with nothing under way is lost; after a
    // refusal PAM asks for a 2 s delay, and a start within it is refused at once ("too soon").
    QtObject {
        id: authenticator
        property bool unlocked: false
        property bool hadPrompt: false
        property string prompt: ""
        property string promptForSecret: ""
        property string infoMessage: ""
        property string errorMessage: ""
        property int starts: 0
        property bool running: false          // a conversation is on
        property bool asking: false           // and PAM is waiting for the password
        property real nextAllowed: 0
        property int factor: 1                // twofactor: which question PAM asks
        property var log: []                  // every answer PAM got
        property bool busy: false             // PAM is checking an answer
        readonly property int state: running ? 1 : 0   // Idle 0, Authenticating 1
        property var queued: []               // answers given while busy, for the next question
        signal failed(int kind)
        signal succeeded()
        signal loginFailedDelayStarted(int kind, var who, int uSecDelay)
        function startAuthenticating() {
            if (running)
                return;
            starts++;
            if (Date.now() < nextAllowed) {
                console.log("flow: too soon");
                failed(0);
                return;
            }
            running = true;
            ask.start();
        }
        function stopAuthenticating() { console.log("flow: stopped"); }
        function respond(text) {
            console.log("flow: responded " + text);
            if (!asking) {
                if (busy) {
                    console.log("flow: queued");
                    queued.push(String(text));
                } else {
                    console.log("flow: dropped");
                }
                return;
            }
            asking = false;
            busy = true;
            log.push(String(text));
            answer.text = String(text);
            answer.interval = win.argv[1] === "twofactor" || win.argv[1] === "checking" ? 600 : 50;
            answer.start();
        }
    }
    Timer {
        id: ask
        interval: 50
        onTriggered: {
            pose();
            if (authenticator.queued.length > 0)  // 6.7's worker answers the new question with it
                authenticator.respond(authenticator.queued.shift());
        }
        function pose() {
            authenticator.hadPrompt = true;
            authenticator.asking = true;
            if (win.argv[1] === "enter") {        // "press Enter" (pam_u2f interactive)
                authenticator.prompt = "Touch the key, then press Enter";
                return;
            }
            if ((win.argv[1] === "twofactor" || win.argv[1] === "checking") && authenticator.factor === 2) {
                authenticator.promptForSecret = "Verificatiecode: ";
                return;
            }
            if (win.argv[1] === "visible") {      // a question whose answer shows (a one-time code)
                if (authenticator.prompt === "Code:")
                    authenticator.promptChanged();
                else
                    authenticator.prompt = "Code:";
                return;
            }
            // the real signal comes with every question, the same words or not
            if (authenticator.promptForSecret === "Wachtwoord: ")
                authenticator.promptForSecretChanged();
            else
                authenticator.promptForSecret = "Wachtwoord: ";
        }
    }
    Timer {
        id: answer
        property string text
        interval: 50
        onTriggered: {
            authenticator.busy = false;
            if ((win.argv[1] === "twofactor" || win.argv[1] === "checking") && authenticator.factor === 1
                    && text === "right") {
                authenticator.factor = 2;         // the password was right: PAM asks for the code
                ask.start();
                return;
            }
            if (win.argv[1] === "enter" && text === "") {
                authenticator.running = false;
                authenticator.unlocked = true;
                authenticator.succeeded();
                return;
            }
            authenticator.running = false;
            if (text === "right" || ((win.argv[1] === "twofactor" || win.argv[1] === "checking") && text === "123456")) {
                authenticator.unlocked = true;
                authenticator.succeeded();
            } else {
                authenticator.nextAllowed = Date.now() + 2000;
                authenticator.loginFailedDelayStarted(0, null, 2000000);
                authenticator.failed(0);
            }
        }
    }

    // fresh, unlocked, checking and idle: the conversation comes first, the lock screen after it
    readonly property bool late: ["fresh", "unlocked", "checking", "idle"].indexOf(win.argv[1]) >= 0
    Timer {
        id: before
        interval: 100
        running: win.late
        repeat: true
        onTriggered: {
            if (win.argv[1] === "unlocked" && !authenticator.unlocked) {
                authenticator.startAuthenticating();
                authenticator.hadPrompt = true;
                authenticator.unlocked = true;
                authenticator.succeeded();        // said to an engine that is no longer there
                return;
            }
            if (win.argv[1] === "fresh" && !authenticator.running) {
                authenticator.startAuthenticating();
                return;
            }
            if (win.argv[1] === "fresh" && !authenticator.asking)
                return;
            // checking: the password answered by the engine that went, and the screen back while
            // PAM checks it; idle: a wrong one refused, and the screen back inside the delay
            if (win.argv[1] === "checking" || win.argv[1] === "idle") {
                if (!authenticator.running && authenticator.log.length === 0) {
                    authenticator.startAuthenticating();
                    return;
                }
                if (authenticator.asking && authenticator.log.length === 0) {
                    authenticator.respond(win.argv[1] === "checking" ? "right" : "wrong");
                    return;
                }
                if (win.argv[1] === "checking" && !authenticator.busy)
                    return;
                if (win.argv[1] === "idle" && authenticator.running)
                    return;
            }
            stop();
            console.log("flow: loaded late");
            screen.source = win.argv[0];
        }
    }

    Loader {
        id: screen
        anchors.fill: parent
        source: win.late ? "" : win.argv[0]
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
            if (step === 0 && what === "replug") {
                // a screen unplugged and plugged in again while PAM asks: kscreenlocker makes it anew
                if (!authenticator.asking)
                    return;
                screen.source = "";
                screen.source = win.argv[0];
                console.log("flow: replugged");
                step = 4;
                return;
            }
            if (step === 4) {                 // the new screen's box gets the right password
                const fresh = win.find(screen.item, "password");
                if (!fresh)
                    return;
                fresh.text = "right";
                fresh.accepted();
                step = 3;
                return;
            }
            if (step === 0 && what === "fresh") {    // the open question, met by a new singleton
                field.text = "right";
                field.accepted();
                step = 3;
                return;
            }
            if (what === "unlocked") {
                if (tries > 20) { console.log("flow: still locked"); Qt.exit(6); }
                return;
            }
            if (step === 0 && what === "checking") {  // the password again, while it is checked
                field.text = "right";
                field.accepted();
                step = 11;
                return;
            }
            if (step === 0 && what === "idle") {      // nothing until PAM asks again; then the right one
                if (!authenticator.asking) {
                    if (tries > 40) { console.log("flow: never asked again"); Qt.exit(6); }
                    return;
                }
                field.text = "right";
                field.accepted();
                step = 3;
                return;
            }
            if (step === 0 && what === "enter") {
                if (!authenticator.asking)
                    return;
                win.find(screen.item, "box").activity();   // the person is there: the box is up
                field.text = "";
                field.accepted();
                step = 3;
                return;
            }
            if (what === "twofactor" || (what === "checking" && step >= 10)) {
                if (step === 0) {
                    if (!authenticator.asking)
                        return;
                    field.text = "right";
                    field.accepted();
                    step = 10;
                } else if (step === 10) {         // while it is checked, the password once more
                    field.text = "right";
                    field.accepted();
                    step = 11;
                } else if (step === 11) {
                    if (!authenticator.asking || authenticator.factor !== 2)
                        return;
                    console.log("flow: second question, answers so far " + JSON.stringify(authenticator.log)
                                + ", message '" + message.text + "'");
                    field.text = "123456";
                    field.accepted();
                    step = 3;
                } else if (tries > 60) {
                    console.log("flow: still locked");
                    Qt.exit(6);
                }
                return;
            }
            if (step === 0 && what === "visible") {
                if (!authenticator.asking)
                    return;
                field.text = "right";
                field.accepted();
                step = 3;
                return;
            }
            if (step === 0) {
                if (!authenticator.asking)
                    return;
                console.log("flow: asked " + authenticator.starts + " times, focus " + field.activeFocus);
                field.text = "wrong";
                field.accepted();
                step = 1;
            } else if (step === 1) {
                console.log("flow: after the wrong one, field '" + field.text + "', message '" + message.text + "'");
                if (what === "flow") {        // the right one at once, while PAM waits out its delay
                    field.text = "right";
                    field.accepted();
                    step = 3;
                } else {
                    step = 2;
                }
            } else if (step === 2) {          // "again": PAM asks once more, in Dutch, and then the right one
                if (!authenticator.asking)
                    return;
                console.log("flow: asked again, message '" + message.text + "'");
                field.text = "right";
                field.accepted();
                step = 3;
            } else if (tries > 40) {
                console.log("flow: still locked");
                Qt.exit(6);
            }
        }
    }
}
