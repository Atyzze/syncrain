#!/usr/bin/env bash
# syncrain installer for Arch-based systems (Arch, CachyOS, EndeavourOS, Manjaro, Garuda, ...)
#
#   ./install.sh                     install this build for your user (asks for sudo once, for pacman packages)
#   ./install.sh --autostart         ...and start it with every graphical login
#   ./install.sh --theme matrix --channel friends --autostart
#   ./install.sh --config config.json  ...and draw what the web page showed (the settings it exported)
#   ./install.sh --login-screen      ...and the rain as your login screen too (optional; greetd, yours stays installed)
#   ./install.sh --login-screen-off  back to the login screen you had (undoes only what --login-screen did)
#   ./install.sh --uninstall         remove it again (pacman packages are left installed)
#
# Run from a newer build's folder, it upgrades in place and restarts a running wallpaper.
# Everything goes into your home directory:
#   ~/.local/share/syncrain/                 the app (plus web/index.html, the browser version)
#   ~/.local/bin/syncrain                    the launcher
#   ~/.config/systemd/user/syncrain.service  only with --autostart
set -euo pipefail

PACKAGES=(python python-gobject python-cairo python-pillow gtk4 gtk4-layer-shell)
# what the native wallpaper is built with (syncrain/native/build.sh); wayland and dbus are on every Plasma desktop
BUILD_PACKAGES=(gcc pkgconf wayland dbus)
PREFIX="${PREFIX:-$HOME/.local}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART=0 UNINSTALL=0 NODEPS=0 YES=0 LOGIN=0 LOGIN_OFF=0
THEME="" CHANNEL="" RAINBOW="" CONFIG="" EXTRA=()

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  cat <<'EOF'

Options:
  --autostart           start with every graphical login (systemd user service)
  --login-screen        optional: the rain and a login box as the login screen, from the next boot
                        (greetd); without it the installer never touches your login screen
  --login-screen-off    back to the login screen from before (undoes only what --login-screen did)
  --config FILE         a settings file the web page exported: the wallpaper (and the login screen)
                        draw what the page showed; kept as ~/.config/syncrain/config.json
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
    --login-screen) LOGIN=1 ;;
    --login-screen-off) LOGIN_OFF=1 ;;
    --theme) THEME="${2:?--theme needs a value}"; shift ;;
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

APPDIR="$PREFIX/share/syncrain"
BINDIR="$PREFIX/bin"
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
# elsewhere. GNU tar does not follow a link from the stream out of the folder, and the files are root's.
copy_app_to_root() {
  tar -C "$APPDIR" -cf - syncrain | as_root tar -C "$1" -xf - --no-same-owner --no-same-permissions
  # the app is files, folders and links; a stream could make devices and pipes, which go
  as_root find "$1" ! -type f ! -type d ! -type l -delete
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
  [ -f "$1" ] && python3 -c 'import json, sys; sys.exit(0 if isinstance(json.load(open(sys.argv[1], encoding="utf-8")).get("glyphs"), dict) else 1)' "$1" 2>/dev/null
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
handover() { PYTHONPATH="$1" PYTHONSAFEPATH=1 python3 -m syncrain.handover "${@:2}"; }
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
  python3 -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("user", ""))' \
    "$LOGIN_LIB/login.json" 2>/dev/null || true
}
mine() { [ -f "$LOGIN_LIB/login.json" ] && [ "$(login_user)" = "$(id -un)" ]; }

