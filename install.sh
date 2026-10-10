#!/usr/bin/env bash
# syncrain installer for Arch-based systems (Arch, CachyOS, EndeavourOS, Manjaro, Garuda, ...)
#
#   ./install.sh                     install this build for your user (asks for sudo once, for pacman packages)
#   ./install.sh --autostart         ...and start it with every graphical login
#   ./install.sh --plasma            ...or, on KDE Plasma, as the desktop's and the lock screen's wallpaper
#   ./install.sh --theme matrix --channel friends --autostart
#   ./install.sh --uninstall         remove it again (pacman packages are left installed)
#
# Run from a newer build's folder, it upgrades in place and restarts a running wallpaper.
# Everything goes into your home directory:
#   ~/.local/share/syncrain/                 the app (plus web/index.html, the browser version)
#   ~/.local/bin/syncrain                    the launcher
#   ~/.config/systemd/user/syncrain.service  only with --autostart
#   ~/.local/share/plasma/wallpapers/org.syncrain.wallpaper/ and, with sudo, <Qt's QML folder>/org/syncrain/
#                                            only with --plasma
set -euo pipefail

PACKAGES=(python python-gobject python-cairo python-pillow gtk4 gtk4-layer-shell)
# what the native wallpaper is built with (syncrain/native/build.sh); wayland and dbus are on every Plasma desktop
BUILD_PACKAGES=(gcc pkgconf wayland dbus)
# and the Plasma wallpaper (syncrain/plasma/); Plasma itself brings the Qt ones
PLASMA_PACKAGES=(cmake make qt6-base qt6-declarative)
PREFIX="${PREFIX:-$HOME/.local}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART=0 PLASMA=0 UNINSTALL=0 NODEPS=0 YES=0
THEME="" CHANNEL="" RAINBOW="" EXTRA=()

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  cat <<'EOF'

Options:
  --autostart           start with every graphical login (systemd user service)
  --plasma              KDE Plasma: the wallpaper of every desktop and of the lock screen, drawn
                        by Plasma itself (behind the icons); its settings are in Desktop and Wallpaper
  --theme NAME          nixos (default) or matrix
  --channel NAME        stream name (default: public)
  --rainbow MODE        logo (default), all or off
  --arg ARG             extra argument for syncrain, repeatable (e.g. --arg --fps --arg 24)
  --prefix DIR          install under DIR instead of ~/.local
  --no-deps             skip the pacman step
  --yes                 do not ask pacman for confirmation
  --uninstall           remove syncrain
  -h, --help            this help
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --autostart) AUTOSTART=1 ;;
    --plasma) PLASMA=1 ;;
    --theme) THEME="${2:?--theme needs a value}"; shift ;;
    --channel) CHANNEL="${2:?--channel needs a value}"; shift ;;
    --rainbow) RAINBOW="${2:?--rainbow needs a value}"; shift ;;
    --arg) EXTRA+=("${2:?--arg needs a value}"); shift ;;
    --prefix) PREFIX="${2:?--prefix needs a value}"; shift ;;
    --no-deps) NODEPS=1 ;;
    --yes|-y) YES=1 ;;
    --uninstall) UNINSTALL=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
  shift
done

APPDIR="$PREFIX/share/syncrain"
BINDIR="$PREFIX/bin"
UNITDIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT="$UNITDIR/syncrain.service"
have_user_systemd() { command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; }
SUDO=(); [ "$(id -u)" != 0 ] && SUDO=(sudo)
WALLPAPER=org.syncrain.wallpaper
PLASMA_PACKAGE="${XDG_DATA_HOME:-$HOME/.local/share}/plasma/wallpapers/$WALLPAPER"
SCENES="${XDG_CACHE_HOME:-$HOME/.cache}/syncrain"
qml_dir() { local d; d="$(qtpaths6 --query QT_INSTALL_QML 2>/dev/null || true)"; printf '%s' "${d:-/usr/lib/qt6/qml}"; }
# Plasma's scripting: every desktop's wallpaper (plasmashell has to be running)
plasma_script() {
  command -v dbus-send >/dev/null &&
    dbus-send --session --print-reply --dest=org.kde.plasmashell /PlasmaShell \
      org.kde.PlasmaShell.evaluateScript "string:$1" >/dev/null 2>&1
}

