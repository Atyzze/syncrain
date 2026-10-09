#!/bin/sh
# Build the native wallpaper: build.sh OUTPUT [extra compiler arguments...]
#
# Needs a C compiler, pkg-config, wayland-scanner, and the headers of libwayland-client,
# libwayland-egl and libdbus-1 (on Arch all of them come with gcc, pkgconf, wayland and dbus).
# EGL and OpenGL are opened at run time, so their headers are not needed. CC and CFLAGS are
# honoured; SYNCRAIN_LIBEGL names the EGL library to open when it is not on the library path (Nix).
set -eu

here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
out=${1:?usage: build.sh OUTPUT [compiler arguments...]}
shift

scanner=$(pkg-config --variable=wayland_scanner wayland-scanner 2>/dev/null || true)
[ -x "$scanner" ] || scanner=$(command -v wayland-scanner || true)
[ -n "$scanner" ] || { echo "build.sh: wayland-scanner not found" >&2; exit 1; }

work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
for xml in "$here"/protocols/*.xml; do
	name=$(basename "$xml" .xml)
	"$scanner" client-header "$xml" "$work/$name.h"
	"$scanner" private-code "$xml" "$work/$name.c"
done

libs=$(pkg-config --cflags --libs wayland-client wayland-egl dbus-1)
[ -z "${SYNCRAIN_LIBEGL:-}" ] || set -- "-DSYNCRAIN_LIBEGL=\"$SYNCRAIN_LIBEGL\"" "$@"

mkdir -p "$(dirname -- "$out")"
# shellcheck disable=SC2086 # the pkg-config output and CFLAGS are lists of words
${CC:-cc} -std=c11 ${CFLAGS:--O2} -Wall -Wextra -Wno-unused-parameter -I"$work" -I"$here" \
	"$here"/*.c "$work"/*.c $libs -ldl -lm -o "$out.tmp" "$@"
mv -f -- "$out.tmp" "$out"
