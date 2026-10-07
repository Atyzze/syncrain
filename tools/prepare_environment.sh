#!/usr/bin/env bash
# Check a build sandbox for everything the test lanes and the release need, and say what is missing.
#
#   tools/prepare_environment.sh --verify           check only; changes nothing (exit 1 if anything is missing)
#   tools/prepare_environment.sh --venv <dir>       also create <dir> as a venv with the Python packages
#
# The full sequence that worked, and the traps: docs/agent/ENVIRONMENT.md.
set -uo pipefail

VENV=""
case "${1:-}" in
  --verify|"") ;;
  --venv) VENV="${2:?--venv needs a directory}" ;;
  -h|--help) sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
esac

if [ -n "$VENV" ]; then
  [ -x "$VENV/bin/python" ] || python3 -m venv "$VENV" || exit 1
  "$VENV/bin/pip" install -q PyGObject PyOpenGL Pillow pycairo pytest pyflakes "setuptools>=64" wheel || exit 1
  export PATH="$VENV/bin:$PATH"
fi

missing=0
ok()   { printf '  ok       %s\n' "$*"; }
miss() { printf '  MISSING  %s\n' "$*"; missing=1; }
check_bin() { if command -v "$1" >/dev/null; then ok "$1 ($2)"; else miss "$1 ($2): $3"; fi; }

echo "python: $(command -v python3) $(python3 -c 'import sys; print(sys.version.split()[0])' 2>/dev/null)"
python3 - <<'PYCHECK' || missing=1
import importlib, sys
bad = 0
def check(label, fn, lane):
    global bad
    try:
        fn()
        print(f"  ok       {label} ({lane})")
    except Exception as exc:
        print(f"  MISSING  {label} ({lane}): {exc}")
        bad = 1
if sys.version_info < (3, 11):
    print("  MISSING  Python 3.11 or later (every lane)"); bad = 1
def gtk():
    import gi; gi.require_version("Gtk", "4.0"); from gi.repository import Gtk  # noqa: F401
def layer():
    import gi; gi.require_version("Gtk4LayerShell", "1.0")
check("PyGObject with GTK 4", gtk, "every lane")
for module, lane in (("OpenGL", "render"), ("PIL", "every lane"), ("cairo", "installer"), ("pytest", "every lane"),
                     ("setuptools", "release"), ("wheel", "release")):
    check(module, lambda m=module: importlib.import_module(m), lane)
check("gtk4-layer-shell typelib (GI_TYPELIB_PATH)", layer, "wayland")
sys.exit(bad)
PYCHECK

check_bin Xvfb render "apt install xvfb / pacman -S xorg-server-xvfb"
check_bin sway wayland "apt install sway / pacman -S sway"
check_bin grim wayland "apt install grim / pacman -S grim"
check_bin shellcheck unit "apt install shellcheck / pacman -S shellcheck"
check_bin zstd release "apt install zstd"
check_bin node browser "node 22 (the sandbox has /opt/node22/bin)"
if command -v node >/dev/null; then
  if NODE_PATH="${NODE_PATH:-$(npm root -g 2>/dev/null)}" node -e "require('playwright')" 2>/dev/null; then
    ok "playwright for node (browser)"
  else
    miss "playwright for node (browser): npm i -g playwright"
  fi
fi
check_bin nix-instantiate nix "Nix, in /nix/var/nix/profiles/default/bin"
check_bin nix-build nix "Nix"
for var in SYNCRAIN_NIXPKGS SYNCRAIN_HOME_MANAGER; do
  if [ -d "${!var:-/nonexistent}" ]; then ok "$var=${!var} (nix)"; else miss "$var (nix): a local checkout, see docs/agent/ENVIRONMENT.md"; fi
done
check_bin dbus-daemon kwin "apt install dbus / pacman -S dbus"
check_bin dbus-send kwin "apt install dbus / pacman -S dbus"
if [ -x "${SYNCRAIN_KWIN:-/nonexistent}" ]; then
  ok "SYNCRAIN_KWIN=$SYNCRAIN_KWIN (kwin)"
elif command -v kwin_wayland >/dev/null; then
  ok "kwin_wayland on PATH (kwin; it must be KWin 6)"
else
  miss "SYNCRAIN_KWIN (kwin): nix build --no-link --print-out-paths -f \"\$SYNCRAIN_NIXPKGS\" kdePackages.kwin, then <path>/bin/kwin_wayland"
fi

typelib=/usr/local/lib/x86_64-linux-gnu/girepository-1.0
if [ -f "$typelib/Gtk4LayerShell-1.0.typelib" ] && [[ ":${GI_TYPELIB_PATH:-}:" != *":$typelib:"* ]]; then
  echo "hint: export GI_TYPELIB_PATH=$typelib"
fi
if [ "$missing" = 0 ]; then echo "everything the lanes and the release need is here"; else echo "the release needs every line above to be ok"; fi
exit "$missing"