# A file of the system's, read as this user where it can be (greetd's config and PAM files are).
read_system_file() { if [ -r "$1" ]; then cat -- "$1"; elif [ -e "$1" ]; then as_root cat -- "$1"; fi; }
greetdconf() {
  local lib="$SRC"
  [ -f "$lib/syncrain/greetdconf.py" ] || lib="$APPDIR"
  PYTHONPATH="$lib" PYTHONSAFEPATH=1 python3 -m syncrain.greetdconf "$@"
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
PAM_MARK="written by syncrain's install.sh --login-screen"
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
  # instead of a black screen.
  local login="$LOGIN_LIB/syncrain/login/login.sh" base="$GREETD_CONFIG" edited pam greeter_pam
  if grep -qs syncrain "$GREETD_CONFIG" && ! grep -qsF "$CONFIG_MARK" "$GREETD_CONFIG"; then
    base="$GREETD_CONFIG.before-syncrain"
  fi
  edited="$(mktemp)"
  if ! read_system_file "$base" | greetdconf config \
      "sh -c 'test -x $login && exec $login; exec agreety --cmd startplasma-wayland'" greeter > "$edited"; then
    rm -f "$edited"
    die "greetd's config ($base) could not be changed, so it stays as it is"
  fi
  copy_to_root "$edited" "$GREETD_CONFIG"
  rm -f "$edited"
  pam="$(pam_file)"
  greeter_pam="$(greeter_pam_file)"
  # SDDM's PAM opens KDE's wallet (and GNOME's keyring) with the password typed at login; greetd's
  # does not, so without these the wallet would ask again. "-" skips a module that is not installed.
  if [ -f "$pam" ] && ! grep -q pam_kwallet5 "$pam"; then
    [ -f "$pam.before-syncrain" ] || as_root cp "$pam" "$pam.before-syncrain"
    printf '%s\n' "" "# added by syncrain's install.sh --login-screen: the wallet opens with the login, as under SDDM" \
      "-auth       optional    pam_gnome_keyring.so" "-auth       optional    pam_kwallet5.so" \
      "-session    optional    pam_gnome_keyring.so    auto_start" "-session    optional    pam_kwallet5.so         auto_start" \
      | as_root tee -a "$pam" >/dev/null
  fi
  # greetd runs its greeter under its own PAM service where that file exists, else under the users'
  # one: a file without the wallet lines keeps a wallet starting for the user greeter at every boot.
  if [ -f "$pam.before-syncrain" ] && [ ! -e "$greeter_pam" ] && [ "$greeter_pam" != "$pam" ]; then
    { printf '# %s: greetd'"'"'s greeter, without the wallet lines\n' "$PAM_MARK"; read_system_file "$pam.before-syncrain"; } \
      | as_root tee "$greeter_pam" >/dev/null
  fi
}