if [ "$UNINSTALL" = 1 ]; then
  bold "Removing syncrain"
  if [ -f "$UNIT" ]; then
    if have_user_systemd; then systemctl --user disable --now syncrain.service >/dev/null 2>&1 || true; fi
    rm -f "$UNIT"
    if have_user_systemd; then systemctl --user daemon-reload || true; fi
    info "removed the autostart service"
  fi
  if [ -d "$PLASMA_PACKAGE" ]; then
    plasma_script "desktops().forEach(d => { if (d.wallpaperPlugin === '$WALLPAPER') d.wallpaperPlugin = 'org.kde.image'; });" &&
      info "Plasma's desktops are back on their image wallpaper"
    if [ "$(kreadconfig6 --file kscreenlockerrc --group Greeter --key WallpaperPlugin 2>/dev/null || true)" = "$WALLPAPER" ]; then
      kwriteconfig6 --file kscreenlockerrc --group Greeter --key WallpaperPlugin --delete && info "the lock screen is back on its default wallpaper"
    fi
    rm -rf "$PLASMA_PACKAGE" "$SCENES"
    info "removed the Plasma wallpaper package"
  fi
  if [ -d "$(qml_dir)/org/syncrain" ]; then
    "${SUDO[@]}" rm -rf "$(qml_dir)/org/syncrain" && info "removed $(qml_dir)/org/syncrain"
  fi
  rm -rf "$APPDIR" "$BINDIR/syncrain"
  info "removed $APPDIR and $BINDIR/syncrain"
  info "pacman packages were left installed: ${PACKAGES[*]} ${BUILD_PACKAGES[*]}"
  exit 0
fi

[ -f "$SRC/syncrain/app.py" ] || die "run this script from the syncrain folder (it needs syncrain/app.py next to it)"
[ -f "$SRC/BUILD_NUMBER" ] || die "this folder has no BUILD_NUMBER, so it is not a syncrain release; use the folder unpacked from SYNCRAIN<N>.tar.zst"
BUILD="$(tr -d '[:space:]' < "$SRC/BUILD_NUMBER")"
[ "$(id -u)" = 0 ] && printf '\033[33mnote:\033[0m running as root installs syncrain for root only; normally run it as your user.\n'

