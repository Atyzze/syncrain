"""The login screen's parts without a display (build 16): greetd's conversation, the sessions offered,
login.sh's way out to greetd's text login, and install.sh --login-screen and --login-screen-off
against stubs for sudo, systemctl and KWin. The whole login in KWin: tests/kwin/test_a_login_in_kwin.py."""
from __future__ import annotations

import getpass
import json
import os
import subprocess
import sys

from syncrain import build, greeter
from syncrain.greetd import Greetd
from tests.conftest import ROOT
from tests.fake_greetd import FakeGreetd

PLASMA = "/usr/lib/plasma-dbus-run-session-if-needed /usr/bin/startplasma-wayland"
ENV = ["XDG_SESSION_TYPE=wayland", "XDG_SESSION_DESKTOP=KDE", "XDG_CURRENT_DESKTOP=KDE"]


def test_the_right_password_starts_the_session_and_the_greeting_is_passed_on(tmp_path):
    fake = FakeGreetd(tmp_path / "sock")
    assert Greetd(fake.path).login("op", "right", ["startplasma-wayland"], ENV) == (True, "Welcome")
    assert fake.started() == [{"type": "start_session", "cmd": ["startplasma-wayland"], "env": ENV}]
    assert [r["type"] for r in fake.requests][:3] == ["create_session", "post_auth_message_response",
                                                       "post_auth_message_response"]
    assert fake.requests[1]["response"] is None, "an info line is answered with nothing"
    fake.close()


def test_a_wrong_password_is_said_and_the_session_cancelled(tmp_path):
    fake = FakeGreetd(tmp_path / "sock")
    ok, said = Greetd(fake.path).login("op", "wrong", ["x"], [])
    assert (ok, said) == (False, "Welcome\nWrong password")
    assert fake.requests[-1] == {"type": "cancel_session"} and not fake.started()
    fake.close()


def test_without_greetd_it_says_so(tmp_path):
    assert Greetd("").login("op", "x", ["x"], []) == (False, "not started by greetd (no GREETD_SOCK)")
    ok, said = Greetd(str(tmp_path / "none")).login("op", "x", ["x"], [])
    assert not ok and said.startswith("greetd: ")


def write_sessions(share):
    folder = share / "wayland-sessions"
    folder.mkdir(parents=True)
    (folder / "plasma.desktop").write_text(f"[Desktop Entry]\nExec={PLASMA}\nDesktopNames=KDE\nName=Plasma (Wayland)\n"
                                           "Name[nl]=Plasma (Wayland)\n")
    (folder / "sway.desktop").write_text("[Desktop Entry]\nExec=sway %U\nDesktopNames=sway;wlroots\nName=Sway\n")
    (folder / "gone.desktop").write_text("[Desktop Entry]\nExec=gone\nTryExec=/nonexistent/gone\nName=Gone\n")
    (folder / "hidden.desktop").write_text("[Desktop Entry]\nExec=hidden\nHidden=true\nName=Hidden\n")


