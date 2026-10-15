/*
    Two screens of syncrain's lock screen side by side, as kscreenlocker draws one per screen on one
    QML engine, driven with real key and pointer events (Qt's qmltestrunner, run by
    tests/lockscreen/test_the_lock_screen.py). The rain's module is left out: these are the boxes.
*/
import QtQuick
import QtTest
import "../../syncrain/lockscreen/package/contents/lockscreen" as Lock

Item {
    id: top
    width: 1300
    height: 380

    // kscreenlocker's `authenticator`, as far as these tests need it: PAM asking whenever started
    // (as its signal), unless `asks` is off (PAM inside its delay)
    QtObject {
        id: authenticator
        property bool asks: true
        property bool unlocked: false
        property bool hadPrompt: true
        property string prompt: ""
        property string promptForSecret: "Password: "
        property string infoMessage: ""
        property string errorMessage: ""
        property var answers: []
        signal failed(int kind)
        signal succeeded()
        function startAuthenticating() { if (asks) promptForSecretChanged(); }
        function stopAuthenticating() {}
        function respond(text) { answers.push(String(text)); }
    }

    Lock.LockScreen { id: left; x: 0; y: 0; width: 640; height: 360 }
    Lock.LockScreen { id: right; x: 650; y: 0; width: 640; height: 360 }

    TestCase {
        name: "TwoScreens"
        when: windowShown

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

        function init() {
            authenticator.asks = true;
            authenticator.hadPrompt = true;
            Lock.Pam.passwordless = false;
            Lock.Pam.waiting = false;
            Lock.Shared.idleMs = 60000;
            Lock.Shared.sleep();
            authenticator.answers = [];
            find(left, "password").forceActiveFocus();
        }

        function test_01_away_until_the_person_is_there() {
            compare(Lock.Shared.shown, false, "no box as the lock comes up");
            mouseMove(left, 100, 100);           // KWin placing the pointer: not the person
            compare(Lock.Shared.shown, false);
            mouseMove(left, 102, 101);           // a still pointer reported again, or a nudge
            compare(Lock.Shared.shown, false);
            mouseMove(left, 140, 120);
            compare(Lock.Shared.shown, true, "a moved pointer brings the box up");
            tryCompare(find(left, "box"), "opacity", 1, 1000);
        }

        function test_02_a_key_brings_it_up_and_goes_into_the_field() {
            keyClick(Qt.Key_A);
            compare(Lock.Shared.shown, true);
            compare(find(left, "password").text, "a", "the first key is not lost");
        }

        function test_03_what_is_typed_is_on_every_screen() {
            keyClick(Qt.Key_A);
            keyClick(Qt.Key_B);
            compare(find(left, "password").text, "ab");
            compare(find(right, "password").text, "ab", "the other screen shows the same");
            find(right, "password").forceActiveFocus();
            keyClick(Qt.Key_C);
            compare(find(left, "password").text, "abc", "and typing goes on from either");
            compare(find(right, "password").text, "abc");
            keyClick(Qt.Key_Backspace);
            compare(find(left, "password").text, "ab");
        }

        function test_04_the_eye_is_the_same_on_every_screen() {
            keyClick(Qt.Key_A);
            mouseClick(find(left, "peek"));
            compare(find(right, "password").echoMode, TextInput.Normal);
            mouseClick(find(right, "peek"));
            compare(find(left, "password").echoMode, TextInput.Password);
        }

        function test_05_a_minute_without_input_takes_it_away_and_forgets() {
            Lock.Shared.idleMs = 300;
            keyClick(Qt.Key_A);
            compare(Lock.Shared.shown, true);
            wait(150);
            keyClick(Qt.Key_B);                  // input keeps it up
            wait(200);
            compare(Lock.Shared.shown, true);
            tryCompare(Lock.Shared, "shown", false, 1000);
            compare(find(left, "password").text, "", "a half-typed password does not wait on screen");
            compare(find(right, "password").text, "");
        }

        function test_06_escape_takes_it_away() {
            keyClick(Qt.Key_A);
            keyClick(Qt.Key_Escape);
            compare(Lock.Shared.shown, false);
            compare(find(right, "password").text, "");
        }

        function test_07_enter_on_either_screen_sends_it_once_and_clears_both() {
            find(right, "password").forceActiveFocus();
            keyClick(Qt.Key_X);
            keyClick(Qt.Key_Y);
            keyClick(Qt.Key_Return);
            compare(authenticator.answers, ["xy"]);
            compare(find(left, "password").text, "");
            compare(find(right, "password").text, "");
        }

        function test_08_a_move_over_the_box_counts_too() {
            mouseMove(left, 320, 180);           // the middle: the hidden box's field
            mouseMove(left, 340, 186);
            compare(Lock.Shared.shown, true);
        }

        function test_09_escape_forgets_a_password_not_yet_sent() {
            authenticator.asks = false;          // PAM inside its delay after a refusal
            keyClick(Qt.Key_A);
            keyClick(Qt.Key_B);
            keyClick(Qt.Key_Return);
            compare(Lock.Pam.pending, "ab", "kept for PAM's next question");
            keyClick(Qt.Key_Escape);
            compare(Lock.Pam.pending, "", "sent away with the box: never tried behind the person's back");
            authenticator.promptForSecretChanged();
            compare(authenticator.answers, []);
        }

        function test_10_the_idle_minute_forgets_it_too() {
            Lock.Shared.idleMs = 200;
            authenticator.asks = false;
            keyClick(Qt.Key_A);
            keyClick(Qt.Key_Return);
            compare(Lock.Pam.pending, "a");
            tryCompare(Lock.Shared, "shown", false, 1000);
            compare(Lock.Pam.pending, "");
        }

        function test_11_no_password_needed_brings_the_box_up_to_say_so() {
            authenticator.hadPrompt = false;     // PAM said yes without asking (a reader, no password)
            authenticator.succeeded();
            compare(Lock.Shared.shown, true);
            compare(find(left, "message").text, "Unlock: no password is needed");
        }
    }
}