# ---- 1. system packages
if [ "$NODEPS" = 0 ]; then
  command -v pacman >/dev/null || die "pacman not found: this script is for Arch-based systems (use --no-deps if you installed the dependencies yourself: ${PACKAGES[*]} ${BUILD_PACKAGES[*]})"
  missing=()
  wanted=("${PACKAGES[@]}" "${BUILD_PACKAGES[@]}")
  [ "$PLASMA" = 1 ] && wanted+=("${PLASMA_PACKAGES[@]}")
  for p in "${wanted[@]}"; do pacman -Qq "$p" >/dev/null 2>&1 || missing+=("$p"); done
  if [ ${#missing[@]} -gt 0 ]; then
    bold "Installing packages: ${missing[*]}"
    confirm=(); [ "$YES" = 1 ] && confirm=(--noconfirm)
    if ! "${SUDO[@]}" pacman -S --needed "${confirm[@]}" "${missing[@]}"; then
      die "pacman could not install the packages. If it reported missing files (404), update first with 'sudo pacman -Syu' and run this again."
    fi
  else
    bold "All packages are already installed"
  fi
fi

# ---- 2. sanity check: the Python bindings load
python3 - <<'EOF' || die "the Python dependencies did not load (see above)"
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: F401
import ctypes
ctypes.CDLL("libepoxy.so.0")  # GTK's OpenGL loader, which syncrain calls OpenGL through
import PIL  # noqa: F401
import cairo  # noqa: F401
try:
    gi.require_version("Gtk4LayerShell", "1.0")
except ValueError:
    print("  note: gtk4-layer-shell is missing, so on Wayland only the native wallpaper can draw; "
          "the GTK host runs on X11 or with --window")
EOF

# ---- 3. the app
if [ -f "$APPDIR/BUILD_NUMBER" ]; then
  OLD="$(tr -d '[:space:]' < "$APPDIR/BUILD_NUMBER")"
  if [ "$OLD" = "$BUILD" ]; then bold "Reinstalling syncrain build $BUILD into $APPDIR"
  else bold "Upgrading syncrain from build $OLD to build $BUILD in $APPDIR"; fi
elif [ -d "$APPDIR" ]; then
  bold "Replacing an earlier syncrain (from before build numbers) with build $BUILD in $APPDIR"
else
  bold "Installing syncrain build $BUILD into $APPDIR"
fi
rm -rf "$APPDIR"
mkdir -p "$APPDIR" "$BINDIR"
cp -r "$SRC/syncrain" "$APPDIR/"
find "$APPDIR" -name '__pycache__' -type d -prune -exec rm -rf {} +
for f in BUILD_NUMBER README.md LICENSE; do [ -f "$SRC/$f" ] && cp "$SRC/$f" "$APPDIR/"; done
if [ -f "$SRC/web/index.html" ]; then mkdir -p "$APPDIR/web" && cp "$SRC/web/index.html" "$APPDIR/web/"; fi

# The native wallpaper (syncrain/native/) draws on Wayland with neither Python nor GTK in memory.
# Without it, the Python and GTK host draws the same frames, as before.
NATIVE="$APPDIR/syncrain/native/syncrain-wallpaper"
if log="$(sh "$APPDIR/syncrain/native/build.sh" "$NATIVE" 2>&1)"; then
  info "native wallpaper: built"
else
  printf '\033[33mnote:\033[0m the native wallpaper did not build, so the Python and GTK host draws instead (it is built with: %s):\n' "${BUILD_PACKAGES[*]}"
  printf '%s\n' "$log" | tail -n 6 | sed 's/^/    /'
fi

cat > "$BINDIR/syncrain" <<EOF
#!/bin/sh
# syncrain launcher, written by install.sh
APPDIR="$APPDIR"
# gtk4-layer-shell has to be loaded before libwayland-client
for lib in /usr/lib/libgtk4-layer-shell.so.0 /usr/lib/libgtk4-layer-shell.so; do
  if [ -e "\$lib" ]; then
    case " \${LD_PRELOAD:-} " in
      *gtk4-layer-shell*) ;;
      *) LD_PRELOAD="\$lib\${LD_PRELOAD:+ \$LD_PRELOAD}"; export LD_PRELOAD ;;
    esac
    break
  fi
done
PYTHONPATH="\$APPDIR\${PYTHONPATH:+:\$PYTHONPATH}"; export PYTHONPATH
# python -m puts the current directory first on the module path; without this, running syncrain
# from inside an unpacked release folder starts that folder's copy instead of the installed one
PYTHONSAFEPATH=1; export PYTHONSAFEPATH
exec "\${SYNCRAIN_PYTHON:-python3}" -m syncrain "\$@"
EOF
chmod +x "$BINDIR/syncrain"
"$BINDIR/syncrain" --build >/dev/null || die "the launcher does not run"
info "launcher: $BINDIR/syncrain ($("$BINDIR/syncrain" --build))"

