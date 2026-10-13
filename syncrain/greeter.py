"""syncrain's login screen: the rain on every screen and a small login box on top, as greetd's greeter.

greetd (a login daemon) runs syncrain/login/login.sh as the user `greeter`; that starts KWin on the
screens and, inside it, session.sh, which runs this. Here: the rain first (`python -m syncrain`, the
native wallpaper), then the box (GTK 4 on the overlay layer, gtk4-layer-shell). The box hands what
was typed to greetd (syncrain/greetd.py); greetd checks it with PAM and, once this greeter and its
KWin have gone, starts the chosen session (Plasma by default) as that user. A login writes the
marker file login.sh looks for; without it login.sh falls back to greetd's text login.

Settings: login.json beside the package (install.sh writes it): {"user", "session", "rain": [args]}.
The last login (user and session) is kept in the state folder, so the box offers it next time.
"""
from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from .greetd import Greetd

LIB = Path(__file__).resolve().parents[1]
#: Field codes a desktop file's Exec may hold; a login session gets no files or URLs.
FIELD_CODES = {"%f", "%F", "%u", "%U", "%d", "%D", "%n", "%N", "%i", "%c", "%k", "%v", "%m"}


def say(text: str) -> None:
    now = time.time()
    print(f"syncrain-login: {time.strftime('%H:%M:%S', time.localtime(now))}.{int(now % 1 * 10)} {text}", flush=True)


def data_dirs() -> list[Path]:
    dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    return [Path(d) for d in dirs.split(":") if d]


def read_desktop(path: Path) -> dict | None:
    """The [Desktop Entry] keys of a session file, or None when it is hidden or cannot start."""
    keys, inside = {}, False
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in lines:
        line = line.strip()
        if line.startswith("["):
            inside = line == "[Desktop Entry]"
        elif inside and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            keys.setdefault(k.strip(), v.strip())
    if keys.get("Hidden") == "true" or keys.get("NoDisplay") == "true" or not keys.get("Exec"):
        return None
    try:
        cmd = [w for w in shlex.split(keys["Exec"]) if w not in FIELD_CODES]
    except ValueError:
        return None
    try_exec = keys.get("TryExec")
    if try_exec and not (os.access(try_exec, os.X_OK) if "/" in try_exec else _on_path(try_exec)):
        return None
    if not cmd:
        return None
    names = [n for n in keys.get("DesktopNames", "").split(";") if n]
    return {"id": path.name, "name": keys.get("Name", path.stem), "cmd": cmd, "desktop": names}


def _on_path(name: str) -> bool:
    return any(os.access(Path(d) / name, os.X_OK) for d in os.environ.get("PATH", "/usr/bin").split(":") if d)


def sessions(dirs: list[Path] | None = None) -> list[dict]:
    """The Wayland sessions installed, first folder winning for a file name (as display managers do)."""
    found: dict[str, dict] = {}
    for d in dirs if dirs is not None else data_dirs():
        folder = d / "wayland-sessions"
        for path in sorted(folder.glob("*.desktop")) if folder.is_dir() else ():
            if path.name not in found:
                entry = read_desktop(path)
                if entry:
                    found[path.name] = entry
    return sorted(found.values(), key=lambda s: s["name"].lower())


def pick(found: list[dict], wanted: str | None) -> int:
    """Which session to offer: the one asked for, else Plasma, else the first."""
    for want in (wanted, "plasma.desktop"):
        for i, s in enumerate(found):
            if want and s["id"] == want:
                return i
    for i, s in enumerate(found):
        if s["id"].startswith("plasma"):
            return i
    return 0


def session_env(session: dict) -> list[str]:
    """What the session is told about itself (SDDM tells Plasma the same)."""
    desktop = session.get("desktop") or [Path(session["id"]).stem]
    return ["XDG_SESSION_TYPE=wayland", f"XDG_SESSION_DESKTOP={desktop[0]}",
            f"XDG_CURRENT_DESKTOP={':'.join(desktop)}"]


def fallback_command(config: dict, dirs: list[Path] | None = None) -> str:
    """The command greetd's text login starts when this login screen did not come up (login.sh)."""
    found = sessions(dirs)
    if not found:
        return "startplasma-wayland"
    s = found[pick(found, config.get("session"))]
    return shlex.join(["env", *session_env(s), *s["cmd"]])


def state_dir() -> Path:
    return Path(os.environ.get("SYNCRAIN_LOGIN_STATE") or os.environ.get("XDG_STATE_HOME") or "/tmp")


