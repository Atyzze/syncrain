/*
    The keyboard layout in use, from Plasma's own keyboard layout module (as Plasma's lock screen
    shows it), named only when there is more than one to choose from: a password typed in another
    layout than the one thought is the commonest wrong one. In a file of its own: where that module
    is missing, the box just does not say it.
*/
import QtQuick
import org.kde.plasma.workspace.keyboardlayout as Keyboards

Keyboards.KeyboardLayout {
    readonly property string name: layoutsList.length > 1 && layout < layoutsList.length ? layoutsList[layout].longName : ""
}
