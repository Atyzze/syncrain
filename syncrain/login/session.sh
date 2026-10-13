#!/bin/sh
# Inside the login screen's KWin (login.sh starts it): the rain and the login box.
# Without portals and the accessibility bus GTK is up seconds sooner (nothing here uses them).
export GDK_DEBUG="${GDK_DEBUG:-no-portals}" GTK_A11Y="${GTK_A11Y:-none}"
exec "${SYNCRAIN_PYTHON:-python3}" -m syncrain.greeter