# ---- 4. autostart
ARGS=()
[ -n "$THEME" ] && ARGS+=(--theme "$THEME")
[ -n "$CHANNEL" ] && ARGS+=(--channel "$CHANNEL")
[ -n "$RAINBOW" ] && ARGS+=(--rainbow "$RAINBOW")
ARGS+=("${EXTRA[@]}")
# Shell words, for the compositor hints below.
quote() { local out="" a; for a in "$@"; do out+=" '${a//\'/\'\\\'\'}'"; done; printf '%s' "$out"; }
# Words for a systemd ExecStart line. systemd splits like a shell but reads backslashes as escapes
# even inside single quotes, expands %-specifiers before splitting and $VARIABLES after it, so each
# word gets its backslashes doubled, its % and $ doubled, then single quotes.
unit_words() {
  local out="" a
  for a in "$@"; do
    a="${a//\\/\\\\}"; a="${a//%/%%}"; a="${a//\$/\$\$}"
    out+=" '${a//\'/\'\\\'\'}'"
  done
  printf '%s' "${out# }"
}

if [ "$PLASMA" = 1 ] && [ "$AUTOSTART" = 1 ]; then
  info "note: --plasma draws the wallpaper inside Plasma, so --autostart is left out"
  AUTOSTART=0
fi

if [ "$AUTOSTART" = 1 ]; then
  bold "Setting up autostart"
  mkdir -p "$UNITDIR"
  cat > "$UNIT" <<EOF
[Unit]
Description=syncrain live wallpaper
PartOf=graphical-session.target
After=graphical-session.target

[Service]
ExecStart=$(unit_words "$BINDIR/syncrain" "${ARGS[@]}")
Restart=on-failure
RestartSec=3
# exit status 69 means no OpenGL here; restarting would only cover the desktop again (syncrain --diagnose says why)
RestartPreventExitStatus=69

[Install]
WantedBy=graphical-session.target
EOF
  if have_user_systemd; then
    systemctl --user daemon-reload
    systemctl --user enable syncrain.service >/dev/null 2>&1 && info "enabled: starts with your next graphical login"
    if systemctl --user is-active --quiet graphical-session.target; then
      systemctl --user restart syncrain.service && info "started now"
    fi
  else
    info "wrote $UNIT; enable it from your desktop session with: systemctl --user enable --now syncrain.service"
  fi
elif [ -f "$UNIT" ] && have_user_systemd && systemctl --user is-active --quiet syncrain.service; then
  systemctl --user restart syncrain.service && info "restarted the running wallpaper on build $BUILD"
fi

