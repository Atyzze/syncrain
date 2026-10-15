/*
    Before the machine sleeps, the box goes and forgets what was typed (as Plasma's own lock screen
    clears its field): the idle minute does not count while suspended. Plasma's session management
    says when; in a file of its own, so the lock screen loads where that module is missing.
*/
import QtQuick
import org.kde.plasma.private.sessions

SessionManagement {
    onAboutToSuspend: Shared.sleep()
}
