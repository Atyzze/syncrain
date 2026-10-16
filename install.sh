#!/usr/bin/env bash
# syncrain installer for four families of Linux: Arch (CachyOS, EndeavourOS, Manjaro, Garuda),
# Debian (Ubuntu, Mint, Pop!_OS), Fedora and openSUSE. Elsewhere: --no-deps, with the packages it names.
#
#   ./install.sh                     install this build for your user (asks for sudo once, for the system's packages)
#   ./install.sh --autostart         ...and start it with every graphical login
#   ./install.sh --preset matrix --channel friends --autostart
#   ./install.sh --config config.json  ...and draw what the web page showed (the settings it exported)
#   ./install.sh --login-screen      ...and the rain as your login screen too (optional; greetd, yours stays installed)
#   ./install.sh --login-screen-off  back to the login screen you had (undoes only what --login-screen did)
#   ./install.sh --lock-screen       ...and the rain with syncrain's box as KDE Plasma's lock screen (optional)
#   ./install.sh --lock-screen-off   back to Plasma's own lock screen (undoes only what --lock-screen did)
#   ./install.sh --uninstall         remove it again (the system's packages are left installed)
#
# Run from a newer build's folder, it upgrades in place and restarts a running wallpaper.
# Everything goes into your home directory (only --login-screen writes outside it: /usr/local/lib/syncrain,
# /var/lib/syncrain-login, greetd's config and PAM files):
#   ~/.local/share/syncrain/                 the app (plus index.html, the browser version)
#   ~/.local/bin/syncrain                    the launcher
#   ~/.config/systemd/user/syncrain.service  only with --autostart
#   ~/.local/share/plasma/shells/org.syncrain.lockscreen/, ~/.local/lib/syncrain/  only with --lock-screen
set -euo pipefail

# The system's packages, by family (detect_family below). PACKAGES: Python, GTK 4 and their
# introspection data. LAYER_PACKAGES: gtk4-layer-shell, which only the GTK host needs on Wayland (the
# native wallpaper speaks layer-shell itself), so a release without it (Ubuntu 24.04, openSUSE Leap
# 16.0) still installs. BUILD_PACKAGES: what the native wallpaper is built with
# (syncrain/native/build.sh). LOCK_PACKAGES: the lock screen's QML module (syncrain/lockscreen/),
# only with --lock-screen. LOGIN_PACKAGES: greetd and its text login, only with --login-screen.
set_packages() {
  case "$1" in
    arch)
      PACKAGES=(python python-gobject python-cairo python-pillow gtk4)
      LAYER_PACKAGES=(gtk4-layer-shell)
      BUILD_PACKAGES=(gcc pkgconf wayland dbus)
      LOCK_PACKAGES=(cmake make qt6-base qt6-declarative)
      LOGIN_PACKAGES=(greetd greetd-agreety) ;;
    debian)
      PACKAGES=(python3 python3-gi python3-gi-cairo python3-cairo python3-pil gir1.2-gtk-4.0)
      LAYER_PACKAGES=(libgtk4-layer-shell0 gir1.2-gtk4layershell-1.0)   # the typelib does not bring the library
      BUILD_PACKAGES=(gcc libc6-dev pkgconf libwayland-dev libdbus-1-dev)   # gcc only recommends libc6-dev
      LOCK_PACKAGES=(cmake make g++ qt6-base-dev qt6-declarative-dev)
      LOGIN_PACKAGES=(greetd) ;;
    fedora)
      PACKAGES=(python3 python3-gobject python3-cairo python3-pillow gtk4)
      LAYER_PACKAGES=(gtk4-layer-shell)
      BUILD_PACKAGES=(gcc pkgconf-pkg-config wayland-devel dbus-devel)
      LOCK_PACKAGES=(cmake make gcc-c++ qt6-qtbase-devel qt6-qtdeclarative-devel)
      LOGIN_PACKAGES=(greetd) ;;
    suse)
      PACKAGES=(python3 python3-gobject python3-gobject-cairo python3-cairo python3-Pillow typelib-1_0-Gtk-4_0)
      LAYER_PACKAGES=(typelib-1_0-Gtk4LayerShell-1_0)
      BUILD_PACKAGES=(gcc pkgconf-pkg-config wayland-devel dbus-1-devel)
      LOCK_PACKAGES=(cmake make gcc-c++ qt6-base-devel qt6-declarative-devel)
      LOGIN_PACKAGES=(greetd greetd-agreety) ;;
    *)  # named for the message only: what to install by hand, by what it is
      PACKAGES=(python3 PyGObject pycairo Pillow "GTK 4 and its typelib")
      LAYER_PACKAGES=("gtk4-layer-shell and its typelib")
      BUILD_PACKAGES=(gcc pkg-config wayland-scanner "wayland and dbus headers")
      LOCK_PACKAGES=(cmake "Qt 6.5+ base and declarative headers")
      LOGIN_PACKAGES=("greetd and agreety") ;;
  esac
}
# SYNCRAIN_PREFIX, not PREFIX: a PREFIX left in the environment by a build of something else would
# move the install without anyone asking
PREFIX="${SYNCRAIN_PREFIX:-$HOME/.local}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART=0 UNINSTALL=0 NODEPS=0 YES=0 LOGIN=0 LOGIN_OFF=0 LOCK=0 LOCK_OFF=0
THEME="" CHANNEL="" RAINBOW="" CONFIG="" EXTRA=()

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# The family of Linux, from os-release (ID, then the words of ID_LIKE), else from the package manager
# there is: arch, debian, fedora, suse, or unknown. SYNCRAIN_FAMILY overrides it.
OS_RELEASE="${SYNCRAIN_OS_RELEASE:-/etc/os-release}"
detect_family() {
  if [ -n "${SYNCRAIN_FAMILY:-}" ]; then printf '%s\n' "$SYNCRAIN_FAMILY"; return; fi
  local words="" w
  if [ -r "$OS_RELEASE" ]; then
    # shellcheck disable=SC1090 # the system's own description, read in a subshell
    words="$( . "$OS_RELEASE" >/dev/null 2>&1; printf '%s %s' "${ID:-}" "${ID_LIKE:-}" )" || words=""
  fi
  for w in $words; do
    case "$w" in
      arch|archarm|cachyos|endeavouros|manjaro|garuda) printf 'arch\n'; return ;;
      debian|ubuntu) printf 'debian\n'; return ;;
      fedora|rhel) printf 'fedora\n'; return ;;
      suse|opensuse|opensuse-*|sles) printf 'suse\n'; return ;;
    esac
  done
  if command -v pacman >/dev/null; then printf 'arch\n'
  elif command -v apt-get >/dev/null; then printf 'debian\n'
  elif command -v dnf >/dev/null; then printf 'fedora\n'
  elif command -v zypper >/dev/null; then printf 'suse\n'
  else printf 'unknown\n'; fi
}
FAMILY="$(detect_family)"
set_packages "$FAMILY"
case "$FAMILY" in
  arch) PKG_TOOL=pacman ;; debian) PKG_TOOL=apt ;; fedora) PKG_TOOL=dnf ;; suse) PKG_TOOL=zypper ;; *) PKG_TOOL="" ;;
esac
# Whether a package (on openSUSE also a capability it provides, as python3-gobject) is installed.
pkg_installed() {
  case "$FAMILY" in
    arch) pacman -Qq "$1" >/dev/null 2>&1 ;;
    debian) dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q 'ok installed' ;;
    fedora|suse) rpm -q --whatprovides "$1" >/dev/null 2>&1 ;;
    *) return 1 ;;
  esac
}
# Install packages with the family's tool, as root; --yes answers its questions.
pkg_install() {
  local yes=()
  case "$FAMILY" in
    arch) [ "$YES" = 1 ] && yes=(--noconfirm); as_root pacman -S --needed "${yes[@]}" "$@" ;;
    debian) [ "$YES" = 1 ] && yes=(-y); as_root apt-get install "${yes[@]}" "$@" ;;
    fedora) [ "$YES" = 1 ] && yes=(-y); as_root dnf install "${yes[@]}" "$@" ;;
    suse) [ "$YES" = 1 ] && yes=(--non-interactive); as_root zypper "${yes[@]}" install "$@" ;;
    *) return 1 ;;
  esac
}
# What to try when the tool could not install: its index is often old on a fresh system.
pkg_hint() {
  case "$FAMILY" in
    arch) printf "If it reported missing files (404), update first with 'sudo pacman -Syu' and run this again." ;;
    debian) printf "If it could not find a package, 'sudo apt-get update' first and run this again." ;;
    fedora) printf "If it could not find a package, 'sudo dnf upgrade --refresh' first and run this again (on RHEL and its rebuilds, enable EPEL)." ;;
    suse) printf "If it could not find a package, 'sudo zypper refresh' first and run this again." ;;
  esac
}
# Install, and stop only if something is still missing after: a tool's exit code can also mean
# a warning (zypper's 107, a script that failed after the packages went in). $1 names them.
pkg_install_checked() {
  local what="$1"; shift
  if ! pkg_install "$@"; then
    pkg_missing "$@"
    [ ${#MISSING[@]} -eq 0 ] || die "$PKG_TOOL could not install $what (${MISSING[*]}). $(pkg_hint)"
  fi
}
# An image-based system (Fedora Atomic, Bazzite, openSUSE Aeon and MicroOS) adds packages its own way.
immutable_hint() {
  if [ -e /run/ostree-booted ]; then
    printf 'this system is image-based (rpm-ostree): add the packages with sudo rpm-ostree install %s, reboot, then ./install.sh --no-deps' "$*"
  elif command -v transactional-update >/dev/null && findmnt -no OPTIONS / 2>/dev/null | grep -qw ro; then
    printf 'this system is image-based (transactional-update): add the packages with sudo transactional-update pkg install %s, reboot, then ./install.sh --no-deps' "$*"
  fi
}
# Only the packages not yet installed, into MISSING.
pkg_missing() { MISSING=(); local p; for p in "$@"; do pkg_installed "$p" || MISSING+=("$p"); done; }

usage() {
  sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | sed '$d; s/^# \{0,1\}//'
  cat <<'EOF'

Options:
  --autostart           start with every graphical login (systemd user service)
  --login-screen        optional: the rain and a login box as the login screen, from the next boot
                        (greetd); without it the installer never touches your login screen
  --login-screen-off    back to the login screen from before (undoes only what --login-screen did)
  --lock-screen         optional, KDE Plasma 6 on Wayland: the rain and syncrain's box as the lock
                        screen, from your next login; without it the installer never touches it
  --lock-screen-off     back to Plasma's own lock screen (undoes only what --lock-screen did)
  --config FILE         a settings file the web page exported: the wallpaper (and the login screen)
                        draw what the page showed; kept as ~/.config/syncrain/config.json
  --preset NAME         where the look starts: syncrain (the default), nixos or matrix (--theme: the same)
  --channel NAME        stream name (default: public)
  --rainbow MODE        logo (default), all or off
  --arg ARG             extra argument for syncrain, repeatable (e.g. --arg --fps --arg 24)
  --prefix DIR          install under DIR instead of ~/.local (or SYNCRAIN_PREFIX)
  --no-deps             skip the system's packages (installed by hand: see the error without it)
  --yes                 do not ask the package manager for confirmation
  --uninstall           remove syncrain
  -h, --help            this help
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --autostart) AUTOSTART=1 ;;
    --login-screen) LOGIN=1 ;;
    --login-screen-off) LOGIN_OFF=1 ;;
    --lock-screen) LOCK=1 ;;
    --lock-screen-off) LOCK_OFF=1 ;;
    --preset|--theme) THEME="${2:?$1 needs a value}"; shift ;;
    --config) CONFIG="${2:?--config needs a file}"; shift ;;
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