login_screen_on() {
  bold "Making the rain your login screen (greetd)"
  if [ "$NODEPS" = 0 ]; then
    local confirm=(); [ "$YES" = 1 ] && confirm=(--noconfirm)
    pacman -Qq greetd greetd-agreety >/dev/null 2>&1 \
      || as_root pacman -S --needed "${confirm[@]}" greetd greetd-agreety || die "pacman could not install greetd"
  fi
  command -v kwin_wayland >/dev/null || die "the login screen runs in KWin (Plasma's compositor), which is not installed"
  command -v agreety >/dev/null || die "greetd's text login (agreety, pacman: greetd-agreety) is missing; the login screen falls back to it"
  local tmp glyphs settings rain=("${ARGS[@]}") before now new="$LOGIN_LIB.new" f conf="${XDG_CONFIG_HOME:-$HOME/.config}"
  # A record counts while greetd starts at boot. Once something else does (picked since), that is
  # what comes before; with greetd running syncrain's config and no record, it is not known.
  before="$(recorded_before)"
  now="$(display_manager)"
  if [ "$now" != greetd.service ]; then before="$now"
  elif [ -z "$before" ]; then
    before=greetd.service
    if grep -qs syncrain "$GREETD_CONFIG"; then before=unknown; fi
  fi
  record_before "$before"
  tmp="$(mktemp -d)"
  # login.json: who logs in by default, and the rain's options as given to this installer
  glyphs="$conf/syncrain/glyphs.json" settings="$conf/syncrain/config.json"
  # a settings file's own sets go over a symbols file, as on the desktop (syncrain/greeter.py drops
  # --glyphs for them too, for a login.json written before the settings file)
  if [ -f "$glyphs" ] && ! settings_have_sets "$settings"; then
    cp "$glyphs" "$tmp/glyphs.json"; rain+=(--glyphs "$LOGIN_LIB/glyphs.json")
  fi
  write_login_json() {
    python3 -c 'import json, sys; json.dump({"user": sys.argv[2], "session": "plasma.desktop", "rain": sys.argv[3:]},
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
      python3 -m syncrain.greeter --draw-symbols || info "the symbols were not drawn now; the login screen draws them"
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
  local owner="${SYNCRAIN_LOGIN_OWNER:-greeter}"
  as_root install -d -m 755 -o "$owner" -g "$(id -gn "$owner")" "$LOGIN_STATE"
  clear_state_copies
  rm -rf "$tmp"
  info "the app: $LOGIN_LIB (user $(id -un), Plasma, the rain's options given to this installer)"

  apply_greetd
  as_root systemctl enable --force greetd.service >/dev/null || die "systemctl could not enable greetd"
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
    info "  or from a text console (Ctrl+Alt+F3): sudo systemctl enable --force $before && sudo reboot"
  fi
}

# Puts back only what --login-screen changed, and only when syncrain changed it: with no record, no
# app copy and no greetd config of syncrain's, the login screen is not syncrain's and stays as it is.
# What starts at boot changes only while greetd still does: a display manager picked since stays,
# and one that is gone leaves greetd with its own config rather than no way to log in. Run again
# (for the hand-over, from Plasma), it finds nothing more of the login screen to put back.
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
    pam="$(pam_file)"                           # the config before syncrain names the same services
    greeter_pam="$(greeter_pam_file)"
    if [ -f "$GREETD_CONFIG.before-syncrain" ] && grep -qs syncrain "$GREETD_CONFIG"; then
      as_root mv -f "$GREETD_CONFIG.before-syncrain" "$GREETD_CONFIG"
    fi
    if [ -f "$pam.before-syncrain" ] && grep -qs "added by syncrain" "$pam"; then
      as_root mv -f "$pam.before-syncrain" "$pam"
    fi
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
  info "the login screen: build $BUILD too"
  local rain=()
  # the login screen's options without its copy of the symbols file (here syncrain reads yours)
  mapfile -t rain < <(python3 -c '
import json, sys
args = json.load(open(sys.argv[1])).get("rain", [])
skip = {i + 1 for i, a in enumerate(args) if a == "--glyphs"} | {i for i, a in enumerate(args) if a == "--glyphs"}
[print(a) for i, a in enumerate(args) if i not in skip]' "$LOGIN_LIB/login.json" 2>/dev/null)
  # only the still frame again: the splash and wallpapers stay as the operator has them now
  if in_plasma && [ -f "$HANDOVER_STATE" ]; then
    handover "$APPDIR" still "${rain[@]}" >/dev/null || true
  fi
}

if [ "$LOGIN_OFF" = 1 ]; then
  login_screen_off
  exit 0
fi

if [ "$UNINSTALL" = 1 ]; then
  # syncrain's login screen goes too when this user set it up. Another user's stays, and without one
  # the login screen is not touched at all.
  if mine; then login_screen_off
  else
    if [ -f "$LOGIN_LIB/login.json" ]; then info "the login screen stays as $(login_user) set it up (--login-screen-off takes it out)"; fi
    if [ -f "$HANDOVER_STATE" ]; then handover_off; fi
  fi
  remove_plasma_wallpaper
  bold "Removing syncrain"
  if [ -f "$UNIT" ]; then
    if have_user_systemd; then systemctl --user disable --now syncrain.service >/dev/null 2>&1 || true; fi
    rm -f "$UNIT"
    if have_user_systemd; then systemctl --user daemon-reload || true; fi
    info "removed the autostart service"
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
  for p in "${PACKAGES[@]}" "${BUILD_PACKAGES[@]}"; do pacman -Qq "$p" >/dev/null 2>&1 || missing+=("$p"); done
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
"$BINDIR/syncrain" --config none --build >/dev/null || die "the launcher does not run"
info "launcher: $BINDIR/syncrain ($("$BINDIR/syncrain" --config none --build))"

# The settings file the web page exported: checked as the wallpaper reads it, then kept where it
# looks. Options given to this installer still go over it; a service written by an earlier
# install is written again, so options it kept from then do not.
if [ -n "$CONFIG" ]; then
  settings="${XDG_CONFIG_HOME:-$HOME/.config}/syncrain/config.json"
  "$BINDIR/syncrain" --config "$CONFIG" --check-config >/dev/null || die "$CONFIG cannot be used (see above)"
  mkdir -p "$(dirname "$settings")"
  # the file itself given again (edited where it is) is kept as it is; another one replaces it
  # whole, through a new file, so a link in its place (dotfiles) is replaced and not written through
  if ! [ "$CONFIG" -ef "$settings" ]; then
    if [ -f "$settings" ] && [ "$(cat "$settings")" != "$(cat "$CONFIG")" ]; then cp "$settings" "$settings.before"; fi
    cp "$CONFIG" "$settings.new"
    mv -f "$settings.new" "$settings"
  fi
  info "settings: $settings (from $CONFIG)"
  if [ -f "$UNIT" ]; then
    AUTOSTART=1
    was="$(sed -n 's/^ExecStart=//p' "$UNIT")"
    case "$was" in
      *" "*) info "the service's options from before go, so the settings file decides: $was (give them again with --arg to keep one)" ;;
    esac
  fi
fi

remove_plasma_wallpaper

# ---- 4. autostart
ARGS=()
# --option=value: a channel that starts with "-" is then no option
[ -n "$THEME" ] && ARGS+=("--theme=$THEME")
[ -n "$CHANNEL" ] && ARGS+=("--channel=$CHANNEL")
[ -n "$RAINBOW" ] && ARGS+=("--rainbow=$RAINBOW")
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
# statuses a restart cannot change, so it would only start the same failure every 3 s: 69 no OpenGL here,
# 2 no wallpaper layer (GNOME) or an option it cannot use, 70 a native wallpaper from another build,
# 78 a picture or font it cannot use (syncrain --diagnose says why)
RestartPreventExitStatus=2 69 70 78

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

if [ "$LOGIN" = 1 ]; then login_screen_on; else login_screen_refresh; fi

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
