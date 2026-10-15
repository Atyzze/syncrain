"""From the login screen to the desktop without a seam (install.sh --login-screen).

After a login Plasma shows its splash screen, then its own wallpaper until syncrain's service draws.
Both become one still frame of the rain: a splash package of syncrain's (Plasma/LookAndFeel with only
a splash) and the image wallpaper of every desktop. What they were before is kept, so `off` puts it
back. Runs as the operator, inside their Plasma session (the wallpaper is set through plasmashell).

    python -m syncrain.handover on [rain options]    # make the still, set splash and wallpaper
    python -m syncrain.handover still [rain options] # make the still again (a newer build), nothing else
    python -m syncrain.handover off                   # put back the splash and wallpapers still on it
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SPLASH = "org.syncrain.splash"
SPLASH_QML = """import QtQuick

// syncrain's splash: the still frame of the rain the desktop's wallpaper also shows, so the login
// screen's rain, this and the desktop's rain follow each other without a seam.
Rectangle {
    color: "black"
    property int stage
    Image {
        anchors.fill: parent
        source: "images/still.png"
        fillMode: Image.PreserveAspectCrop
    }
}
"""


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def state_path() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    return base / "syncrain" / "handover.json"


def still_path() -> Path:
    return data_home() / "wallpapers" / "syncrain.png"


# ------------------------------------------------------------------ KDE's ini files (ksplashrc)

def read_ini(path: Path, group: str, key: str) -> str | None:
    inside = False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        s = line.strip()
        if s.startswith("["):
            inside = s == f"[{group}]"
        elif inside and "=" in s and s.split("=", 1)[0].strip() == key:
            return s.split("=", 1)[1].strip()
    return None


def write_ini(path: Path, group: str, key: str, value: str | None) -> None:
    """Set (or with None, remove) one key, leaving the rest of the file as it was."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    out, inside, done, seen = [], False, False, False
    for line in lines:
        s = line.strip()
        if s.startswith("["):
            if inside and not done and value is not None:
                out.append(f"{key}={value}")
                done = True
            inside = s == f"[{group}]"
            seen = seen or inside
        elif inside and "=" in s and s.split("=", 1)[0].strip() == key:
            if value is not None and not done:
                out.append(f"{key}={value}")
            done = True
            continue
        out.append(line)
    if not done and value is not None:
        if not seen:
            out += (["", f"[{group}]"] if out else [f"[{group}]"])
        out.append(f"{key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ Plasma's shell

def plasma_script(script: str) -> str:
    """Run a Plasma desktop script in the running shell; what it printed."""
    from gi.repository import Gio, GLib
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    reply = bus.call_sync("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell", "evaluateScript",
                          GLib.Variant("(s)", (script,)), GLib.VariantType("(s)"), Gio.DBusCallFlags.NONE,
                          20000, None)
    return reply.unpack()[0]


READ_WALLPAPERS = """var out = [];
desktops().forEach(function (d) {
    d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    out.push([d.wallpaperPlugin, d.readConfig("Image", ""), d.id]);
});
print(JSON.stringify(out));"""


def set_wallpapers_script(entries: list) -> str:
    """Each desktop on the entry ([plugin, image, id]) with its id; one without, on the entry at its
    place in the list (or the last)."""
    return f"""var want = {json.dumps(entries)};
desktops().forEach(function (d, i) {{
    var w = want[Math.min(i, want.length - 1)];
    want.forEach(function (e) {{ if (e.length > 2 && e[2] === d.id) w = e; }});
    d.wallpaperPlugin = w[0];
    if (w[0] === "org.kde.image") {{   // an empty Image is Plasma's default wallpaper
        d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
        d.writeConfig("Image", w[1]);
    }}
}});"""


# ------------------------------------------------------------------ the still frame

def screen_size() -> str:
    """The largest screen, as WxH in the units a window's --size is in (1920x1080 when GTK cannot say)."""
    probe = ("import gi; gi.require_version('Gdk', '4.0'); gi.require_version('Gtk', '4.0');"
             "from gi.repository import Gdk, Gtk; Gtk.init(); d = Gdk.Display.get_default(); m = d.get_monitors();"
             "s = [(g.width, g.height) for x in"
             " (m.get_item(i) for i in range(m.get_n_items())) for g in [x.get_geometry()]];"
             "print('%dx%d' % max(s, key=lambda v: v[0] * v[1]) if s else '')")
    try:
        done = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=30)
        size = done.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        size = ""
    return size or "1920x1080"