# The prefix goes into the launcher and the service's ExecStart: a whole path, and none of the
# characters a shell or systemd would read as their own
# (links stay as written, so a linked ~/.local is still the folder on PATH; a realpath without -m
# still gets a whole path)
PREFIX="$(realpath -ms -- "$PREFIX" 2>/dev/null || case "$PREFIX" in /*) printf '%s\n' "$PREFIX" ;; *) printf '%s\n' "$PWD/$PREFIX" ;; esac)"
case "$PREFIX" in
  *[\"\$\`\\%]*|*$'\n'*) die "the prefix $PREFIX holds a character the launcher and the service cannot carry (\" \$ \` \\ %)" ;;
esac
APPDIR="$PREFIX/share/syncrain"
BINDIR="$PREFIX/bin"
# The Python syncrain runs with: the system's (/usr/bin/python3, where the family's packages go) when
# it has GTK 4's bindings, cairo and Pillow, else the first python3 on PATH that has them (--no-deps, by hand), else
# whichever there is (the check after the packages says what is missing). Not simply the first on
# PATH: pyenv, conda or a venv there has none of the system's packages. SYNCRAIN_PYTHON decides.
pick_python() {
  local p
  if [ -n "${SYNCRAIN_PYTHON:-}" ]; then printf '%s\n' "$SYNCRAIN_PYTHON"; return; fi
  for p in /usr/bin/python3 "$(command -v python3 2>/dev/null || true)"; do
    if [ -n "$p" ] && [ -x "$p" ] && "$p" -c 'import gi; gi.require_version("Gtk", "4.0"); from gi.repository import Gtk; import cairo, PIL' 2>/dev/null; then
      printf '%s\n' "$p"; return
    fi
  done
  command -v python3 2>/dev/null || printf '/usr/bin/python3\n'
}
PY="$(pick_python)"
# The installs this script made carry this file; it removes no folder without it.
MARKER=".installed-by-syncrain"
# Whether $1 may be replaced or removed: nothing there, this script's install (its marker, or from
# before the marker: the app with no install.sh or .git beside it), and never the folder this script
# runs from or one holding it.
ours_to_replace() {
  local dir src
  [ -e "$1" ] || return 0
  dir="$(realpath -m -- "$1")" src="$(realpath -m -- "$SRC")"
  case "$src/" in "$dir"/*) die "this folder ($SRC) is where the app goes ($1): unpack the release elsewhere and run install.sh from there" ;; esac
  if [ -f "$1/$MARKER" ]; then return 0; fi
  if [ -d "$1" ] && [ -z "$(ls -A -- "$1")" ]; then return 0; fi
  if [ -d "$1/syncrain" ] && [ ! -e "$1/install.sh" ] && [ ! -e "$1/.git" ]; then return 0; fi
  local why="no syncrain folder in it"
  if [ -e "$1/.git" ]; then why="a .git in it"; elif [ -e "$1/install.sh" ]; then why="an install.sh in it"
  elif [ ! -d "$1" ]; then why="not a folder"; fi
  die "$1 is not an install of this script's (no $MARKER, $why), so it stays as it is"
}
UNITDIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT="$UNITDIR/syncrain.service"
have_user_systemd() { command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; }

# Builds 13 and 14 had a Plasma wallpaper (dropped in build 15): take it away again, and put Plasma's
# desktops and lock screen back on their image wallpaper.
remove_plasma_wallpaper() {
  local plugin=org.syncrain.wallpaper qml package
  package="${XDG_DATA_HOME:-$HOME/.local/share}/plasma/wallpapers/$plugin"
  qml="$(qtpaths6 --query QT_INSTALL_QML 2>/dev/null || true)"
  qml="${qml:-/usr/lib/qt6/qml}/org/syncrain"
  [ -d "$package" ] || [ -d "$qml" ] || return 0
  bold "Removing build 13 and 14's Plasma wallpaper"
  if command -v dbus-send >/dev/null && dbus-send --session --print-reply --dest=org.kde.plasmashell /PlasmaShell \
      org.kde.PlasmaShell.evaluateScript \
      "string:desktops().forEach(d => { if (d.wallpaperPlugin === '$plugin') d.wallpaperPlugin = 'org.kde.image'; });" \
      >/dev/null 2>&1; then
    info "Plasma's desktops are back on their image wallpaper"
  else
    info "Plasma's shell did not answer: if a desktop stays black, right-click it, Desktop and Wallpaper, Image"
  fi
  if [ "$(kreadconfig6 --file kscreenlockerrc --group Greeter --key WallpaperPlugin 2>/dev/null || true)" = "$plugin" ]; then
    kwriteconfig6 --file kscreenlockerrc --group Greeter --key WallpaperPlugin --delete && info "the lock screen too"
  fi
  rm -rf "$package" "${XDG_CACHE_HOME:-$HOME/.cache}/syncrain"/scene-*.bin
  if [ -d "$qml" ]; then
    local sudo=(); [ "$(id -u)" != 0 ] && sudo=(sudo)
    "${sudo[@]}" rm -rf "$qml" && info "removed $qml"
  fi
}

# ---- the login screen, only with --login-screen: greetd runs syncrain/login/login.sh as its user
# `greeter`, so the app is copied where that user can read it. The display manager it replaces (SDDM,
# Plasma Login) stays installed, and --login-screen-off switches back to it. Without --login-screen
# none of this runs: installing, upgrading and removing the wallpaper leave the login screen alone.
LOGIN_LIB="${SYNCRAIN_LOGIN_LIB:-/usr/local/lib/syncrain}"
LOGIN_STATE="${SYNCRAIN_LOGIN_STATE:-/var/lib/syncrain-login}"
GREETD_CONFIG="${SYNCRAIN_GREETD_CONFIG:-/etc/greetd/config.toml}"
PAM_DIR="${SYNCRAIN_PAM_DIR:-/etc/pam.d}"
DM_LINK="${SYNCRAIN_DM_LINK:-/etc/systemd/system/display-manager.service}"
# What started at boot before --login-screen: a unit (sddm.service, plasmalogin.service,
# greetd.service), "none" or "unknown". Written by --login-screen before anything else changes,
# beside greetd's config rather than in the app copy, so removing the copy never loses it;
# --login-screen-off deletes it last.
LOGIN_BEFORE="${SYNCRAIN_LOGIN_BEFORE:-$(dirname "$GREETD_CONFIG")/display-manager.before-syncrain}"
# Debian's and Ubuntu's display managers agree through this file: greetd's package points what starts
# at boot back at the one it names on every upgrade, and Ubuntu's SDDM will not start unless it names
# SDDM. Where it exists it changes with the switch, and goes back with it (the record beside it).
DDM_FILE="${SYNCRAIN_DDM_FILE:-/etc/X11/default-display-manager}"
DDM_BEFORE="$(dirname "$LOGIN_BEFORE")/default-display-manager.before-syncrain"
as_root() { if [ "$(id -u)" = 0 ]; then "$@"; else sudo "$@"; fi; }
# One of this user's files, copied to where root keeps the login screen: the user reads it, root only
# writes. root opening a path the user controls would follow a link there to root's own files and
# make them readable by everyone. A file this user cannot read stays out.
copy_to_root() {
  if [ -f "$1" ] && [ -r "$1" ]; then cat -- "$1" | as_root tee "$2" >/dev/null
  else info "not copied, this user cannot read it: $1"; fi
}
# The app, into the folder root made, $1: this user reads it into a stream and root unpacks that, so
# root never walks this user's folder, where a folder swapped for a link mid-copy would lead it
# elsewhere. A link is followed on this user's side (-h): the copy holds what it pointed at, as root's
# files, never a link back to something this user can still change and greetd's user would run.
copy_app_to_root() {
  tar -C "$APPDIR" -chf - syncrain | as_root tar -C "$1" -xf - --no-same-owner --no-same-permissions
  # only files and folders: a link a stream could still hold, devices and pipes go
  as_root find "$1" ! -type f ! -type d -delete
}
# KWin on the login screen reads this user's screen layout, keyboard layout and Num Lock (kcminputrc)
# from copies, made into the folder root made, $1.
copy_kde_settings() {
  local f conf="${XDG_CONFIG_HOME:-$HOME/.config}"
  for f in kwinoutputconfig.json kxkbrc kcminputrc; do
    if [ -e "$conf/$f" ] || [ -L "$conf/$f" ]; then copy_to_root "$conf/$f" "$1/$f"; fi
  done
}
# The operator's settings file (the web page's export), for the login screen's rain to draw alike.
copy_settings() {
  local settings="${XDG_CONFIG_HOME:-$HOME/.config}/syncrain/config.json"
  if [ -f "$settings" ]; then copy_to_root "$settings" "$1/config.json"; fi
}
# Whether the settings file names symbol sets of its own (they go over a symbols file).
settings_have_sets() {
  [ -f "$1" ] && "$PY" -c 'import json, sys; sys.exit(0 if isinstance(json.load(open(sys.argv[1], encoding="utf-8")).get("glyphs"), dict) else 1)' "$1" 2>/dev/null
}
# The copies of those settings login.sh made in the state folder go when they are copied anew: it
# makes them again at its next start. (find does not go into a link in the folder's place.)
clear_state_copies() {
  if [ -d "$LOGIN_STATE/config" ]; then
    as_root find "$LOGIN_STATE/config" -maxdepth 1 \( -name kwinoutputconfig.json -o -name kxkbrc -o -name kcminputrc \) -delete
  fi
}
# The hand-over after a login (syncrain/handover.py): Plasma's splash and wallpaper become a still
# frame of the rain. It needs this user's Plasma session (its shell sets the wallpaper).
in_plasma() { case "${XDG_CURRENT_DESKTOP:-}" in *KDE*) [ -n "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ] ;; *) false ;; esac; }
handover() { PYTHONPATH="$1" PYTHONSAFEPATH=1 "$PY" -m syncrain.handover "${@:2}"; }
HANDOVER_STATE="${XDG_STATE_HOME:-$HOME/.local/state}/syncrain/handover.json"
# This user's splash and wallpaper as they were: this folder's code, or the installed one's when this
# folder is too old to have it.
handover_off() {
  if [ -f "$SRC/syncrain/handover.py" ]; then handover "$SRC" off || true
  elif [ -f "$APPDIR/syncrain/handover.py" ]; then handover "$APPDIR" off || true; fi
}
# Who set the login screen up (login.json), or nothing. On a machine with more users, another user's
# installs, upgrades and removals of the wallpaper leave it as that user set it up.
login_user() {
  "$PY" -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("user", ""))' \
    "$LOGIN_LIB/login.json" 2>/dev/null || true
}
mine() { [ -f "$LOGIN_LIB/login.json" ] && [ "$(login_user)" = "$(id -un)" ]; }

# A file of the system's, read as this user where it can be (greetd's config and PAM files are).
read_system_file() { if [ -r "$1" ]; then cat -- "$1"; elif [ -e "$1" ]; then as_root cat -- "$1"; fi; }
greetdconf() {
  local lib="$SRC"
  [ -f "$lib/syncrain/greetdconf.py" ] || lib="$APPDIR"
  PYTHONPATH="$lib" PYTHONSAFEPATH=1 "$PY" -m syncrain.greetdconf "$@"
}
# The PAM file of the service greetd logs users in with ([general] service in its config), and of
# the one it runs its greeter under ([default_session] service).
pam_file() {
  local s
  s="$(read_system_file "$GREETD_CONFIG" | greetdconf service 2>/dev/null)" || s=greetd
  printf '%s/%s\n' "$PAM_DIR" "${s:-greetd}"
}
greeter_pam_file() {
  local s
  s="$(read_system_file "$GREETD_CONFIG" | greetdconf greeter-service 2>/dev/null)" || s=greetd-greeter
  printf '%s/%s\n' "$PAM_DIR" "${s:-greetd-greeter}"
}
# greetd's text login: on PATH, or where Debian keeps it (/usr/sbin, not on a user's PATH there).
# The system's own first: greetd runs it as its user, reading passwords, so one on PATH counts only
# if it is root's, outside this user's home, and safe inside the sh -c '...' of greetd's config.
agreety_path() {
  local a
  if [ -n "${SYNCRAIN_AGREETY:-}" ]; then printf '%s\n' "$SYNCRAIN_AGREETY"; return; fi
  for a in /usr/bin/agreety /usr/sbin/agreety; do
    if [ -x "$a" ]; then printf '%s\n' "$a"; return; fi
  done
  a="$(command -v agreety 2>/dev/null || true)"
  case "$a" in ""|"$HOME"/*|*[!A-Za-z0-9/._-]*) return 0 ;; esac
  if [ -x "$a" ] && [ "$(stat -c %u "$a" 2>/dev/null)" = 0 ]; then printf '%s\n' "$a"; fi
}
# The user greetd runs its greeter as, which each family names its own way (greeter on Arch and
# openSUSE, _greetd on Debian, greetd on Fedora): the one greetd's packaged config names, else the
# first of those that exists. SYNCRAIN_GREETER_USER overrides it.
greeter_user() {
  local u="" f
  if [ -n "${SYNCRAIN_GREETER_USER:-}" ]; then printf '%s\n' "$SYNCRAIN_GREETER_USER"; return; fi
  for f in "$GREETD_CONFIG.before-syncrain" "$GREETD_CONFIG"; do
    if [ -e "$f" ]; then u="$(read_system_file "$f" | greetdconf user 2>/dev/null || true)"; fi
    if [ -n "$u" ]; then break; fi
  done
  for u in $u greeter _greetd greetd; do
    if getent passwd "$u" >/dev/null 2>&1; then printf '%s\n' "$u"; return; fi
  done
}
PAM_MARK="written by syncrain's install.sh --login-screen"
WALLET_MARK="# added by syncrain's install.sh --login-screen"
WALLET_LINES=("-auth       optional    pam_gnome_keyring.so" "-auth       optional    pam_kwallet5.so"
              "-session    optional    pam_gnome_keyring.so    auto_start" "-session    optional    pam_kwallet5.so         auto_start")
# A PAM file (stdin) without the lines --login-screen added: its mark, the wallet lines right after it,
# and the blank line before it; nothing else.
without_wallet() {
  "$PY" -c 'import sys
mark, wallet = sys.argv[1], set(sys.argv[2:])
lines, out, i = sys.stdin.buffer.read().decode("utf-8", "surrogateescape").split("\n"), [], 0
while i < len(lines):
    if lines[i].startswith(mark):
        if out and not out[-1].strip():
            out.pop()
        i += 1
        while i < len(lines) and lines[i] in wallet:
            i += 1
        continue
    out.append(lines[i])
    i += 1
sys.stdout.buffer.write("\n".join(out).encode("utf-8", "surrogateescape"))' "$WALLET_MARK" "${WALLET_LINES[@]}"
}
CONFIG_MARK="set by syncrain's install.sh --login-screen"

unit_name() { case "$1" in *[!A-Za-z0-9@._-]*|"") return 1 ;; *.service) return 0 ;; *) return 1 ;; esac; }
# What starts at boot now: the display manager's unit, "none" without one, "unknown" for anything else.
display_manager() {
  local t
  if [ -L "$DM_LINK" ]; then
    t="$(basename "$(readlink "$DM_LINK")")"
    if unit_name "$t"; then printf '%s\n' "$t"; else printf 'unknown\n'; fi
  elif [ -e "$DM_LINK" ]; then printf 'unknown\n'
  else printf 'none\n'; fi
}
# The record of what started at boot before syncrain's login screen, or nothing. Builds 16 and 17 kept
# it inside the app copy, and only for a display manager other than greetd.
recorded_before() {
  local v=""
  if [ -f "$LOGIN_BEFORE" ]; then v="$(head -n 1 "$LOGIN_BEFORE")"
  elif [ -f "$LOGIN_LIB/previous-display-manager" ]; then v="$(head -n 1 "$LOGIN_LIB/previous-display-manager")"; fi
  case "$v" in none|unknown) printf '%s\n' "$v" ;; *) if unit_name "$v"; then printf '%s\n' "$v"; fi ;; esac
}
record_before() {
  as_root mkdir -p "$(dirname "$LOGIN_BEFORE")"
  printf '%s\n' "$1" | as_root tee "$LOGIN_BEFORE" >/dev/null
  as_root chmod 644 "$LOGIN_BEFORE"             # read back as this user, whatever root's umask
}
keep_record() { if [ ! -f "$LOGIN_BEFORE" ] && [ -n "$1" ]; then record_before "$1"; fi; }

# greetd's side of the login screen, at --login-screen and again at each upgrade (an earlier build
# wrote greetd's whole config and missed the greeter's PAM file).
apply_greetd() {
  if [ -f "$GREETD_CONFIG" ] && ! grep -q syncrain "$GREETD_CONFIG" && [ ! -f "$GREETD_CONFIG.before-syncrain" ]; then
    as_root cp "$GREETD_CONFIG" "$GREETD_CONFIG.before-syncrain"
  fi
  as_root mkdir -p "$(dirname "$GREETD_CONFIG")"
  # Only [default_session] changes; the rest of greetd's config stays as the operator has it: a PAM
  # service, an automatic login, the terminal. A whole config written by builds 16 to 18 starts again
  # from greetd's own. If the login screen's files ever go missing, greetd's text login asks
  # instead of a black screen. login.sh is read by sh, not run itself, and read once first (sh -n
  # parses without running), so a policy that refuses to run or to read it (SELinux, fapolicyd)
  # leaves the text login, not a shell that ended at a failed exec.
  local login="$LOGIN_LIB/syncrain/login/login.sh" base="$GREETD_CONFIG" edited pam greeter_pam agreety user
  agreety="$(agreety_path)" user="$(greeter_user)"
  if [ -z "$agreety" ] || [ -z "$user" ]; then
    info "greetd's config stays as it is: its text login or its user was not found"
    return 0
  fi
  if grep -qs syncrain "$GREETD_CONFIG" && ! grep -qsF "$CONFIG_MARK" "$GREETD_CONFIG"; then
    base="$GREETD_CONFIG.before-syncrain"
  fi
  edited="$(mktemp)"
  if ! read_system_file "$base" | greetdconf config \
      "sh -c '/bin/sh -n $login 2>/dev/null && SYNCRAIN_LOGIN_TEXT=$agreety exec /bin/sh $login; exec $agreety --cmd startplasma-wayland'" "$user" > "$edited"; then
    rm -f "$edited"
    die "greetd's config ($base) could not be changed, so it stays as it is"
  fi
  copy_to_root "$edited" "$GREETD_CONFIG"
  rm -f "$edited"
  pam="$(pam_file)"
  greeter_pam="$(greeter_pam_file)"
  # SDDM's PAM opens KDE's wallet (and GNOME's keyring) with the password typed at login; greetd's
  # does not, so without these the wallet would ask again. "-" skips a module that is not installed.
  # The lines are marked, and --login-screen-off takes out those lines alone: whatever else is
  # changed in the file meanwhile (a second factor, faillock) stays.
  if [ -f "$pam" ] && ! grep -q pam_kwallet5 "$pam"; then
    printf '%s\n' "" "$WALLET_MARK: the wallet opens with the login, as under SDDM" "${WALLET_LINES[@]}" \
      | as_root tee -a "$pam" >/dev/null
  fi
  # greetd runs its greeter under its own PAM service where that file exists, else under the users'
  # one: a file without the wallet lines keeps a wallet starting for the user greeter at every boot.
  # It is greetd's own file without them, made again at each install, so the file's changes reach it.
  if grep -qsF "$WALLET_MARK" "$pam" && [ "$greeter_pam" != "$pam" ] \
      && { [ ! -e "$greeter_pam" ] || head -n 1 "$greeter_pam" | grep -qF "$PAM_MARK"; }; then
    # made whole beside, and put there only when it holds more than its first line: a file of no
    # rules would leave greetd no greeter
    local made
    made="$(mktemp)"
    if { printf '# %s: greetd'"'"'s greeter, greetd'"'"'s own file without the wallet lines (made again at each install)\n' "$PAM_MARK"
         read_system_file "$pam" | without_wallet; } > "$made" && grep -qv '^[[:space:]]*\(#.*\)\?$' "$made"; then
      copy_to_root "$made" "$greeter_pam"
    else
      info "greetd's greeter keeps its PAM file as it was: greetd's own could not be read"
    fi
    rm -f "$made"
  fi
}

login_screen_on() {
  bold "Making the rain your login screen (greetd)"
  command -v kwin_wayland >/dev/null || die "the login screen runs in KWin (Plasma's compositor), which is not installed"
  local tmp glyphs settings rain=("${ARGS[@]}") before now new="$LOGIN_LIB.new" f conf="${XDG_CONFIG_HOME:-$HOME/.config}"
  # A record counts while greetd starts at boot. Once something else does (picked since), that is
  # what comes before; with greetd running syncrain's config and no record, it is not known.
  # Seen before greetd is installed, as Debian's package makes itself what starts at boot where
  # nothing did; written once greetd is there, so a run that stops leaves no record behind.
  before="$(recorded_before)"
  now="$(display_manager)"
  if [ "$now" != greetd.service ]; then before="$now"
  elif [ -z "$before" ]; then
    before=greetd.service
    if grep -qs syncrain "$GREETD_CONFIG"; then before=unknown; fi
  fi
  # Debian's file too, before greetd's package (whose question may make it name greetd) is in
  local ddm_was=""
  if [ "$now" != greetd.service ] && [ -f "$DDM_FILE" ]; then ddm_was="$(read_system_file "$DDM_FILE")"; fi
  if [ "$NODEPS" = 0 ] && [ -n "$PKG_TOOL" ]; then
    pkg_missing "${LOGIN_PACKAGES[@]}"
    if [ ${#MISSING[@]} -gt 0 ]; then pkg_install_checked "greetd" "${MISSING[@]}"; fi
  fi
  [ -n "$(agreety_path)" ] || die "greetd's text login (agreety, in ${LOGIN_PACKAGES[*]}) is missing; the login screen falls back to it"
  [ -n "$(greeter_user)" ] || die "greetd's user was not found (greetd's config names none that exists): is greetd installed?"
  record_before "$before"
  ddm_record "$ddm_was"
  tmp="$(mktemp -d)"
  # login.json: who logs in by default, and the rain's options as given to this installer
  glyphs="$conf/syncrain/glyphs.json" settings="$conf/syncrain/config.json"
  # a settings file's own sets go over a symbols file, as on the desktop (syncrain/greeter.py drops
  # --glyphs for them too, for a login.json written before the settings file)
  if [ -f "$glyphs" ] && ! settings_have_sets "$settings"; then
    cp "$glyphs" "$tmp/glyphs.json"; rain+=(--glyphs "$LOGIN_LIB/glyphs.json")
  fi
  write_login_json() {
    "$PY" -c 'import json, sys; json.dump({"user": sys.argv[2], "session": "plasma.desktop", "rain": sys.argv[3:]},
                open(sys.argv[1], "w"), indent=1)' "$@"
  }
  write_login_json "$tmp/login.json" "$(id -un)" "${rain[@]}"
  if [ -f "$tmp/glyphs.json" ] || settings_have_sets "$settings"; then
    # Symbols not in syncrain's own set are drawn now, with this user's fonts, so the login screen
    # does not spend seconds drawing them at every boot.
    if [ -f "$tmp/glyphs.json" ]; then
      write_login_json "$tmp/draw.json" "$(id -un)" "${ARGS[@]}" --glyphs "$tmp/glyphs.json"
    else
      write_login_json "$tmp/draw.json" "$(id -un)" --config "$settings" "${ARGS[@]}"
    fi
    XDG_CACHE_HOME="$tmp/cache" SYNCRAIN_LOGIN_CONFIG="$tmp/draw.json" PYTHONPATH="$APPDIR" PYTHONSAFEPATH=1 \
      "$PY" -m syncrain.greeter --draw-symbols || info "the symbols were not drawn now; the login screen draws them"
  fi
  # Made beside the old copy and swapped in whole, so greetd never finds half of one. Root reads
  # nothing of this user's: the app comes as a stream (copy_app_to_root), every other file through
  # copy_to_root. chmod -R is given only the folder root made: a link it meets inside, it leaves alone.
  as_root rm -rf "$new"
  as_root mkdir -p "$new/cache" "$new/kde"
  copy_app_to_root "$new"
  copy_to_root "$APPDIR/BUILD_NUMBER" "$new/BUILD_NUMBER"
  copy_to_root "$tmp/login.json" "$new/login.json"
  if [ -f "$tmp/glyphs.json" ]; then copy_to_root "$tmp/glyphs.json" "$new/glyphs.json"; fi
  for f in "$tmp/cache/syncrain"/glyphs-*.png; do
    if [ -f "$f" ]; then copy_to_root "$f" "$new/cache/${f##*/}"; fi
  done
  copy_kde_settings "$new/kde"
  copy_settings "$new"
  as_root chmod -R a+rX,go-w,ug-s "$new"
  as_root rm -rf "$LOGIN_LIB"
  as_root mv "$new" "$LOGIN_LIB"
  local owner="${SYNCRAIN_LOGIN_OWNER:-$(greeter_user)}"
  # greetd's user's alone, as on NixOS: its log and last.json say who logged in, and when
  as_root install -d -m 700 -o "$owner" -g "$(id -gn "$owner")" "$LOGIN_STATE"
  clear_state_copies
  rm -rf "$tmp"
  info "the app: $LOGIN_LIB (user $(id -un), Plasma, the rain's options given to this installer)"

  apply_greetd
  as_root systemctl enable --force greetd.service >/dev/null || die "systemctl could not enable greetd"
  ddm_set
  if in_plasma; then
    info "after a login, Plasma's splash and wallpaper show a still frame of the rain (a window opens for a moment):"
    handover "$APPDIR" on "${ARGS[@]}" || info "the still frame was not made; Plasma's splash and wallpaper stay as they were"
  else
    info "run this again from your Plasma session for the still frame after a login"
  fi
  info "from your next boot the login screen is the rain (before: $before)"
  info "if it ever fails, greetd's text login asks instead, and Plasma starts as usual"
  info "back: ./install.sh --login-screen-off"
  if unit_name "$before" && [ "$before" != greetd.service ]; then
    if [ -f "$DDM_BEFORE" ]; then
      info "  or from a text console (Ctrl+Alt+F3): sudo systemctl enable --force $before && sudo cp $DDM_BEFORE $DDM_FILE && sudo reboot"
    else
      info "  or from a text console (Ctrl+Alt+F3): sudo systemctl enable --force $before && sudo reboot"
    fi
  fi
}

# Puts back only what --login-screen changed, and only when syncrain changed it: with no record, no
# app copy and no greetd config of syncrain's, the login screen is not syncrain's and stays as it is.
# What starts at boot changes only while greetd still does: a display manager picked since stays,
# and one that is gone leaves greetd with its own config rather than no way to log in. Run again
# (for the hand-over, from Plasma), it finds nothing more of the login screen to put back.
# greetd's [default_session] as it was before --login-screen (its command and user, as they were
# written); every other change to the config since stays. If greetd would not read the result as
# meant, the config stays: its command finds no login.sh and runs greetd's text login.
greetd_back() {
  local back was
  if [ -f "$GREETD_CONFIG.before-syncrain" ] && grep -qs syncrain "$GREETD_CONFIG"; then
    back="$(mktemp)" was="$(mktemp)"
    read_system_file "$GREETD_CONFIG.before-syncrain" > "$was"
    if read_system_file "$GREETD_CONFIG" | greetdconf restore "$was" > "$back"; then
      copy_to_root "$back" "$GREETD_CONFIG"
      as_root rm -f "$GREETD_CONFIG.before-syncrain"
    else
      info "greetd's config keeps syncrain's login command (above); with the login screen gone it runs greetd's text login"
    fi
    rm -f "$back" "$was"
  fi
}
# Debian's default-display-manager names greetd while the login screen is on (see DDM_FILE).
greetd_daemon() { command -v greetd 2>/dev/null || printf '/usr/sbin/greetd\n'; }
# What the file named before: $1, as read before greetd's package could change it, recorded whenever
# something other than greetd starts at boot (a display manager picked since is what comes before).
ddm_record() {
  if [ -n "$1" ]; then printf '%s\n' "$1" | as_root tee "$DDM_BEFORE" >/dev/null; fi
}
ddm_set() {
  [ -f "$DDM_FILE" ] || return 0
  greetd_daemon | as_root tee "$DDM_FILE" >/dev/null
}
# ... and names what it named before, back with the switch: when greetd starts at boot and is
# switched away from here, or when the file still names greetd as this script wrote it (the
# operator switched back by hand, as the hint said). A file someone changed since stays theirs.
ddm_back() {
  if [ ! -f "$DDM_BEFORE" ] || [ ! -f "$DDM_FILE" ]; then
    if [ -z "$again" ]; then as_root rm -f "$DDM_BEFORE"; fi
    return 0
  fi
  local names
  names="$(read_system_file "$DDM_FILE")"
  if { [ "$1" = greetd.service ] && [ -z "$keep$again" ]; } \
      || { [ "$1" != greetd.service ] && [ "$names" = "$(greetd_daemon)" ]; }; then
    read_system_file "$DDM_BEFORE" | as_root tee "$DDM_FILE" >/dev/null
  fi
  if [ -z "$again" ]; then as_root rm -f "$DDM_BEFORE"; fi
}

login_screen_off() {
  local before now keep="" again="" pam greeter_pam
  before="$(recorded_before)"
  now="$(display_manager)"
  if [ -z "$before" ] && [ ! -d "$LOGIN_LIB" ] && ! grep -qs syncrain "$GREETD_CONFIG"; then
    bold "syncrain's login screen is not installed: the login screen stays as it is"
  else
    if [ "$now" != greetd.service ]; then
      bold "Taking syncrain's login screen out; what starts at boot ($now) stays"
    else
      case "$before" in
        none) bold "Putting back what started at boot before: no display manager"
              as_root systemctl disable greetd.service >/dev/null || again="systemctl could not disable greetd" ;;
        greetd.service) bold "Putting greetd's own login back" ;;
        ""|unknown) bold "Taking syncrain's login screen out"
                    keep="what started at boot before is not known" ;;
        *) bold "Putting the login screen back on $before"
           if ! as_root systemctl enable --force "$before" >/dev/null; then
             if systemctl cat "$before" >/dev/null 2>&1; then again="systemctl could not enable $before"
             else keep="$before is not installed any more"; fi
           fi ;;
      esac
    fi
    ddm_back "$now"                             # first: what a stop half way leaves is then right
    pam="$(pam_file)"                           # the config before syncrain names the same services
    greeter_pam="$(greeter_pam_file)"
    greetd_back
    # Only the lines --login-screen added go: a second factor or faillock added since stays. (Builds
    # up to 35 kept a whole copy of the file beside it; the copy goes, unused.)
    if grep -qsF "$WALLET_MARK" "$pam"; then
      local cleaned
      cleaned="$(mktemp)"
      read_system_file "$pam" | without_wallet > "$cleaned"
      copy_to_root "$cleaned" "$pam"
      rm -f "$cleaned"
    fi
    as_root rm -f "$pam.before-syncrain"
    if head -n 1 "$greeter_pam" 2>/dev/null | grep -qF "$PAM_MARK"; then as_root rm -f "$greeter_pam"; fi
    as_root rm -rf "$LOGIN_LIB" "$LOGIN_STATE"
    # The record goes once what it names is back; a run that could not do that leaves it for the next.
    if [ -n "$again" ]; then
      record_before "$before"                   # builds 16 and 17 kept it in the app copy, gone now
      info "$again: greetd stays for now, with its own config; ./install.sh --login-screen-off again finishes this"
    else
      as_root rm -f "$LOGIN_BEFORE"
    fi
    if [ -n "$keep" ]; then
      info "$keep, so greetd stays, with its own config;"
      info "to switch: sudo systemctl enable --force <the one you want>.service"
    fi
    info "from your next boot; greetd stays installed"
  fi
  handover_off
}

