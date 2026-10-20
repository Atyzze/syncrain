/*
    What every screen's box shows, one for all of them (a singleton, as Pam.qml is): what is typed,
    whether the password is shown, and whether the box is up at all. Typed on one screen, the same
    dots are on every screen, so it never matters which one is looked at.

    The box comes up on a key or a moved pointer and goes after a minute without either, on Escape
    and before a suspend; going, it forgets what was typed, sent or not (a half-typed password does
    not wait on the screen, nor get tried later). The rain stays, at its full rate for as long as the
    screen is locked: a lock screen is watched (and recorded) without a key being touched. Only when
    the settings file asks for a rest (`lock_rest`, seconds; Rain.qml sets restMs from the scene)
    does it draw 10 frames a second after that long without a key or a move, and 30 again at the next.
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
    property int restMs: 0                   // 0: never rests (the default)
    readonly property real fps: resting ? 10 : 30

    function wake() {
        shared.shown = true;
        shared.resting = false;
        idle.restart();
        if (shared.restMs > 0)
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

    // from the lock on (or from when the rest is set), as from every key or move after it
    property Timer rest: Timer {
        interval: Math.max(1, shared.restMs)
        running: shared.restMs > 0
        onTriggered: shared.resting = true
    }
    onRestMsChanged: {
        shared.resting = false;
        if (shared.restMs > 0)
            rest.restart();
    }
}
