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
import queue
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


def session_command(session: dict) -> list[str]:
    """The session's command as greetd takes it. greetd joins the words it is given with spaces and
    has sh run the line, so the command goes as one word, quoted the way sh reads it: an Exec line's
    quoted words arrive whole."""
    return [shlex.join(session["cmd"])]


def fallback_command(config: dict, dirs: list[Path] | None = None) -> str:
    """The command greetd's text login starts when this login screen did not come up (login.sh)."""
    found = sessions(dirs)
    if not found:
        return "startplasma-wayland"
    s = found[pick(found, config.get("session"))]
    return shlex.join(["env", *session_env(s), *s["cmd"]])


def state_dir() -> Path | None:
    """The login screen's own folder, which login.sh names; None anywhere else. install.sh's
    --draw-symbols runs as the operator, and a fallback to a shared folder such as /tmp would read a
    last.json any other user can leave there."""
    named = os.environ.get("SYNCRAIN_LOGIN_STATE")
    return Path(named) if named else None


#: What the last login may say: who and which session, never the rain's options.
LAST_KEYS = ("user", "session")


def read_config() -> dict:
    """login.json, then the last login (user and session) on top of it, on the login screen."""
    out: dict = {}
    path = Path(os.environ.get("SYNCRAIN_LOGIN_CONFIG") or LIB / "login.json")
    state = state_dir()
    for p, keys in ((path, None), (state / "last.json" if state else None, LAST_KEYS)):
        if p is None:
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            out.update({k: v for k, v in data.items() if v not in (None, "") and (keys is None or k in keys)})
    return out


def remember(user: str, session_id: str) -> None:
    state = state_dir()
    if state is None:
        return
    try:
        (state / "last.json").write_text(json.dumps({"user": user, "session": session_id}), encoding="utf-8")
    except OSError:
        pass


