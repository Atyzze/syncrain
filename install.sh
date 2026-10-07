#!/usr/bin/env bash
# syncrain installer for Arch-based systems (Arch, CachyOS, EndeavourOS, Manjaro, Garuda, ...)
#
#   ./install.sh                     install this build for your user (asks for sudo once, for pacman packages)
#   ./install.sh --autostart         ...and start it with every graphical login
#   ./install.sh --theme matrix --channel friends --autostart
#   ./install.sh --uninstall         remove it again (pacman packages are left installed)
#
# Run from a newer build's folder, it upgrades in place and restarts a running wallpaper.
# Everything goes into your home directory:
#   ~/.local/share/syncrain/                 the app (plus web/index.html, the browser version)
#   ~/.local/bin/syncrain                    the launcher
#   ~/.config/systemd/user/syncrain.service  only with --autostart
set -euo pipefail

PACKAGES=(python python-gobject python-cairo python-opengl python-pillow gtk4 gtk4-layer-shell)
PREFIX="${PREFIX:-$HOME/.local}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART=0 UNINSTALL=0 NODEPS=0 YES=0
THEME="" CHANNEL="" RAINBOW="" EXTRA=()

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  cat <<'EOF'

Options:
  --autostart           start with every graphical login (systemd user service)
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

if [ "$UNINSTALL" = 1 ]; then
  bold "Removing syncrain"
  if [ -f "$UNIT" ]; then
    if have_user_systemd; then systemctl --user disable --now syncrain.service >/dev/null 2>&1 || true; fi
    rm -f "$UNIT"
    if have_user_systemd; then systemctl --user daemon-reload || true; fi
    info "removed the autostart service"
  fi
  rm -rf "$APPDIR" "$BINDIR/syncrain"
  info "removed $APPDIR and $BINDIR/syncrain"
  info "pacman packages were left installed: ${PACKAGES[*]}"
  exit 0
fi

[ -f "$SRC/syncrain/app.py" ] || die "run this script from the syncrain folder (it needs syncrain/app.py next to it)"
[ -f "$SRC/BUILD_NUMBER" ] || die "this folder has no BUILD_NUMBER, so it is not a syncrain release; use the folder unpacked from SYNCRAIN<N>.tar.zst"
BUILD="$(tr -d '[:space:]' < "$SRC/BUILD_NUMBER")"
[ "$(id -u)" = 0 ] && printf '\033[33mnote:\033[0m running as root installs syncrain for root only; normally run it as your user.\n'

# ---- 1. system packages
if [ "$NODEPS" = 0 ]; then
  command -v pacman >/dev/null || die "pacman not found: this script is for Arch-based systems (use --no-deps if you installed the dependencies yourself: ${PACKAGES[*]})"
  missing=()
  for p in "${PACKAGES[@]}"; do pacman -Qq "$p" >/dev/null 2>&1 || missing+=("$p"); done
  if [ ${#missing[@]} -gt 0 ]; then
    bold "Installing packages: ${missing[*]}"
    confirm=(); [ "$YES" = 1 ] && confirm=(--noconfirm)
    SUDO=(); [ "$(id -u)" != 0 ] && SUDO=(sudo)
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
import OpenGL.GL  # noqa: F401
import PIL  # noqa: F401
import cairo  # noqa: F401
try:
    gi.require_version("Gtk4LayerShell", "1.0")
except ValueError:
    print("  note: gtk4-layer-shell is missing, so syncrain only runs on X11 or in --window mode")
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

# ---- 5. what next
desktop="${XDG_CURRENT_DESKTOP:-}"
echo
bold "Done. Try it:"
info "syncrain --window        preview in a normal window"
info "syncrain                 run as your wallpaper (Ctrl+C stops it)"
info "syncrain --theme matrix  the green theme; see --help for all options"
info "syncrain --diagnose      if it does not draw: what this machine offers, and why"
case ":$PATH:" in *":$BINDIR:"*) ;; *) info "note: $BINDIR is not on your PATH; run $BINDIR/syncrain or add it to PATH" ;; esac
case "$desktop" in
  *KDE*) info "KDE Plasma: syncrain sits just above Plasma's desktop, so desktop icons and widgets are hidden behind it (clicks still reach the desktop)."
         info "To keep the icons, show $APPDIR/web/index.html?hud=0 with a Plasma wallpaper plugin for web pages instead." ;;
  *Hyprland*) [ "$AUTOSTART" = 1 ] && info "Hyprland: if it doesn't start at login, add 'exec-once = $BINDIR/syncrain$(quote "${ARGS[@]}")' to hyprland.conf (or log in through UWSM)." ;;
  *sway*|*Sway*) [ "$AUTOSTART" = 1 ] && info "Sway: if it doesn't start at login, add 'exec $BINDIR/syncrain$(quote "${ARGS[@]}")' to your sway config." ;;
  *GNOME*) info "GNOME has no wallpaper layer for apps; use 'syncrain --window' or open $APPDIR/web/index.html in a browser." ;;
esac
info "uninstall: ./install.sh --uninstall"