def read_config() -> dict:
    """login.json, then the last login on top of it."""
    out: dict = {}
    path = Path(os.environ.get("SYNCRAIN_LOGIN_CONFIG") or LIB / "login.json")
    for p in (path, state_dir() / "last.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            out.update({k: v for k, v in data.items() if v not in (None, "")})
    return out


def remember(user: str, session_id: str) -> None:
    try:
        (state_dir() / "last.json").write_text(json.dumps({"user": user, "session": session_id}), encoding="utf-8")
    except OSError:
        pass


def rain_command(config: dict) -> list[str]:
    args = [str(a) for a in config.get("rain") or []]
    return [sys.executable, "-m", "syncrain", *args, "--pause-under", "never"]


def preload_layer_shell(argv: list[str]) -> None:
    """gtk4-layer-shell has to be loaded before libwayland-client: start again once with it preloaded."""
    if not os.environ.get("WAYLAND_DISPLAY") or "gtk4-layer-shell" in os.environ.get("LD_PRELOAD", ""):
        return
    import ctypes.util
    lib = ctypes.util.find_library("gtk4-layer-shell")
    if lib:
        os.environ["LD_PRELOAD"] = (lib + " " + os.environ.get("LD_PRELOAD", "")).strip()
        os.execv(sys.executable, [sys.executable, "-m", "syncrain.greeter", *argv])


def start_rain(config: dict):
    """The rain, before anything else: it draws while GTK is still loading."""
    if os.environ.get("SYNCRAIN_LOGIN_NO_RAIN"):
        return None
    env = {k: v for k, v in os.environ.items() if k not in ("LD_PRELOAD", "SYNCRAIN_REEXEC")}
    try:
        proc = subprocess.Popen(rain_command(config), env=env, start_new_session=True)
    except OSError as e:
        say(f"the rain did not start: {e}")
        return None
    say(f"rain started (pid {proc.pid})")
    return proc


def stop_rain(proc) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=1.5)            # greetd allows the greeter about 5 s to leave
    except (OSError, subprocess.TimeoutExpired):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass


CSS = """
window.syncrain-login { background-color: transparent; }
.login-box { background-color: rgba(3, 8, 18, 0.80); border: 1px solid rgba(126, 182, 255, 0.40);
             border-radius: 14px; padding: 16px 26px; }
.login-box label.title { font-size: 17px; font-weight: bold; color: #cfe3ff; }
.login-box label.message { color: #ff9a8a; }
.login-box entry, .login-box dropdown button { min-width: 260px; color: #e8f1ff; box-shadow: none;
             background-image: none; background-color: rgba(255, 255, 255, 0.07);
             border: 1px solid rgba(126, 182, 255, 0.30); }
.login-box dropdown button label, .login-box dropdown arrow { color: #e8f1ff; }
.login-box entry:focus-within { border-color: rgba(126, 182, 255, 0.85); }
.login-box button.login { background-image: none; background-color: rgba(70, 130, 220, 0.85); color: white;
             border: none; box-shadow: none; }
.login-box button.login:hover { background-color: rgba(90, 150, 240, 0.95); }
.login-box button.power { color: #9fb6d6; background-image: none; background-color: transparent; }
"""


