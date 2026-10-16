/*
    What every screen's box shows, one for all of them (a singleton, as Pam.qml is): what is typed,
    whether the password is shown, and whether the box is up at all. Typed on one screen, the same
    dots are on every screen, so it never matters which one is looked at.

    The box comes up on a key or a moved pointer and goes after a minute without either, on Escape
    and before a suspend; going, it forgets what was typed, sent or not (a half-typed password does
    not wait on the screen, nor get tried later). The rain stays, and after five minutes without
    either it rests: fewer frames a second, for a lock screen nobody is looking at (each frame costs
    power, and on NVIDIA memory in KWin's greeter); a key or a move brings the full rate back.
*/
pragma Singleton

import QtQuick

QtObject {
    id: shared

    property string typed: ""
    property bool peek: false
    property bool shown: false
    property int idleMs: 60000               // tests make it shorter
    property bool resting: false
    property int restMs: 300000
    readonly property real fps: resting ? 10 : 30

    function wake() {
        shared.shown = true;
        shared.resting = false;
        idle.restart();
        rest.restart();
    }

    function sleep() {
        idle.stop();
        shared.shown = false;
        shared.typed = "";
        shared.peek = false;
        Pam.forget();
    }

    property Timer idle: Timer {
        interval: shared.idleMs
        onTriggered: shared.sleep()
    }

    // from the lock on, as from every key or move after it
    property Timer rest: Timer {
        interval: shared.restMs
        running: true
        onTriggered: shared.resting = true
    }
}
