#!/bin/sh
# syncrain's login screen, as greetd runs it (/etc/greetd/config.toml; user greeter).
# KWin takes the screens and runs session.sh: the rain and the login box (syncrain/greeter.py).
# The box hands the login to greetd, which starts the session once KWin is gone. If nobody got
# logged in that way (KWin or the box failed), greetd's own text login takes over, so a broken
# login screen still lets the operator in. What happened goes to the state folder's login.log.
LIB="$(cd "$(dirname "$0")/../.." && pwd)"

STATE="${SYNCRAIN_LOGIN_STATE:-/var/lib/syncrain-login}"
if ! { mkdir -p "$STATE" && [ -w "$STATE" ]; } 2>/dev/null; then
  # Elsewhere only in a folder of this user's own: one in /tmp that someone else made could hold a
  # KWin config of theirs, with a program in it that sees what is typed.
  STATE="${XDG_RUNTIME_DIR:-}/syncrain-login"
  if [ -z "${XDG_RUNTIME_DIR:-}" ] || ! { mkdir -p "$STATE" && [ -O "$STATE" ]; } 2>/dev/null; then
    STATE="$(mktemp -d /tmp/syncrain-login.XXXXXX)"
  fi
fi
LOG="$STATE/login.log"
[ -f "$LOG" ] && mv -f "$LOG" "$LOG.1"
# The greeter user's home is / (not writable): KWin's and syncrain's files live in the state folder.
export XDG_CONFIG_HOME="$STATE/config" XDG_CACHE_HOME="$STATE/cache" XDG_STATE_HOME="$STATE/state" \
       XDG_DATA_HOME="$STATE/data"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_STATE_HOME" "$XDG_DATA_HOME"
# The operator's screen and keyboard settings as installed now (a copy of one no longer installed
# goes), and the symbols drawn at install (drawing takes seconds).
for f in kwinoutputconfig.json kxkbrc kcminputrc; do rm -f "$XDG_CONFIG_HOME/$f"; done
[ -d "$LIB/kde" ] && cp -f "$LIB/kde/"* "$XDG_CONFIG_HOME/" 2>/dev/null
# Without the operator's keyboard layout, the system's (localectl) is the next best.
LOCALE1=--locale1
[ -f "$XDG_CONFIG_HOME/kxkbrc" ] && LOCALE1=""
[ -d "$LIB/cache" ] && mkdir -p "$XDG_CACHE_HOME/syncrain" && cp -f "$LIB/cache/"* "$XDG_CACHE_HOME/syncrain/" 2>/dev/null
export SYNCRAIN_LOGIN_STATE="$STATE" SYNCRAIN_LOGIN_MARKER="$STATE/logged-in"
export PYTHONPATH="$LIB" PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
rm -f "$SYNCRAIN_LOGIN_MARKER"

{ echo "syncrain-login: $(date '+%F %T') build $(cat "$LIB/BUILD_NUMBER" 2>/dev/null), user $(id -un)"; } > "$LOG"
# In a process group of its own, so the watchdog below can stop all of it.
# shellcheck disable=SC2086 # the arguments are words on purpose
setsid -w dbus-run-session -- "${SYNCRAIN_LOGIN_KWIN:-kwin_wayland}" \
  ${SYNCRAIN_LOGIN_KWIN_ARGS:---drm --no-lockscreen --no-global-shortcuts --no-kactivities $LOCALE1} \
  --exit-with-session "$LIB/syncrain/login/session.sh" >> "$LOG" 2>&1 &
kwin=$!
# greetd stops a greeter by signalling this script alone: when a login's session is due and the
# greeter is slow to go, and when greetd itself stops or restarts. KWin runs in a session of its own,
# so it is stopped here too, and gone before this script is (killed after 3 s, inside greetd's 10),
# or it would keep the screens from the session that follows.
stop_kwin() {
  trap '' TERM INT HUP                  # greetd may signal again; the deadline below holds anyway
  kill -TERM "-$kwin" 2>/dev/null
  (sleep 3; kill -KILL "-$kwin" 2>/dev/null) &
  wait "$kwin" 2>/dev/null              # dbus-run-session, at the head of KWin's session
  n=0
  while kill -0 "-$kwin" 2>/dev/null && [ "$n" -lt 30 ]; do sleep 0.1; n=$((n + 1)); done
  kill -KILL "-$kwin" 2>/dev/null
  exit 0
}
trap stop_kwin TERM INT HUP
# A KWin that hangs, or a box that never shows, would otherwise leave a black screen for good.
WAIT="${SYNCRAIN_LOGIN_WATCHDOG:-60}"
(
  n=0
  while kill -0 "$kwin" 2>/dev/null; do
    if [ "$n" -ge "$WAIT" ] && ! grep -q "box shown" "$LOG"; then
      echo "syncrain-login: no box after $WAIT s; stopping KWin" >> "$LOG"
      kill -TERM "-$kwin" 2>/dev/null
      sleep 5
      kill -KILL "-$kwin" 2>/dev/null
      break
    fi
    sleep 1
    n=$((n + 1))
  done
) &
wait "$kwin"
echo "syncrain-login: KWin ended with $?" >> "$LOG"
if [ -f "$SYNCRAIN_LOGIN_MARKER" ]; then
  exit 0
fi

echo "syncrain-login: nobody logged in through the box; greetd's text login takes over" >> "$LOG"
CMD="$("${SYNCRAIN_PYTHON:-python3}" -m syncrain.greeter --fallback-command 2>> "$LOG")" || CMD=""
exec "${SYNCRAIN_LOGIN_TEXT:-agreety}" --cmd "${CMD:-startplasma-wayland}"