def run_box(config: dict, client: Greetd) -> int:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, GLib, Gtk
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell as LayerShell
        if not LayerShell.is_supported():
            LayerShell = None
    except (ValueError, ImportError):
        LayerShell = None

    Gtk.init()
    display = Gdk.Display.get_default()
    if display is None:
        say("no display")
        return 1
    css = Gtk.CssProvider()
    if hasattr(css, "load_from_string"):
        css.load_from_string(CSS)
    else:
        css.load_from_data(CSS.encode())
    add_provider = getattr(Gtk, "style_context_add_provider_for_display", None) \
        or Gtk.StyleContext.add_provider_for_display
    add_provider(display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    found = sessions()
    if not found:
        say("no Wayland sessions installed (wayland-sessions/*.desktop)")
    loop = GLib.MainLoop()
    result = {"code": 1}

    win = Gtk.Window(title="syncrain login")
    win.add_css_class("syncrain-login")
    win.set_decorated(False)
    if LayerShell is not None:
        LayerShell.init_for_window(win)
        LayerShell.set_namespace(win, "syncrain-login")
        LayerShell.set_layer(win, LayerShell.Layer.OVERLAY)
        LayerShell.set_keyboard_mode(win, LayerShell.KeyboardMode.EXCLUSIVE)
        # below the rain's logo, which sits in the middle of the screen; KWin puts the box on the
        # screen with the pointer, and its height is known once it is there (shown, below)
        LayerShell.set_anchor(win, LayerShell.Edge.BOTTOM, True)
        LayerShell.set_margin(win, LayerShell.Edge.BOTTOM, 40)
    else:
        say("the compositor has no layer-shell; the box opens as a window")

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
    box.add_css_class("login-box")
    title = Gtk.Label(label=os.uname().nodename)
    title.add_css_class("title")
    user = Gtk.Entry(placeholder_text="User", text=str(config.get("user", "")))
    password = Gtk.PasswordEntry(placeholder_text="Password", show_peek_icon=True)
    names = Gtk.StringList()
    for s in found:
        names.append(s["name"])
    chooser = Gtk.DropDown(model=names)
    if found:
        chooser.set_selected(pick(found, config.get("session")))
    login = Gtk.Button(label="Log in")
    login.add_css_class("login")
    message = Gtk.Label(label="", wrap=True, max_width_chars=36, justify=Gtk.Justification.CENTER, visible=False)
    message.add_css_class("message")

    def tell(text):
        message.set_label(text)
        message.set_visible(bool(text))
    power = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
    for label, verb in (("Restart", "reboot"), ("Shut down", "poweroff"), ("Text login", "text")):
        b = Gtk.Button(label=label)
        b.add_css_class("flat")
        b.add_css_class("power")
        b.connect("clicked", lambda _b, verb=verb: text_login() if verb == "text" else power_off(verb))
        power.append(b)
    for w in (title, user, password, chooser, login, message, power):
        box.append(w)
    win.set_child(box)

    def power_off(verb):
        say(f"systemctl {verb}")

        def work():
            try:
                done = subprocess.run(["systemctl", verb], capture_output=True, text=True, timeout=60)
                said = done.stderr.strip() if done.returncode else ""
            except (OSError, subprocess.TimeoutExpired) as e:
                said = str(e)
            if said:
                say(f"systemctl {verb}: {said}")
                GLib.idle_add(tell, f"systemctl {verb}: {said}")
        threading.Thread(target=work, daemon=True).start()

    def text_login():
        # No marker: login.sh hands over to greetd's text login.
        say("text login asked for")
        loop.quit()

    def busy(on: bool):
        for w in (user, password, chooser, login):
            w.set_sensitive(not on)

    def attempt(*_):
        name = user.get_text().strip()
        if not name:
            user.grab_focus()
            return
        if not found:
            tell("No session to start")
            return
        session = found[chooser.get_selected()]
        secret = password.get_text()
        busy(True)
        tell("Logging in...")

        def work():
            ok, said = client.login(name, secret, session["cmd"], session_env(session))
            GLib.idle_add(done, ok, said, name, session)
        threading.Thread(target=work, daemon=True).start()

    def done(ok, said, name, session):
        if ok:
            say(f"logged in {name}: {shlex.join(session['cmd'])}")
            remember(name, session["id"])
            marker = os.environ.get("SYNCRAIN_LOGIN_MARKER")
            try:
                if marker:
                    Path(marker).write_text(session["id"] + "\n", encoding="utf-8")
            except OSError as e:          # greetd starts the session anyway; the text login is killed
                say(f"no marker written: {e}")
            result["code"] = 0
            loop.quit()
            return False
        say(f"not logged in: {said.replace(chr(10), ' / ')}")
        tell(said)
        busy(False)
        password.set_text("")
        password.grab_focus()
        later(next_test)
        return False

    user.connect("activate", lambda *_: password.grab_focus())
    password.connect("activate", attempt)
    login.connect("clicked", attempt)
    win.connect("close-request", lambda *_: (loop.quit(), False)[1])

    # The tests type into the box through this: a list of {"user", "password", "session", "wait"
    # (seconds before typing)} tried in turn; {"text": true} presses Text login.
    tests = json.loads(os.environ.get("SYNCRAIN_GREETER_TEST_INPUT") or "[]")

    def later(fn):
        if tests:
            GLib.timeout_add(int(float(tests[0].get("wait", 0.3)) * 1000), fn)

    def next_test():
        if not tests:
            return False
        t = tests.pop(0)
        if t.get("text"):
            text_login()
            return False
        if "user" in t:
            user.set_text(t["user"])
        password.set_text(t.get("password", ""))
        if "session" in t:
            for i, s in enumerate(found):
                if s["id"] == t["session"]:
                    chooser.set_selected(i)
        attempt()
        return False

    def shown(*_):
        if result.get("shown"):
            return
        result["shown"] = True
        monitor = display.get_monitor_at_surface(win.get_surface()) if win.get_surface() else None
        if LayerShell is not None and monitor is not None:
            LayerShell.set_margin(win, LayerShell.Edge.BOTTOM, int(monitor.get_geometry().height * 0.04))
        say("box shown")
        (password if user.get_text() else user).grab_focus()
        later(next_test)
    win.connect("map", shown)
    win.present()
    loop.run()
    win.destroy()
    return result["code"]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    config = read_config()
    if argv[:1] == ["--fallback-command"]:
        print(fallback_command(config))
        return 0
    if argv[:1] == ["--draw-symbols"]:
        # install.sh: the symbols the rain needs drawn now, into XDG_CACHE_HOME, so the login screen
        # does not spend seconds drawing them at every boot; the scene is otherwise thrown away.
        from . import app, native
        native.scene_bytes(app.parse_args(rain_command(config)[3:]), None)
        return 0
    preload_layer_shell(argv)
    rain = start_rain(config)
    try:
        return run_box(config, Greetd())
    finally:
        stop_rain(rain)


if __name__ == "__main__":
    raise SystemExit(main())