def rain_command(config: dict) -> list[str]:
    """The rain as the login screen runs it: the operator's settings file where install.sh copied it
    (else none: the greeter's own folder holds none of theirs), then the options login.json names."""
    args = [str(a) for a in config.get("rain") or []]
    settings = LIB / "config.json"
    try:
        has_sets = isinstance(json.loads(settings.read_text(encoding="utf-8")).get("glyphs"), dict)
    except (OSError, ValueError, AttributeError):
        has_sets = False
    if has_sets:                                  # the settings file's sets, as the wallpaper draws them
        args = [a for i, a in enumerate(args) if a != "--glyphs" and (i == 0 or args[i - 1] != "--glyphs")]
    return [sys.executable, "-m", "syncrain", "--config", str(settings) if settings.is_file() else "none", *args,
            "--pause-under", "never"]


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
    if LayerShell is None:
        say("the compositor has no layer-shell; the box opens as a window")

    found = sessions()
    if not found:
        say("no Wayland sessions installed (wayland-sessions/*.desktop)")
    loop = GLib.MainLoop()
    result = {"code": 1}

    # One box on every screen, all the same box: what is typed in one shows in all of them, so the
    # screen with the keyboard's attention never matters, nor one that is off or out of sight.
    user_text = Gtk.EntryBuffer.new(str(config.get("user", "")), -1)
    password_text = Gtk.PasswordEntryBuffer()
    names = Gtk.StringList()
    for s in found:
        names.append(s["name"])
    shared = {"session": pick(found, config.get("session")) if found else 0, "message": "", "busy": False,
              "peek": False, "shown": set(), "asking": None, "text_after": False}
    boxes: list[dict] = []

    def tell(text):
        shared["message"] = text
        for b in boxes:
            b["message"].set_label(text)
            b["message"].set_visible(bool(text))

    def busy(on: bool):
        shared["busy"] = on
        for b in boxes:
            for w in (b["user"], b["password"], b["chooser"], b["login"], b["text"]):
                w.set_sensitive(not on)

    def choose(i):
        shared["session"] = i
        for b in boxes:
            if b["chooser"].get_selected() != i:
                b["chooser"].set_selected(i)

    def peek(on):
        shared["peek"] = on
        for b in boxes:
            b["password"].set_visibility(on)
            b["password"].set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY,
                                                  "view-conceal-symbolic" if on else "view-reveal-symbolic")

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
        # While PAM asks for more (a second factor), the login is given up first, then the text login
        # comes, so greetd holds no half-made session.
        if shared["asking"] is not None:
            say("text login: giving up the login under way first")
            shared["text_after"] = True
            answer(None)
            tell("Giving up this login...")
            return
        # Not while greetd is checking a login: leaving now would leave greetd holding that half-made
        # session, and the text login's first attempt would fail on it.
        if shared["busy"]:
            say("text login: not while a login is under way")
            return
        # No marker: login.sh hands over to greetd's text login.
        say("text login asked for")
        loop.quit()

    def asking_look(b):
        """A box while PAM asks: the password field takes the answer, Text login can give up."""
        prompt, secret = shared["prompt"]
        for w in (b["password"], b["login"], b["text"]):
            w.set_sensitive(True)
        b["password"].set_placeholder_text(prompt)
        b["password"].set_visibility(shared["peek"] or not secret)

    def ask_here(prompt, secret, answers):
        """PAM asks for more than the password: the password field takes the answer."""
        shared["asking"], shared["prompt"] = answers, (prompt, secret)
        say(f"asked: {prompt}")
        tell(prompt)
        password_text.set_text("", -1)
        for b in boxes:
            asking_look(b)
            b["password"].grab_focus()
        later(next_test)
        return False

    def answer(text):
        answers, shared["asking"] = shared["asking"], None
        busy(True)
        for b in boxes:
            b["password"].set_placeholder_text("Password")
            b["password"].set_visibility(shared["peek"])
        tell("Logging in...")
        answers.put(text)

    def attempt(*_):
        if shared["asking"] is not None:
            answer(password_text.get_text())
            password_text.set_text("", -1)
            return
        if shared["busy"]:
            return
        name = user_text.get_text().strip()
        if not name:
            for b in boxes:
                b["user"].grab_focus()
            return
        if not found:
            tell("No session to start")
            return
        session = found[shared["session"]]
        secret = password_text.get_text()
        busy(True)
        tell("Logging in...")

        def ask(prompt, secret):
            answers = queue.Queue()
            GLib.idle_add(ask_here, prompt, secret, answers)
            try:
                return answers.get(timeout=300)
            except queue.Empty:                   # nobody answered: the login is given up
                GLib.idle_add(lambda: (shared.update(asking=None), False)[1])
                return None

        def work():
            ok, said = client.login(name, secret, session_command(session), session_env(session), ask=ask,
                                    tell=lambda text: GLib.idle_add(lambda: (tell(text), False)[1]))
            GLib.idle_add(done, ok, said, name, session)
        threading.Thread(target=work, daemon=True).start()

    def done(ok, said, name, session):
        shared["asking"] = None
        for b in boxes:
            b["password"].set_placeholder_text("Password")
            b["password"].set_visibility(shared["peek"])
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
        if shared["text_after"]:
            text_login()
            return False
        password_text.set_text("", -1)
        for b in boxes:
            b["password"].grab_focus()
        later(next_test)
        return False

    def mirror(field):
        if shared.get("mirroring"):
            return
        shared["mirroring"] = True
        try:
            for b in boxes:
                b[field].grab_focus()
        finally:
            shared["mirroring"] = False

    def make(monitor):
        win = Gtk.Window(title="syncrain login")
        win.add_css_class("syncrain-login")
        win.set_decorated(False)
        if LayerShell is not None:
            LayerShell.init_for_window(win)
            LayerShell.set_namespace(win, "syncrain-login")
            LayerShell.set_layer(win, LayerShell.Layer.OVERLAY)
            LayerShell.set_keyboard_mode(win, LayerShell.KeyboardMode.EXCLUSIVE)
            if monitor is not None:
                LayerShell.set_monitor(win, monitor)
            # below the rain's logo, which sits in the middle of the screen
            LayerShell.set_anchor(win, LayerShell.Edge.BOTTOM, True)
            height = monitor.get_geometry().height if monitor is not None else 720
            LayerShell.set_margin(win, LayerShell.Edge.BOTTOM, int(height * 0.04))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        box.add_css_class("login-box")
        title = Gtk.Label(label=os.uname().nodename)
        title.add_css_class("title")
        user = Gtk.Entry(buffer=user_text, placeholder_text="User")
        password = Gtk.Entry(buffer=password_text, placeholder_text="Password", visibility=shared["peek"],
                             input_purpose=Gtk.InputPurpose.PASSWORD)
        password.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY,
                                         "view-conceal-symbolic" if shared["peek"] else "view-reveal-symbolic")
        password.connect("icon-press", lambda *_: peek(not shared["peek"]))
        chooser = Gtk.DropDown(model=names)
        if found:
            chooser.set_selected(shared["session"])
        chooser.connect("notify::selected", lambda c, _p: choose(c.get_selected()))
        login = Gtk.Button(label="Log in")
        login.add_css_class("login")
        message = Gtk.Label(label=shared["message"], wrap=True, max_width_chars=36,
                            justify=Gtk.Justification.CENTER, visible=bool(shared["message"]))
        message.add_css_class("message")
        power = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        buttons = {}
        for label, verb in (("Restart", "reboot"), ("Shut down", "poweroff"), ("Text login", "text")):
            b = buttons[verb] = Gtk.Button(label=label)
            b.add_css_class("flat")
            b.add_css_class("power")
            b.connect("clicked", lambda _b, verb=verb: text_login() if verb == "text" else power_off(verb))
            power.append(b)
        for w in (title, user, password, chooser, login, message, power):
            box.append(w)
        win.set_child(box)
        user.connect("activate", lambda *_: password.grab_focus())
        password.connect("activate", attempt)
        login.connect("clicked", attempt)
        # On layer-shell a box is closed by the compositor when its screen goes; place() rebuilds.
        win.connect("close-request", lambda *_: True if LayerShell is not None else (loop.quit(), False)[1])
        # The keyboard goes to one box (KWin picks); a field clicked in any box is the field in all.
        for field, widget in (("user", user), ("password", password)):
            focus = Gtk.EventControllerFocus()
            focus.connect("enter", lambda _c, field=field: mirror(field))
            widget.add_controller(focus)
        name = (monitor.get_connector() if monitor is not None else None) or "a window"
        entry = {"win": win, "user": user, "password": password, "chooser": chooser, "login": login,
                 "text": buttons["text"], "message": message, "name": name}

        def shown(*_):
            if name in shared["shown"]:
                return
            (password if user_text.get_text() else user).grab_focus()
            first = not shared["shown"]
            shared["shown"].add(name)
            say(f"box shown on {name}")
            if first:
                later(next_test)
        win.connect("map", shown)
        boxes.append(entry)
        if shared["busy"]:
            busy(True)
        if shared["asking"] is not None:              # a screen came while PAM asks: it asks there too
            asking_look(entry)
        win.present()

    def place(*_):
        """A box for every screen there is now (a screen plugged in or out rebuilds them)."""
        for b in boxes:
            b["win"].destroy()
        boxes.clear()
        shared["shown"] = set()
        monitors = display.get_monitors()
        items = [monitors.get_item(i) for i in range(monitors.get_n_items())]
        for monitor in (items if LayerShell is not None and items else [None]):
            make(monitor)

    # The tests type into the box through this: a list of {"user", "password", "session", "wait"
    # (seconds before typing)} tried in turn; {"text": true} presses Text login; {"answer"} answers
    # what PAM asks after the password. An entry with "during": true comes while the login before
    # it is still being checked.
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
        if "answer" in t:
            password_text.set_text(t["answer"], -1)
            attempt()
            return False
        if "user" in t:
            user_text.set_text(t["user"], -1)
        password_text.set_text(t.get("password", ""), -1)
        if "session" in t:
            for i, s in enumerate(found):
                if s["id"] == t["session"]:
                    choose(i)
        attempt()
        if tests and tests[0].get("during"):
            later(next_test)
        return False

    display.get_monitors().connect("items-changed", lambda *_: GLib.idle_add(lambda: (place(), False)[1]))
    place()
    loop.run()
    for b in boxes:
        b["win"].destroy()
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
