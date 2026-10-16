/*
    Two screens of syncrain's lock screen side by side, as kscreenlocker draws one per screen on one
    QML engine, driven with real key and pointer events (Qt's qmltestrunner, run by
    tests/lockscreen/test_the_lock_screen.py). The rain's module is left out: these are the boxes.
*/
import QtQuick
import QtTest
import "../../syncrain/lockscreen/package/contents/lockscreen" as Lock
import org.kde.plasma.workspace.keyboardlayout as Keyboards

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
        property int state: 1                 // Authenticating
        property bool busy: false
        property var answers: []
        signal failed(int kind)
        signal succeeded()
        signal loginFailedDelayStarted(int kind, var who, int uSecDelay)
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
            authenticator.prompt = "";
            authenticator.promptForSecret = "Password: ";
            authenticator.state = 1;
            authenticator.busy = false;
            Lock.Pam.passwordless = false;
            Lock.Pam.waiting = false;
            Lock.Pam.secret = true;
            Lock.Pam.conversing = false;
            Lock.Pam.fresh = false;
            Lock.Pam.firstOpen = false;
            Lock.Pam.answers = 0;
            Lock.Pam.pending = "";
            Lock.Pam.delayGiven = false;
            Lock.Pam.message = "";
            Lock.Pam.retry.stop();
            Lock.Pam.retry.interval = 3000;
            Lock.Shared.idleMs = 60000;
            Lock.Shared.restMs = 300000;
            Keyboards.LayoutState.layouts = [{ shortName: "us", displayName: "", longName: "English (US)" }];
            Keyboards.LayoutState.current = 0;
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

        function test_12_the_hidden_box_s_eye_takes_no_click() {
            compare(Lock.Shared.shown, false);
            const eye = find(left, "peek");
            mouseClick(eye);                      // where the eye is, but nobody can see it
            compare(Lock.Shared.peek, false, "a stray click shows no password on any screen");
            compare(Lock.Shared.shown, true, "the click brings the box up instead");
            mouseClick(eye);
            compare(Lock.Shared.peek, true, "once the box is up, the eye works");
            mouseClick(eye);
        }

        function test_13_a_long_delay_from_pam_counts_once() {
            authenticator.loginFailedDelayStarted(0, null, 60000000);   // faillock: a minute
            authenticator.failed(0);
            compare(Lock.Pam.retry.interval, 60100);
            Lock.Pam.retry.stop();
            authenticator.failed(0);                                    // the next refusal asks for none
            compare(Lock.Pam.retry.interval, 3000, "back to the usual 3 s");
            Lock.Pam.retry.stop();
        }

        function test_14_enter_on_the_hidden_box_answers_nothing() {
            authenticator.asks = false;           // the question below is the one open
            authenticator.prompt = "Passcode or option (1-3): ";
            authenticator.promptChanged();        // a question whose answer shows, empty allowed
            compare(Lock.Pam.waiting, true);
            compare(Lock.Shared.shown, false);
            keyClick(Qt.Key_Return);              // the key that wakes the screen
            compare(authenticator.answers, [], "an empty answer counts as a refusal: not sent unseen");
            compare(Lock.Shared.shown, true);
            keyClick(Qt.Key_Return);              // at the box that is up, it is the person's answer
            compare(authenticator.answers, [""]);
        }

        function test_15_a_question_whose_answer_shows_clears_a_password_typed_before_it() {
            keyClick(Qt.Key_S);
            keyClick(Qt.Key_E);
            compare(find(left, "password").text, "se");
            authenticator.prompt = "Touch the key, then press Enter";
            authenticator.promptChanged();
            compare(find(left, "password").echoMode, TextInput.Normal);
            compare(find(left, "password").text, "", "never a password in clear");
            compare(find(right, "password").text, "");
        }

        function test_16_empty_words_are_no_question() {
            authenticator.promptForSecret = "";
            authenticator.promptForSecretChanged();   // a conversation's end clears the words
            authenticator.promptChanged();
            compare(Lock.Pam.waiting, false);
            compare(Lock.Pam.secret, true);
        }

        function test_17_a_new_engine_meets_pam_where_it_is() {
            // a screen back while PAM checks an answer: nothing is open, nothing is sent
            authenticator.busy = true;
            authenticator.asks = false;           // kscreenlocker ignores a start while one is under way
            Lock.Pam.attach(authenticator);
            compare(Lock.Pam.waiting, false);
            compare(Lock.Pam.conversing, true);
            keyClick(Qt.Key_A);
            keyClick(Qt.Key_Return);
            compare(authenticator.answers, [], "kept, not queued for whatever PAM asks next");
            authenticator.promptForSecret = "Verificatiecode: ";
            authenticator.promptForSecretChanged();   // the second factor
            compare(authenticator.answers, [], "a second factor never gets the password");
            compare(Lock.Pam.message, "Verificatiecode: ", "and is said");
            // a screen back with a question open: it is answered, and its words are shown
            init();
            authenticator.promptForSecret = "Verificatiecode: ";
            Lock.Pam.attach(authenticator);
            compare(Lock.Pam.waiting, true);
            compare(Lock.Pam.message, "Verificatiecode: ");
            // a screen back just after a refusal: PAM is not started inside its delay
            init();
            authenticator.state = 0;
            Lock.Pam.attach(authenticator);
            compare(Lock.Pam.waiting, false);
            compare(Lock.Pam.retry.running, true);
            Lock.Pam.retry.stop();
        }

        function test_18_several_layouts_name_the_one_in_use_and_switch_on_every_screen() {
            const one = find(left, "layout");
            verify(one && !one.visible, "one layout: nothing to say");
            Keyboards.LayoutState.layouts = [{ shortName: "us", displayName: "", longName: "English (US)" },
                                             { shortName: "de", displayName: "", longName: "German" }];
            keyClick(Qt.Key_A);
            tryCompare(find(left, "layout"), "visible", true);
            compare(find(left, "layout").contentItem.text, "\u2328 English (US)");
            mouseClick(find(right, "layout"));
            tryCompare(find(left, "layout").contentItem, "text", "\u2328 German");
            compare(find(right, "layout").contentItem.text, "\u2328 German");
            compare(find(left, "password").text, "a", "what was typed stays");
            Keyboards.LayoutState.layouts = [];                 // KWin's list gone for a moment
            tryCompare(find(left, "layout"), "visible", false);
        }

        function test_19_the_rain_rests_while_nobody_is_there() {
            Lock.Shared.restMs = 200;
            Lock.Shared.wake();
            compare(Lock.Shared.fps, 30);
            tryCompare(Lock.Shared, "resting", true, 3000);
            compare(Lock.Shared.fps, 10);
            keyClick(Qt.Key_B);
            compare(Lock.Shared.resting, false, "a key brings the full rate back");
            compare(Lock.Shared.fps, 30);
            tryCompare(Lock.Shared, "resting", true, 3000);
            keyClick(Qt.Key_Escape);
            compare(Lock.Shared.resting, false, "Escape is a key too");
        }
    }
}