def test_the_sessions_offered_are_the_installed_wayland_ones(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    write_sessions(second)
    (first / "wayland-sessions").mkdir(parents=True)
    (first / "wayland-sessions" / "sway.desktop").write_text("[Desktop Entry]\nExec=sway --mine\nName=My Sway\n")
    found = greeter.sessions([first, second])
    assert [(s["id"], s["name"], s["cmd"]) for s in found] == [
        ("sway.desktop", "My Sway", ["sway", "--mine"]),
        ("plasma.desktop", "Plasma (Wayland)", PLASMA.split())]
    assert greeter.pick(found, None) == 1, "Plasma unless asked otherwise"
    assert greeter.pick(found, "sway.desktop") == 0
    assert greeter.session_env(found[1]) == ENV
    assert greeter.session_env({"id": "sway.desktop", "desktop": ["sway", "wlroots"]})[1:] == [
        "XDG_SESSION_DESKTOP=sway", "XDG_CURRENT_DESKTOP=sway:wlroots"]
    assert greeter.read_desktop(second / "wayland-sessions" / "sway.desktop")["cmd"] == ["sway"], "field codes go"


def test_the_last_login_is_offered_next_time(tmp_path, monkeypatch):
    (tmp_path / "login.json").write_text(json.dumps({"user": "op", "session": "plasma.desktop", "rain": ["--fps", "20"]}))
    monkeypatch.setenv("SYNCRAIN_LOGIN_CONFIG", str(tmp_path / "login.json"))
    monkeypatch.setenv("SYNCRAIN_LOGIN_STATE", str(tmp_path))
    greeter.remember("guest", "sway.desktop")
    config = greeter.read_config()
    assert (config["user"], config["session"]) == ("guest", "sway.desktop")
    assert greeter.rain_command(config)[3:] == ["--fps", "20", "--pause-under", "never"]


def stub(folder, name, body):
    folder.mkdir(exist_ok=True)
    path = folder / name
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(0o755)
    return path


def test_when_the_box_never_logs_anyone_in_greetd_s_text_login_starts_plasma(tmp_path):
    write_sessions(tmp_path / "share")
    text = stub(tmp_path / "bin", "agreety", f'printf "%s\\n" "$@" > {tmp_path}/text.ran')
    env = dict(os.environ, XDG_DATA_DIRS=str(tmp_path / "share"), SYNCRAIN_LOGIN_STATE=str(tmp_path / "state"),
               SYNCRAIN_LOGIN_KWIN="false", SYNCRAIN_LOGIN_TEXT=str(text), SYNCRAIN_PYTHON=sys.executable,
               SYNCRAIN_LOGIN_CONFIG=str(tmp_path / "none.json"))
    done = subprocess.run(["sh", str(ROOT / "syncrain/login/login.sh")], env=env, capture_output=True, text=True,
                          timeout=60)
    assert done.returncode == 0, done.stdout + done.stderr
    assert (tmp_path / "text.ran").read_text().splitlines() == ["--cmd", "env " + " ".join(ENV) + " " + PLASMA]
    log = (tmp_path / "state" / "login.log").read_text()
    assert f"build {build.BUILD_NUMBER}" in log and "greetd's text login takes over" in log


def run_install(tmp_path, *args):
    bins = tmp_path / "bin"
    stub(bins, "sudo", 'exec "$@"')
    stub(bins, "kwin_wayland", "exit 0")
    stub(bins, "agreety", "exit 0")
    stub(bins, "systemctl", f'[ "$1" = --user ] && exit 1; echo "$@" >> {tmp_path}/systemctl.calls')
    env = {"HOME": str(tmp_path / "home"), "XDG_CONFIG_HOME": str(tmp_path / "config"), "LANG": "C.UTF-8",
           "XDG_CACHE_HOME": str(tmp_path / "cache"),
           "PATH": f"{bins}:{os.path.dirname(sys.executable)}:/usr/bin:/bin", "CC": "no-compiler-here",
           "SYNCRAIN_LOGIN_LIB": str(tmp_path / "lib"), "SYNCRAIN_LOGIN_STATE": str(tmp_path / "state"),
           "SYNCRAIN_GREETD_CONFIG": str(tmp_path / "etc/greetd/config.toml"),
           "SYNCRAIN_GREETD_PAM": str(tmp_path / "etc/pam.d/greetd"),
           "SYNCRAIN_DM_LINK": str(tmp_path / "display-manager.service"),
           "SYNCRAIN_LOGIN_OWNER": getpass.getuser()}
    for key in ("GI_TYPELIB_PATH", "LD_LIBRARY_PATH"):
        if key in os.environ:
            env[key] = os.environ[key]
    return subprocess.run(["bash", str(ROOT / "install.sh"), "--no-deps", *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=180)


def test_install_makes_the_rain_the_login_screen_and_puts_sddm_back_after(tmp_path):
    (tmp_path / "etc/greetd").mkdir(parents=True)
    (tmp_path / "etc/greetd/config.toml").write_text("[default_session]\ncommand = \"agreety --cmd /bin/sh\"\n")
    (tmp_path / "etc/pam.d").mkdir(parents=True)
    pam = "#%PAM-1.0\nauth       include      system-local-login\nsession    include      system-local-login\n"
    (tmp_path / "etc/pam.d/greetd").write_text(pam)
    (tmp_path / "display-manager.service").symlink_to("/usr/lib/systemd/system/sddm.service")
    (tmp_path / "config/syncrain").mkdir(parents=True)
    (tmp_path / "config/syncrain/glyphs.json").write_text(json.dumps({"sets": [{"name": "big", "chars": "AB",
                                                                                "size": 1.2}]}))
    (tmp_path / "config/kwinoutputconfig.json").write_text("[]")
    (tmp_path / "config/kxkbrc").write_text("[Layout]\nLayoutList=us\n")
    done = run_install(tmp_path, "--theme", "matrix", "--login-screen")
    assert done.returncode == 0, done.stdout + done.stderr
    lib = tmp_path / "lib"
    assert json.loads((lib / "login.json").read_text()) == {
        "user": getpass.getuser(), "session": "plasma.desktop",
        "rain": ["--theme", "matrix", "--glyphs", f"{lib}/glyphs.json"]}
    assert (lib / "BUILD_NUMBER").read_text().strip() == str(build.BUILD_NUMBER)
    assert os.access(lib / "syncrain/login/login.sh", os.X_OK) and sorted(p.name for p in (lib / "kde").iterdir()) == [
        "kwinoutputconfig.json", "kxkbrc"]
    assert list((lib / "cache").glob("glyphs-*.png")), "the big symbols were drawn at install"
    config = (tmp_path / "etc/greetd/config.toml").read_text()
    login = f"{lib}/syncrain/login/login.sh"
    assert f"command = \"sh -c 'test -x {login} && exec {login}; exec agreety --cmd startplasma-wayland'\"" in config
    assert 'user = "greeter"' in config
    import tomllib
    command = tomllib.loads(config)["default_session"]["command"]
    assert command == f"sh -c 'test -x {login} && exec {login}; exec agreety --cmd startplasma-wayland'"
    assert "agreety --cmd /bin/sh" in (tmp_path / "etc/greetd/config.toml.before-syncrain").read_text()
    assert (lib / "previous-display-manager").read_text() == "sddm.service\n"
    added = (tmp_path / "etc/pam.d/greetd").read_text()
    assert added.startswith(pam) and "-auth       optional    pam_kwallet5.so" in added
    assert "-session    optional    pam_kwallet5.so         auto_start" in added
    assert "sudo systemctl enable --force sddm.service && sudo reboot" in done.stdout

    again = run_install(tmp_path)                   # a newer build: the login screen's copy follows
    assert again.returncode == 0 and "the login screen: build" in again.stdout, again.stdout + again.stderr
    assert json.loads((lib / "login.json").read_text())["rain"][:2] == ["--theme", "matrix"]

    off = run_install(tmp_path, "--login-screen-off")
    assert off.returncode == 0, off.stdout + off.stderr
    assert (tmp_path / "systemctl.calls").read_text().splitlines() == [
        "enable --force greetd.service", "enable --force sddm.service"]
    assert "agreety --cmd /bin/sh" in (tmp_path / "etc/greetd/config.toml").read_text()
    assert (tmp_path / "etc/pam.d/greetd").read_text() == pam
    assert not lib.exists() and not (tmp_path / "state").exists()


def test_the_diagnosis_says_which_login_screen_starts_and_what_it_said(tmp_path, monkeypatch):
    from syncrain.diagnose import login_lines
    (tmp_path / "dm").symlink_to("/usr/lib/systemd/system/greetd.service")
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib/BUILD_NUMBER").write_text("16\n")
    (tmp_path / "config.toml").write_text(f'[default_session]\ncommand = "{tmp_path}/lib/syncrain/login/login.sh"\n')
    (tmp_path / "state").mkdir()
    (tmp_path / "state/login.log").write_text("syncrain-login: 07:00:01.2 rain started (pid 9)\nnoise\n"
                                              "syncrain: 30.0 fps at 2560x1440 (area 0)\n"
                                              "syncrain-login: 07:00:01.9 box shown\n")
    for key, value in (("DM_LINK", "dm"), ("LOGIN_LIB", "lib"), ("GREETD_CONFIG", "config.toml"), ("LOGIN_STATE", "state")):
        monkeypatch.setenv(f"SYNCRAIN_{key}", str(tmp_path / value))
    assert login_lines() == [
        "display manager at boot: greetd.service", "greetd runs syncrain's login screen",
        f"syncrain's login screen: build 16 in {tmp_path}/lib", f"the last start ({tmp_path}/state/login.log):",
        "  syncrain-login: 07:00:01.2 rain started (pid 9)", "  syncrain-login: 07:00:01.9 box shown"]


def test_a_kwin_that_hangs_is_stopped_and_the_text_login_asks(tmp_path):
    write_sessions(tmp_path / "share")
    text = stub(tmp_path / "bin", "agreety", f'printf "%s\\n" "$@" > {tmp_path}/text.ran')
    hang = stub(tmp_path / "bin", "kwin", "exec sleep 600")
    env = dict(os.environ, XDG_DATA_DIRS=str(tmp_path / "share"), SYNCRAIN_LOGIN_STATE=str(tmp_path / "state"),
               SYNCRAIN_LOGIN_KWIN=str(hang), SYNCRAIN_LOGIN_TEXT=str(text), SYNCRAIN_PYTHON=sys.executable,
               SYNCRAIN_LOGIN_CONFIG=str(tmp_path / "none.json"), SYNCRAIN_LOGIN_WATCHDOG="2")
    done = subprocess.run(["sh", str(ROOT / "syncrain/login/login.sh")], env=env, capture_output=True, text=True,
                          timeout=60)
    assert done.returncode == 0, done.stdout + done.stderr
    log = (tmp_path / "state" / "login.log").read_text()
    assert "no box after 2 s; stopping KWin" in log and "greetd's text login takes over" in log, log
    assert (tmp_path / "text.ran").read_text().splitlines()[0] == "--cmd"