# ---- 5. the Plasma wallpaper
if [ "$PLASMA" = 1 ]; then
  bold "Installing the Plasma wallpaper"
  work="$(mktemp -d)"
  trap 'rm -rf "$work"' EXIT
  if ! log="$(cmake -S "$APPDIR/syncrain/plasma" -B "$work" -DCMAKE_BUILD_TYPE=Release \
                -DSYNCRAIN_COMMAND="$BINDIR/syncrain" 2>&1 && cmake --build "$work" -j "$(nproc)" 2>&1)"; then
    printf '%s\n' "$log" | tail -n 12 | sed 's/^/    /'
    die "the Plasma wallpaper did not build (it needs: ${PLASMA_PACKAGES[*]} pkgconf dbus)"
  fi
  module="$(qml_dir)/org/syncrain"
  upgrade=0; [ -d "$module" ] && upgrade=1
  # Qt's own QML folder, so plasmashell and the lock screen find it without any setting
  "${SUDO[@]}" install -d "$module"
  "${SUDO[@]}" install -m 644 "$work"/qml/org/syncrain/qmldir "$work"/qml/org/syncrain/*.qmltypes "$module/"
  "${SUDO[@]}" install -m 755 "$work"/qml/org/syncrain/*.so "$module/"
  info "QML module: $module"
  rm -rf "$PLASMA_PACKAGE" "$SCENES"
  mkdir -p "$(dirname "$PLASMA_PACKAGE")"
  cp -r "$APPDIR/syncrain/plasma/package" "$PLASMA_PACKAGE"
  info "wallpaper: $PLASMA_PACKAGE"
  # the service would draw a second wallpaper on top of Plasma's
  if [ -f "$UNIT" ] && have_user_systemd; then
    systemctl --user disable --now syncrain.service >/dev/null 2>&1 && info "the autostart service is off now: Plasma draws syncrain"
  fi
  # the installer's options become the wallpaper's settings
  settings=()
  [ -n "$THEME" ] && settings+=(Theme "$THEME")
  [ -n "$CHANNEL" ] && settings+=(Channel "$CHANNEL")
  [ -n "$RAINBOW" ] && settings+=(Rainbow "$RAINBOW")
  [ ${#EXTRA[@]} -gt 0 ] && settings+=(ExtraArgs "${EXTRA[*]}")
  script="$(python3 - "$WALLPAPER" "${settings[@]}" <<'PY'
import json, sys
plugin, pairs = sys.argv[1], sys.argv[2:]
settings = dict(zip(pairs[::2], pairs[1::2]))
print("const settings = %s; desktops().forEach(d => { d.wallpaperPlugin = %s; "
      "d.currentConfigGroup = ['Wallpaper', %s, 'General']; "
      "for (const k in settings) d.writeConfig(k, settings[k]); d.reloadConfig(); });"
      % (json.dumps(settings), json.dumps(plugin), json.dumps(plugin)))
PY
)"
  if plasma_script "$script"; then
    info "now the wallpaper of every desktop (Desktop and Wallpaper has its settings)"
  else
    info "Plasma's shell did not answer: choose \"syncrain\" in Desktop and Wallpaper"
  fi
  if command -v kwriteconfig6 >/dev/null; then
    kwriteconfig6 --file kscreenlockerrc --group Greeter --key WallpaperPlugin "$WALLPAPER"
    for ((i = 0; i < ${#settings[@]}; i += 2)); do
      kwriteconfig6 --file kscreenlockerrc --group Greeter --group Wallpaper --group "$WALLPAPER" --group General \
        --key "${settings[i]}" "${settings[i + 1]}"
    done
    info "and of the lock screen (Screen Locking, Appearance)"
  fi
  if [ "$upgrade" = 1 ] && have_user_systemd && systemctl --user is-active --quiet plasma-plasmashell.service; then
    systemctl --user restart plasma-plasmashell.service && info "restarted Plasma's shell, so it draws with build $BUILD"
  fi
fi

# ---- 6. what next
desktop="${XDG_CURRENT_DESKTOP:-}"
echo
if [ "$PLASMA" = 1 ]; then
  bold "Done: Plasma draws syncrain now. More:"
else
  bold "Done. Try it:"
fi
info "syncrain --window        preview in a normal window"
[ "$PLASMA" = 1 ] || info "syncrain                 run as your wallpaper (Ctrl+C stops it)"
info "syncrain --theme matrix  the green theme; see --help for all options"
info "syncrain --diagnose      if it does not draw: what this machine offers, and why"
case ":$PATH:" in *":$BINDIR:"*) ;; *) info "note: $BINDIR is not on your PATH; run $BINDIR/syncrain or add it to PATH" ;; esac
case "$desktop" in
  *KDE*) [ "$PLASMA" = 1 ] || info "KDE Plasma: ./install.sh --plasma makes syncrain the wallpaper of every desktop and the lock screen, behind the icons." ;;
  *Hyprland*) [ "$AUTOSTART" = 1 ] && info "Hyprland: if it doesn't start at login, add 'exec-once = $BINDIR/syncrain$(quote "${ARGS[@]}")' to hyprland.conf (or log in through UWSM)." ;;
  *sway*|*Sway*) [ "$AUTOSTART" = 1 ] && info "Sway: if it doesn't start at login, add 'exec $BINDIR/syncrain$(quote "${ARGS[@]}")' to your sway config." ;;
  *GNOME*) info "GNOME has no wallpaper layer for apps; use 'syncrain --window' or open $APPDIR/web/index.html in a browser." ;;
esac
info "uninstall: ./install.sh --uninstall"