def make_still(rain: list[str], path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "syncrain", *rain, "--window", "--size", screen_size(), "--screenshot", str(path)]
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        why = (done.stdout + done.stderr).strip()[-300:] if done.returncode != 0 or not path.is_file() else ""
    except (OSError, subprocess.TimeoutExpired) as e:
        why = str(e)
    if why:
        print(f"syncrain: the still frame was not made: {why}", file=sys.stderr)
        return False
    return True


def write_splash(still: Path) -> Path:
    root = data_home() / "plasma" / "look-and-feel" / SPLASH
    images = root / "contents" / "splash" / "images"
    images.mkdir(parents=True, exist_ok=True)
    (root / "metadata.json").write_text(json.dumps({
        "KPackageStructure": "Plasma/LookAndFeel",
        "KPlugin": {"Id": SPLASH, "Name": "syncrain", "Description": "A still frame of syncrain's rain",
                    "License": "MIT", "Category": ""},
        "X-Plasma-APIVersion": "2"}, indent=1), encoding="utf-8")
    (root / "contents" / "splash" / "Splash.qml").write_text(SPLASH_QML, encoding="utf-8")
    (images / "still.png").write_bytes(still.read_bytes())
    return root


# ------------------------------------------------------------------ on and off

def on(rain: list[str], shell=plasma_script) -> list[str]:
    """What was done, line by line."""
    said = []
    still = still_path()
    if not make_still(rain, still):
        return ["the still frame could not be made; splash and wallpaper left as they were"]
    write_splash(still)
    state = state_path()
    try:
        before = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        before = {}
    rc = config_home() / "ksplashrc"
    # Run again (an upgrade, other options), what was chosen since the first run stays: only what
    # still shows syncrain's still, or was never recorded, becomes it.
    if "splash" not in before:
        # syncrain's own splash, left by a run that broke off, is not what to go back to: Plasma's is
        ours = read_ini(rc, "KSplash", "Theme") == SPLASH
        before["splash"] = {k: None if ours else read_ini(rc, "KSplash", k) for k in ("Engine", "Theme")}
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps(before, indent=1), encoding="utf-8")     # kept before anything changes
        again = False
    else:
        again = True
    if not again or read_ini(rc, "KSplash", "Theme") == SPLASH:
        write_ini(rc, "KSplash", "Engine", "KSplashQML")
        write_ini(rc, "KSplash", "Theme", SPLASH)
        said.append("splash after login: the still frame")
    else:
        said.append("splash after login: the one chosen since stays")
    try:
        uri = still.as_uri()
        now = json.loads(shell(READ_WALLPAPERS) or "[]")
        if "wallpapers" not in before:
            # our own still, left by an earlier build, is not worth going back to: Plasma's default is
            before["wallpapers"] = [[e[0], "" if e[1] == uri else e[1], *e[2:]] for e in now]
            want, kept = [["org.kde.image", uri]], 0
        else:
            known = {e[2] for e in before["wallpapers"] if len(e) > 2}
            want, kept = [], 0
            for e in now:
                if len(e) > 2 and e[2] not in known:             # a desktop new since: recorded too
                    before["wallpapers"].append([e[0], "" if e[1] == uri else e[1], *e[2:]])
                    want.append(["org.kde.image", uri, e[2]])
                elif e[0] == "org.kde.image" and e[1] == uri:
                    want.append(["org.kde.image", uri, *e[2:]])
                else:
                    want.append(list(e))
                    kept += 1
        if want:
            shell(set_wallpapers_script(want))
        said.append("Plasma's wallpaper: the same still frame, under the rain" if not kept else
                    f"Plasma's wallpaper: the still frame where it was; {kept} chosen since stay")
    except Exception as e:  # noqa: BLE001 - no Plasma shell answering is said, not fatal
        said.append(f"Plasma's wallpaper not changed (its shell did not answer: {getattr(e, 'message', e)})")
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps(before, indent=1), encoding="utf-8")
    return said