# A newer build updates the login screen's copy too, keeping its settings (and moving the record of
# what started at boot before out of the copy, where builds 16 and 17 kept it). Only the user who
# set the login screen up updates it.
login_screen_refresh() {
  if ! mine; then
    if [ -f "$LOGIN_LIB/login.json" ]; then info "the login screen stays as $(login_user) set it up"; fi
    return 0
  fi
  keep_record "$(recorded_before)"
  # Into a folder root makes, for chmod -R: given a link by name, it would follow it, and the copy
  # is of a folder this user can change. The screen and keyboard settings go over again too, as this
  # user reads them now, so a copy an earlier build made as root through a link goes.
  as_root rm -rf "$LOGIN_LIB.new"
  as_root mkdir -p "$LOGIN_LIB.new/kde"
  copy_app_to_root "$LOGIN_LIB.new"
  copy_kde_settings "$LOGIN_LIB.new/kde"
  copy_settings "$LOGIN_LIB.new"
  as_root chmod -R a+rX,go-w,ug-s "$LOGIN_LIB.new"
  as_root rm -rf "$LOGIN_LIB/syncrain" "$LOGIN_LIB/kde"
  as_root mv "$LOGIN_LIB.new/syncrain" "$LOGIN_LIB.new/kde" "$LOGIN_LIB/"
  if [ -f "$LOGIN_LIB.new/config.json" ]; then as_root mv -f "$LOGIN_LIB.new/config.json" "$LOGIN_LIB/"
  else as_root rm -f "$LOGIN_LIB/config.json"; fi
  as_root rm -rf "$LOGIN_LIB.new"
  clear_state_copies
  copy_to_root "$APPDIR/BUILD_NUMBER" "$LOGIN_LIB/BUILD_NUMBER"
  as_root chmod a+r "$LOGIN_LIB/BUILD_NUMBER"
  if grep -qs syncrain "$GREETD_CONFIG"; then apply_greetd; fi
  # what --login-screen does since build 36, for a login screen set up before it
  if [ "$(display_manager)" = greetd.service ] && grep -qsF "$CONFIG_MARK" "$GREETD_CONFIG"; then
    if [ -f "$DDM_FILE" ] && [ ! -f "$DDM_BEFORE" ] && [ "$(read_system_file "$DDM_FILE")" != "$(greetd_daemon)" ]; then
      ddm_record "$(read_system_file "$DDM_FILE")"
      ddm_set
    fi
    if [ -d "$LOGIN_STATE" ]; then as_root chmod 700 "$LOGIN_STATE"; fi
  fi
  info "the login screen: build $BUILD too"
  # Options given now, or a new settings file, are the login screen's too, as they are the service's:
  # its options from before would go over the new settings and draw another rain there.
  if [ ${#ARGS[@]} -gt 0 ] || [ -n "$CONFIG" ]; then
    local made
    made="$(mktemp)"
    if "$PY" -c 'import json, os, sys
path, out, lib, args = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
login = json.load(open(path, encoding="utf-8"))
glyphs = os.path.join(lib, "glyphs.json")
try:
    sets = isinstance(json.load(open(os.path.join(lib, "config.json"), encoding="utf-8")).get("glyphs"), dict)
except (OSError, ValueError, AttributeError):
    sets = False
login["rain"] = args + (["--glyphs", glyphs] if os.path.isfile(glyphs) and not sets else [])
json.dump(login, open(out, "w", encoding="utf-8"), indent=1)' "$LOGIN_LIB/login.json" "$made" "$LOGIN_LIB" "${ARGS[@]}"; then
      copy_to_root "$made" "$LOGIN_LIB/login.json"
      as_root chmod a+r "$LOGIN_LIB/login.json"
      info "the login screen's options: as given now (${ARGS[*]:-none})"
    fi
    rm -f "$made"
  fi
  local rain=()
  # the login screen's options without its copy of the symbols file (here syncrain reads yours)
  mapfile -t rain < <("$PY" -c '
import json, sys
args = json.load(open(sys.argv[1])).get("rain", [])
skip = {i + 1 for i, a in enumerate(args) if a == "--glyphs"} | {i for i, a in enumerate(args) if a == "--glyphs"}
[print(a) for i, a in enumerate(args) if i not in skip]' "$LOGIN_LIB/login.json" 2>/dev/null)
  # only the still frame again: the splash and wallpapers stay as the operator has them now
  if in_plasma && [ -f "$HANDOVER_STATE" ]; then
    handover "$APPDIR" still "${rain[@]}" >/dev/null || true
  fi
}

# ---- the lock screen, only with --lock-screen: KDE Plasma's own locker (kscreenlocker_greet, which
# KWin starts) loads its screen from the shell package that PLASMA_DEFAULT_SHELL names when
# plasmashellrc names none. That variable goes to KWin alone, in a drop-in for its systemd unit, so
# Plasma's shell (whose layout is kept under the name of its own package) never sees it. The package
# (syncrain/lockscreen/package/) draws the rain with syncrain's QML module, built here, from the scene
# file the wallpaper keeps current; nothing in the lock screen runs Python. Without --lock-screen none
# of this runs, and --lock-screen-off takes away exactly these files.
LOCK_SHELL="${XDG_DATA_HOME:-$HOME/.local/share}/plasma/shells/org.syncrain.lockscreen"
LOCK_LIB="$PREFIX/lib/syncrain"
LOCK_QML="$LOCK_LIB/qml"
LOCK_STATE="${XDG_STATE_HOME:-$HOME/.local/state}/syncrain"
LOCK_SCENE="$LOCK_STATE/lock-screen.scene"
# plasmashellrc's ShellPackage when it said org.kde.plasma.desktop outright (the default spelled out,
# which some global themes write): taken out so the variable decides, put back by --lock-screen-off
LOCK_SHELL_BEFORE="$LOCK_STATE/plasmashellrc-ShellPackage.before-syncrain"
# kscreenlockerrc's wallpaper plugin before --lock-screen (empty: none was named), to put back
LOCK_WALLPAPER_BEFORE="$LOCK_STATE/kscreenlockerrc-WallpaperPlugin.before-syncrain"
LOCK_DROPIN_DIR="$UNITDIR/plasma-kwin_wayland.service.d"
LOCK_DROPIN="$LOCK_DROPIN_DIR/syncrain-lock-screen.conf"
lock_screen_installed() { [ -f "$LOCK_DROPIN" ]; }

# The module, the package and the scene, each made beside the one in use and then put in its place.
lock_screen_build() {
  local work log
  work="$(mktemp -d)"
  if ! log="$(cmake -S "$APPDIR/syncrain/lockscreen" -B "$work" -DCMAKE_BUILD_TYPE=Release 2>&1 \
              && cmake --build "$work" -j "$(nproc)" 2>&1)"; then
    printf '%s\n' "$log" | tail -n 8 | sed 's/^/    /'
    rm -rf -- "${work:?}"
    info "the lock screen's module did not build (it is built with: ${LOCK_PACKAGES[*]})"
    return 1
  fi
  # (inside a function called from `if`, set -e is off: each step says when it fails)
  rm -rf -- "${LOCK_QML:?}.new"
  if ! { mkdir -p "$LOCK_QML.new/org/syncrain" \
         && cp "$work"/qml/org/syncrain/qmldir "$work"/qml/org/syncrain/*.qmltypes "$work"/qml/org/syncrain/*.so \
               "$LOCK_QML.new/org/syncrain/"; }; then
    rm -rf -- "${work:?}" "${LOCK_QML:?}.new"
    info "the lock screen's module could not be copied"
    return 1
  fi
  rm -rf -- "${work:?}" "${LOCK_QML:?}"
  mv "$LOCK_QML.new" "$LOCK_QML" || { info "the lock screen's module could not be put in place"; return 1; }
  mkdir -p "${XDG_DATA_HOME:-$HOME/.local/share}/plasma/shells" || return 1
  rm -rf -- "${LOCK_SHELL:?}.new"
  cp -r "$APPDIR/syncrain/lockscreen/package" "$LOCK_SHELL.new" \
    || { info "the lock screen's package could not be copied"; return 1; }
  rm -rf -- "${LOCK_SHELL:?}"
  mv "$LOCK_SHELL.new" "$LOCK_SHELL" || { info "the lock screen's package could not be put in place"; return 1; }
  mkdir -p "$LOCK_STATE" || return 1
  # this run's options; a wallpaper the run then restarts writes it again with the service's own
  if ! "$BINDIR/syncrain" --write-scene "$LOCK_SCENE" "${ARGS[@]}"; then
    info "the lock screen's scene could not be made, so it shows the box on black (see above)"
    return 1
  fi
}

# Plasma's locker loads the wallpaper kscreenlockerrc names (an image, decoded at the screen's size)
# under any shell package, where syncrain's never shows it: a plain black costs nothing, and should
# syncrain's lock screen not load, Plasma's own then shows black. Done once (the record says so): a
# wallpaper chosen in Plasma's settings afterwards is the operator's, and stays.
lock_wallpaper_plain() {
  [ -f "$LOCK_WALLPAPER_BEFORE" ] && return 0
  command -v kreadconfig6 >/dev/null && command -v kwriteconfig6 >/dev/null || return 0
  mkdir -p "$LOCK_STATE" || return 0
  kreadconfig6 --file kscreenlockerrc --group Greeter --key WallpaperPlugin > "$LOCK_WALLPAPER_BEFORE" 2>/dev/null \
    || : > "$LOCK_WALLPAPER_BEFORE"
  if kwriteconfig6 --file kscreenlockerrc --group Greeter --key WallpaperPlugin org.kde.color \
      && kwriteconfig6 --file kscreenlockerrc --group Greeter --group Wallpaper --group org.kde.color --group General \
           --key Color 0,0,0; then
    info "the lock screen: Plasma's own lock wallpaper, unseen under syncrain's, is plain black now"
  else
    rm -f -- "$LOCK_WALLPAPER_BEFORE"
  fi
}

lock_screen_on() {
  bold "Setting up the lock screen"
  if ! { have_user_systemd && systemctl --user cat plasma-kwin_wayland.service >/dev/null 2>&1; }; then
    die "--lock-screen is for KDE Plasma 6 on Wayland started by systemd (plasma-kwin_wayland.service); not found here, so nothing was changed"
  fi
  case "$LOCK_QML$LOCK_SCENE" in
    *[\"\\%]*) die "--lock-screen cannot name $LOCK_QML or $LOCK_SCENE in KWin's unit (a quote, backslash or % in the path)" ;;
  esac
  local shell
  shell="$(kreadconfig6 --file plasmashellrc --group Shell --key ShellPackage 2>/dev/null || true)"
  if [ -n "$shell" ] && [ "$shell" != org.kde.plasma.desktop ]; then
    die "plasmashellrc names the shell package $shell, and the lock screen follows it, so syncrain's would not show; nothing was changed"
  fi
  lock_screen_build || die "the lock screen was not set up (see above); nothing in Plasma was changed"
  if [ "$shell" = org.kde.plasma.desktop ]; then
    printf '%s\n' "$shell" > "$LOCK_SHELL_BEFORE"
    kwriteconfig6 --file plasmashellrc --group Shell --key ShellPackage --delete
    info "plasmashellrc spelled out Plasma's default shell; taken out (--lock-screen-off puts it back)"
  fi
  lock_wallpaper_plain
  mkdir -p "$LOCK_DROPIN_DIR"
  cat > "$LOCK_DROPIN" <<EOF
# Written by syncrain's install.sh --lock-screen (./install.sh --lock-screen-off removes it): KWin
# starts Plasma's lock screen with these, and the lock screen then shows syncrain's.
[Service]
Environment="PLASMA_DEFAULT_SHELL=org.syncrain.lockscreen"
Environment="QML_IMPORT_PATH=$LOCK_QML"
Environment="SYNCRAIN_LOCK_SCENE=$LOCK_SCENE"
EOF
  systemctl --user daemon-reload || true
  info "the lock screen: syncrain's from your next login (log out and back in once: KWin starts it)"
  info "should it ever not unlock: Ctrl+Alt+F3, log in there, loginctl unlock-sessions, then ./install.sh --lock-screen-off"
}

# Every install while the lock screen is in place: its module, package and scene on this build too.
lock_screen_refresh() {
  lock_screen_installed || return 0
  local said
  lock_wallpaper_plain                      # an install from before this was done
  if said="$(lock_screen_build 2>&1)"; then info "the lock screen: build $BUILD too"
  else
    printf '%s\n' "$said"
    info "the lock screen could not be brought to build $BUILD (above); unlocking works as before"
  fi
}

lock_screen_off() {
  local had=0
  if [ -f "$LOCK_DROPIN" ]; then
    rm -f -- "$LOCK_DROPIN"
    rmdir -- "$LOCK_DROPIN_DIR" 2>/dev/null || true
    if have_user_systemd; then systemctl --user daemon-reload || true; fi
    had=1
  fi
  if [ -e "$LOCK_SHELL" ] || [ -e "$LOCK_QML" ] || [ -e "$LOCK_SCENE" ]; then had=1; fi
  rm -rf -- "${LOCK_SHELL:?}" "${LOCK_SHELL:?}.new" "${LOCK_QML:?}" "${LOCK_QML:?}.new"
  rm -f -- "$LOCK_SCENE"
  rmdir -- "$LOCK_LIB" 2>/dev/null || true
  if [ -f "$LOCK_SHELL_BEFORE" ]; then
    kwriteconfig6 --file plasmashellrc --group Shell --key ShellPackage "$(cat "$LOCK_SHELL_BEFORE")" \
      && rm -f -- "$LOCK_SHELL_BEFORE"
  fi
  if [ -f "$LOCK_WALLPAPER_BEFORE" ]; then
    local was now
    was="$(cat "$LOCK_WALLPAPER_BEFORE")"
    now="$(kreadconfig6 --file kscreenlockerrc --group Greeter --key WallpaperPlugin 2>/dev/null || true)"
    # put back only what syncrain set: one chosen since in Plasma's settings stays
    if [ "$now" = org.kde.color ]; then
      if [ -n "$was" ]; then kwriteconfig6 --file kscreenlockerrc --group Greeter --key WallpaperPlugin "$was"
      else kwriteconfig6 --file kscreenlockerrc --group Greeter --key WallpaperPlugin --delete; fi
      kwriteconfig6 --file kscreenlockerrc --group Greeter --group Wallpaper --group org.kde.color --group General \
        --key Color --delete || true
    fi
    rm -f -- "$LOCK_WALLPAPER_BEFORE"
    had=1
  fi
  if [ "$had" = 1 ]; then
    bold "The lock screen is Plasma's own again"
    info "from your next login (log out and back in once)"
  else
    info "the lock screen was not syncrain's; nothing to undo"
  fi
}

# The ways back, each asked for one runs, in this order, and nothing is installed after them.
if [ "$LOCK_OFF" = 1 ] || [ "$LOGIN_OFF" = 1 ] || [ "$UNINSTALL" = 1 ]; then
  # an uninstall that would refuse the app's folder refuses before anything else is taken away
  if [ "$UNINSTALL" = 1 ]; then ours_to_replace "$APPDIR"; fi
  if [ "$LOCK_OFF" = 1 ]; then lock_screen_off; fi
  if [ "$LOGIN_OFF" = 1 ]; then login_screen_off; fi
  [ "$UNINSTALL" = 1 ] || exit 0
  # syncrain's login screen goes too when this user set it up. Another user's stays, and without one
  # the login screen is not touched at all.
  if [ "$LOGIN_OFF" = 1 ]; then :
  elif mine; then login_screen_off
  else
    if [ -f "$LOGIN_LIB/login.json" ]; then info "the login screen stays as $(login_user) set it up (--login-screen-off takes it out)"; fi
    if [ -f "$HANDOVER_STATE" ]; then handover_off; fi
  fi
  remove_plasma_wallpaper
  if lock_screen_installed || [ -e "$LOCK_SHELL" ] || [ -f "$LOCK_WALLPAPER_BEFORE" ]; then lock_screen_off; fi
  bold "Removing syncrain"
  if [ -f "$UNIT" ]; then
    if have_user_systemd; then systemctl --user disable --now syncrain.service >/dev/null 2>&1 || true; fi
    rm -f "$UNIT"
    if have_user_systemd; then systemctl --user daemon-reload || true; fi
    info "removed the autostart service"
  fi
  state="${XDG_STATE_HOME:-$HOME/.local/state}/syncrain"
  gone=("$APPDIR" "$BINDIR/syncrain" "${XDG_CACHE_HOME:-$HOME/.cache}/syncrain")
  # the records a way back kept because it could not finish (Plasma's shell did not answer, its
  # config could not be written) are what running it again needs: the state folder stays with them
  kept=""
  for f in "$state/handover.json" "$state"/*.before-syncrain; do
    if [ -e "$f" ]; then kept=1; fi
  done
  if [ -n "$kept" ]; then info "kept $state: it holds what --login-screen-off or --lock-screen-off needs to put Plasma's settings back"
  else gone+=("$state"); fi
  for f in "${gone[@]}"; do
    if [ -e "$f" ] || [ -L "$f" ]; then rm -rf -- "$f"; info "removed $f"; fi
  done
  conf="${XDG_CONFIG_HOME:-$HOME/.config}/syncrain"
  if [ -d "$conf" ]; then info "kept your settings: $conf (remove it yourself if you do not want them)"; fi
  info "the system's packages were left installed: ${PACKAGES[*]} ${LAYER_PACKAGES[*]} ${BUILD_PACKAGES[*]}"
  exit 0
fi

[ -f "$SRC/syncrain/app.py" ] || die "run this script from the syncrain folder (it needs syncrain/app.py next to it)"
[ -f "$SRC/BUILD_NUMBER" ] || die "this folder has no BUILD_NUMBER, so it is not a syncrain release; use the folder unpacked from SYNCRAIN<N>.tar.zst"
BUILD="$(tr -d '[:space:]' < "$SRC/BUILD_NUMBER")"
[ "$(id -u)" = 0 ] && printf '\033[33mnote:\033[0m running as root installs syncrain for root only; normally run it as your user.\n'

# ---- 1. system packages
if [ "$NODEPS" = 0 ]; then
  if [ -z "$PKG_TOOL" ] || ! command -v "${PKG_TOOL/apt/apt-get}" >/dev/null; then
    die "this system is none of the four families install.sh knows (Arch, Debian, Fedora, openSUSE). Install these yourself, then run ./install.sh --no-deps: ${PACKAGES[*]}; ${LAYER_PACKAGES[*]}; to build the native wallpaper ${BUILD_PACKAGES[*]}. Or hand this folder to your AI agent and let it adapt install.sh to your system."
  fi
  wanted=("${PACKAGES[@]}" "${BUILD_PACKAGES[@]}")
  if [ "$LOCK" = 1 ] || lock_screen_installed; then wanted+=("${LOCK_PACKAGES[@]}"); fi
  pkg_missing "${wanted[@]}"
  if [ ${#MISSING[@]} -gt 0 ]; then
    hint="$(immutable_hint "${MISSING[@]}" "${LAYER_PACKAGES[@]}")"
    [ -z "$hint" ] || die "$hint"
    bold "Installing packages ($PKG_TOOL): ${MISSING[*]}"
    pkg_install_checked "the packages" "${MISSING[@]}"
  else
    bold "All packages are already installed"
  fi
  # gtk4-layer-shell on its own: a release without it still gets the native wallpaper
  pkg_missing "${LAYER_PACKAGES[@]}"
  if [ ${#MISSING[@]} -gt 0 ]; then
    pkg_install "${MISSING[@]}" \
      || info "gtk4-layer-shell is not available here (${MISSING[*]}): on Wayland the native wallpaper draws; the GTK host only on X11 or with --window"
  fi
fi

# ---- 2. sanity check: the Python bindings load
PY="$(pick_python)"                   # the packages may have just gone into the system's Python
"$PY" - <<'EOF' || die "the Python dependencies did not load in $PY (see above; SYNCRAIN_PYTHON picks another)"
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: F401
import ctypes
ctypes.CDLL("libepoxy.so.0")  # GTK's OpenGL loader, which syncrain calls OpenGL through
import PIL  # noqa: F401
import cairo  # noqa: F401
try:
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gtk4LayerShell
    Gtk4LayerShell.get_major_version()  # loads its library, which a typelib alone does not bring
except Exception:  # noqa: BLE001 - ValueError: none; GLib.Error: the typelib without its library
    print("  note: gtk4-layer-shell is missing, so on Wayland only the native wallpaper can draw; "
          "the GTK host and the login screen's box run on X11 or with --window")
EOF

# ---- 3. the app
# Made beside the installed one (APPDIR.new) and swapped in whole: an upgrade that stops half way
# leaves the installed app as it was. A folder is only ever replaced or removed when it is this
# script's install, never a checkout that happens to be where the app goes.
ours_to_replace "$APPDIR"
if [ -f "$APPDIR/BUILD_NUMBER" ]; then
  OLD="$(tr -d '[:space:]' < "$APPDIR/BUILD_NUMBER")"
  if [ "$OLD" = "$BUILD" ]; then bold "Reinstalling syncrain build $BUILD into $APPDIR"
  else bold "Upgrading syncrain from build $OLD to build $BUILD in $APPDIR"; fi
elif [ -d "$APPDIR" ]; then
  bold "Replacing an earlier syncrain (from before build numbers) with build $BUILD in $APPDIR"
else
  bold "Installing syncrain build $BUILD into $APPDIR"
fi
STAGE="$APPDIR.new"
rm -rf "$STAGE"
trap '[ -e "$APPDIR" ] || [ ! -e "$APPDIR.old" ] || mv "$APPDIR.old" "$APPDIR"; rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE" "$BINDIR"
cp -r "$SRC/syncrain" "$STAGE/"
find "$STAGE" -name '__pycache__' -type d -prune -exec rm -rf {} +
for f in BUILD_NUMBER README.md LICENSE; do [ -f "$SRC/$f" ] && cp "$SRC/$f" "$STAGE/"; done
if [ -f "$SRC/index.html" ]; then cp "$SRC/index.html" "$STAGE/"; fi
: > "$STAGE/$MARKER"

# The native wallpaper (syncrain/native/) draws on Wayland with neither Python nor GTK in memory.
# Without it, the Python and GTK host draws the same frames, as before. One built in the source
# folder by hand goes first: when this build fails, no other build's program stays behind.
rm -f "$STAGE/syncrain/native/syncrain-wallpaper"
if log="$(sh "$STAGE/syncrain/native/build.sh" "$STAGE/syncrain/native/syncrain-wallpaper" 2>&1)"; then
  info "native wallpaper: built"
else
  printf '\033[33mnote:\033[0m the native wallpaper did not build, so the Python and GTK host draws instead (it is built with: %s):\n' "${BUILD_PACKAGES[*]}"
  printf '%s\n' "$log" | tail -n 6 | sed 's/^/    /'
fi
# The options for the service and the settings file are checked as the new app reads them, before
# anything is swapped or kept: a misspelt preset in the service would only stop it at every login.
ARGS=()
# --option=value: a channel that starts with "-" is then no option
[ -n "$THEME" ] && ARGS+=("--preset=$THEME")
[ -n "$CHANNEL" ] && ARGS+=("--channel=$CHANNEL")
[ -n "$RAINBOW" ] && ARGS+=("--rainbow=$RAINBOW")
ARGS+=("${EXTRA[@]}")
staged() { PYTHONPATH="$STAGE" PYTHONSAFEPATH=1 "$PY" -m syncrain "$@"; }
staged --config none --build >/dev/null || die "the new app does not run in $PY (see above)"
if [ -n "$CONFIG" ]; then
  staged --config "$CONFIG" "${ARGS[@]}" --check-config >/dev/null \
    || die "$CONFIG${ARGS[*]:+ or these options (${ARGS[*]})} cannot be used (see above)"
elif [ ${#ARGS[@]} -gt 0 ]; then
  staged "${ARGS[@]}" --check-config >/dev/null \
    || die "these options (${ARGS[*]}) or your settings file (${XDG_CONFIG_HOME:-$HOME/.config}/syncrain/config.json) cannot be used (see above)"
fi

rm -rf "$APPDIR.old"
if [ -d "$APPDIR" ]; then mv "$APPDIR" "$APPDIR.old"; fi
mv "$STAGE" "$APPDIR"
rm -rf "$APPDIR.old"
trap - EXIT

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
exec "\${SYNCRAIN_PYTHON:-$PY}" -m syncrain "\$@"
EOF
chmod +x "$BINDIR/syncrain"
"$BINDIR/syncrain" --config none --build >/dev/null || die "the launcher does not run"
info "launcher: $BINDIR/syncrain ($("$BINDIR/syncrain" --config none --build))"

# The settings file the web page exported: checked above as the wallpaper reads it, then kept where it
# looks. Options given to this installer still go over it; a service written by an earlier
# install is written again, so options it kept from then do not.
if [ -n "$CONFIG" ]; then
  settings="${XDG_CONFIG_HOME:-$HOME/.config}/syncrain/config.json"
  mkdir -p "$(dirname "$settings")"
  # the file itself given again (edited where it is) is kept as it is; another one replaces it
  # whole, through a new file, so a link in its place (dotfiles) is replaced and not written through
  if ! [ "$CONFIG" -ef "$settings" ]; then
    if [ -f "$settings" ] && [ "$(cat "$settings")" != "$(cat "$CONFIG")" ]; then cp "$settings" "$settings.before"; fi
    cp "$CONFIG" "$settings.new"
    mv -f "$settings.new" "$settings"
  fi
  info "settings: $settings (from $CONFIG)"
fi

remove_plasma_wallpaper

# ---- 4. autostart
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

# The lock screen before the wallpaper's (re)start below: the started wallpaper then writes the lock
# screen's scene last, with the service's own options.
if [ "$LOCK" = 1 ]; then lock_screen_on; else lock_screen_refresh; fi

# The service: written with --autostart, and again at every install where it is (a fix to it reaches
# an upgrade). Its options are the ones given now; with none given (and no new settings file, which
# decides instead), the ones it had.
if [ "$AUTOSTART" = 1 ] || [ -f "$UNIT" ]; then
  exec_line="$(unit_words "$BINDIR/syncrain" "${ARGS[@]}")"
  was=""
  if [ -f "$UNIT" ]; then was="$(sed -n 's/^ExecStart=//p' "$UNIT" | head -n 1)"; fi
  if [ -n "$was" ] && [ ${#ARGS[@]} -eq 0 ] && [ -z "$CONFIG" ]; then
    # the options it had, after this install's launcher: a service another prefix wrote would
    # otherwise go on starting that install's build
    launcher="$(printf '%s' "$was" | sed -E "s/^('[^']*'|\"[^\"]*\"|[^ '\"]+)( +|$).*/\1/")"
    rest="${was#"$launcher"}"; rest="${rest# }"
    exec_line="$(unit_words "$BINDIR/syncrain")${rest:+ $rest}"
    if [ "$launcher" != "$(unit_words "$BINDIR/syncrain")" ]; then
      info "the service started $launcher; it now starts $BINDIR/syncrain"
    fi
  elif [ -n "$was" ] && [ "$was" != "$exec_line" ]; then
    case "$was" in
      *" "*) info "the service's options from before go: $was (give them again to keep one)" ;;
    esac
  fi
  if [ "$AUTOSTART" = 1 ]; then bold "Setting up autostart"; fi
  mkdir -p "$UNITDIR"
  cat > "$UNIT.new" <<EOF
[Unit]
Description=syncrain live wallpaper
PartOf=graphical-session.target
After=graphical-session.target
# a compositor or GPU that comes back after minutes still gets its wallpaper (the restarts slow
# down to one in two minutes); a failure no restart mends ends after 30 tries in ten minutes
StartLimitIntervalSec=600
StartLimitBurst=30

[Service]
ExecStart=$exec_line
Restart=on-failure
RestartSec=3
RestartSteps=10
RestartMaxDelaySec=120
# statuses a restart cannot change, so it would only start the same failure every 3 s: 69 no OpenGL here,
# 2 no wallpaper layer (GNOME) or an option it cannot use, 70 a native wallpaper from another build,
# 78 a picture or font it cannot use (syncrain --diagnose says why)
RestartPreventExitStatus=2 69 70 78

[Install]
WantedBy=graphical-session.target
EOF
  # lines added to it by hand (a key syncrain does not write) would be lost with each install: the
  # file is kept beside it
  own='^(\[(Unit|Service|Install)\]|(Description|PartOf|After|StartLimitIntervalSec|StartLimitBurst|ExecStart|Restart|RestartSec|RestartSteps|RestartMaxDelaySec|RestartPreventExitStatus|WantedBy)=.*|#.*|[[:space:]]*)$'
  if [ -f "$UNIT" ] && grep -qvE "$own" "$UNIT"; then
    cp "$UNIT" "$UNIT.before"
    info "the service file had lines of its own, kept in $UNIT.before; lasting changes go in a drop-in: systemctl --user edit syncrain"
  fi
  mv -f "$UNIT.new" "$UNIT"
  if have_user_systemd; then
    systemctl --user daemon-reload
    if [ "$AUTOSTART" = 1 ]; then
      systemctl --user enable syncrain.service >/dev/null 2>&1 && info "enabled: starts with your next graphical login"
    fi
    # A running one restarts on the new build wherever it was started. A stopped one starts only in a
    # graphical session, with --autostart, or after a failure (its cause may be mended) when it is
    # still enabled: one turned off stays off.
    if systemctl --user is-active --quiet syncrain.service; then
      systemctl --user restart syncrain.service && info "restarted, on build $BUILD"
    elif systemctl --user is-active --quiet graphical-session.target \
        && { [ "$AUTOSTART" = 1 ] || { systemctl --user is-failed --quiet syncrain.service \
             && systemctl --user is-enabled --quiet syncrain.service; }; }; then
      systemctl --user reset-failed syncrain.service >/dev/null 2>&1 || true
      systemctl --user restart syncrain.service && info "started now, on build $BUILD"
    fi
  elif [ "$AUTOSTART" = 1 ]; then
    info "wrote $UNIT; enable it from your desktop session with: systemctl --user enable --now syncrain.service"
  fi
fi

if [ "$LOGIN" = 1 ]; then login_screen_on; else login_screen_refresh; fi

# ---- 5. what next
desktop="${XDG_CURRENT_DESKTOP:-}"
echo
bold "Done. Try it:"
info "syncrain --window        preview in a normal window"
info "syncrain                 run as your wallpaper (Ctrl+C stops it)"
info "index.html (in this folder): try every setting, then ./install.sh --config config.json; syncrain --help for all options"
info "syncrain --diagnose      if it does not draw: what this machine offers, and why"
case ":$PATH:" in *":$BINDIR:"*) ;; *) info "note: $BINDIR is not on your PATH; run $BINDIR/syncrain or add it to PATH" ;; esac
case "$desktop" in
  *KDE*) info "KDE Plasma: syncrain sits just above Plasma's desktop, so desktop icons and widgets are hidden behind it (clicks still reach the desktop)."
         info "To keep the icons, show $APPDIR/index.html?hud=0 with a Plasma wallpaper plugin for web pages instead." ;;
  *Hyprland*) [ "$AUTOSTART" = 1 ] && info "Hyprland: if it doesn't start at login, add 'exec-once = $BINDIR/syncrain$(quote "${ARGS[@]}")' to hyprland.conf (or log in through UWSM)." ;;
  *sway*|*Sway*) [ "$AUTOSTART" = 1 ] && info "Sway: if it doesn't start at login, add 'exec $BINDIR/syncrain$(quote "${ARGS[@]}")' to your sway config." ;;
  *GNOME*) info "GNOME has no wallpaper layer for apps; use 'syncrain --window' or open $APPDIR/index.html in a browser." ;;
esac
info "uninstall: ./install.sh --uninstall"