def still(rain: list[str]) -> list[str]:
    """A newer build's still frame, into the same file and the splash: the splash and the
    wallpapers stay as the operator has them now (they may have chosen others since)."""
    if not make_still(rain, still_path()):
        return ["the still frame could not be made again; the one from before stays"]
    if (data_home() / "plasma" / "look-and-feel" / SPLASH).is_dir():
        write_splash(still_path())
    return ["the still frame: made again"]


def off(shell=plasma_script) -> list[str]:
    said = []
    state = state_path()
    rc = config_home() / "ksplashrc"
    package = data_home() / "plasma" / "look-and-feel" / SPLASH
    import shutil
    try:
        before = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        if read_ini(rc, "KSplash", "Theme") == SPLASH:           # the record went; the splash is ours
            write_ini(rc, "KSplash", "Theme", None)
            write_ini(rc, "KSplash", "Engine", None)
            said.append("splash after login: Plasma's own")
        shutil.rmtree(package, ignore_errors=True)
        return said
    # Only what still shows syncrain's: a splash or wallpaper chosen since stays.
    if read_ini(rc, "KSplash", "Theme") == SPLASH:
        splash = before.get("splash") or {}
        for key in ("Engine", "Theme"):
            write_ini(rc, "KSplash", key, splash.get(key))
        said.append("splash after login: as before")
    else:
        said.append("splash after login: the one chosen since stays")
    if before.get("wallpapers"):
        try:
            now = json.loads(shell(READ_WALLPAPERS) or "[]")
            uri = still_path().as_uri()
            shell(set_wallpapers_script(back_to(before["wallpapers"], now, uri)))
            chosen = sum(1 for e in now if not (e[0] == "org.kde.image" and e[1] == uri))
            said.append("Plasma's wallpaper: as before" if not chosen else
                        f"Plasma's wallpaper: as before where the still was; {chosen} chosen since stay")
        except Exception as e:  # noqa: BLE001
            # The still and the record stay, so a run from inside Plasma can still put them back.
            said.append(f"Plasma's wallpaper not put back (its shell did not answer: {getattr(e, 'message', e)});"
                        " run ./install.sh --login-screen-off again from your Plasma session")
            shutil.rmtree(package, ignore_errors=True)
            return said
    shutil.rmtree(package, ignore_errors=True)
    still_path().unlink(missing_ok=True)
    state.unlink(missing_ok=True)
    return said


def back_to(before: list, now: list, still_uri: str) -> list:
    """The wallpaper for each desktop now: the one from before where the still is, else as it is."""
    out = []
    for i, entry in enumerate(now):
        if entry[0] == "org.kde.image" and entry[1] == still_uri:
            same = [e for e in before if len(e) > 2 and len(entry) > 2 and e[2] == entry[2]]
            out.append(list(same[0] if same else before[min(i, len(before) - 1)] if before else ["org.kde.image", ""]))
        else:
            out.append(list(entry))
    return out


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["on"]:
        lines = on(argv[1:])
    elif argv[:1] == ["still"]:
        lines = still(argv[1:])
    elif argv[:1] == ["off"]:
        lines = off()
    else:
        print(__doc__)
        return 2
    for line in lines:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
