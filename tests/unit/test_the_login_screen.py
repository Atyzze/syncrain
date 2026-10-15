"""The login screen's parts without a display (build 16): greetd's conversation, the sessions offered,
login.sh's way out to greetd's text login, and install.sh --login-screen and --login-screen-off
against stubs for sudo, systemctl and KWin. The whole login in KWin: tests/kwin/test_a_login_in_kwin.py."""
from __future__ import annotations

import getpass
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from syncrain import build, greeter
from syncrain.greetd import Greetd
from tests.conftest import ROOT
from tests.fake_greetd import FakeGreetd
from tests.support import login_install, stub

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


def test_the_text_login_after_a_box_that_died_mid_conversation_is_not_refused(tmp_path, monkeypatch, capsys):
    """greetd keeps the conversation a greeter began after the greeter is gone: login.sh's way out
    drops it before greetd's text login asks, or that login's first try is refused."""
    import socket
    import struct
    fake = FakeGreetd(tmp_path / "sock")

    def request(message):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(fake.path)
            data = json.dumps(message).encode()
            s.sendall(struct.pack("=I", len(data)) + data)
            (size,) = struct.unpack("=I", s.recv(4))
            return json.loads(s.recv(size))

    assert request({"type": "create_session", "username": "op"})["type"] == "auth_message"   # the box, then gone
    assert request({"type": "create_session", "username": "op"})["description"] == \
        "a session is already being configured", "what greetd's text login would meet"
    monkeypatch.setenv("GREETD_SOCK", fake.path)
    monkeypatch.setenv("SYNCRAIN_LOGIN_CONFIG", str(tmp_path / "none.json"))
    assert greeter.main(["--fallback-command"]) == 0
    assert capsys.readouterr().out.strip()
    assert fake.requests[-1] == {"type": "cancel_session"}
    assert request({"type": "create_session", "username": "op"})["type"] == "auth_message", "the text login asks"
    fake.close()


def test_a_greetd_that_stops_answering_is_given_up_on_and_the_conversation_dropped(tmp_path):
    """The box's socket has a timeout: a greetd that never answers ends the try (said), and the
    half-made conversation is cancelled over a new connection."""
    import socket
    import threading
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(tmp_path / "sock"))
    server.listen(4)
    seen = []

    def serve():
        while True:
            try:
                conn, _ = server.accept()
            except OSError:
                return
            seen.append(conn.recv(4096))              # read, never answered
    threading.Thread(target=serve, daemon=True).start()
    started = time.monotonic()
    ok, said = Greetd(str(tmp_path / "sock"), timeout=0.5).login("op", "right", ["x"], [])
    assert not ok and said.startswith("greetd: ") and time.monotonic() - started < 10, said
    time.sleep(0.2)
    assert any(b"cancel_session" in s for s in seen), seen
    server.close()


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
    assert greeter.rain_command(config)[5:] == ["--fps", "20", "--pause-under", "never"]


def test_away_from_the_login_screen_no_last_login_is_read_or_kept(tmp_path, monkeypatch):
    """install.sh draws the symbols with the greeter's code as the operator, where login.sh names no
    state folder: no last.json is read then, neither XDG_STATE_HOME's nor one in /tmp (any user can
    leave one there). On the login screen the last login says who and which session, nothing more."""
    login = {"user": "op", "session": "plasma.desktop", "rain": ["--fps", "20"]}
    last = {"user": "guest", "session": "sway.desktop", "rain": ["--glyphs", "/tmp/planted.json"]}
    (tmp_path / "login.json").write_text(json.dumps(login))
    (tmp_path / "last.json").write_text(json.dumps(last))
    monkeypatch.setenv("SYNCRAIN_LOGIN_CONFIG", str(tmp_path / "login.json"))
    monkeypatch.delenv("SYNCRAIN_LOGIN_STATE", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert greeter.state_dir() is None
    assert greeter.read_config() == login
    greeter.remember("someone", "else.desktop")
    assert json.loads((tmp_path / "last.json").read_text()) == last, "nothing kept away from the login screen"
    monkeypatch.setenv("SYNCRAIN_LOGIN_STATE", str(tmp_path))
    assert greeter.read_config() == {"user": "guest", "session": "sway.desktop", "rain": ["--fps", "20"]}


def test_a_session_s_words_reach_greetd_as_its_exec_line_has_them(tmp_path):
    """greetd joins the words of the command it is given with spaces and has sh run the line, so the
    box sends the command as one word quoted for sh: a quoted word with spaces arrives whole."""
    write_sessions(tmp_path)
    (tmp_path / "wayland-sessions" / "words.desktop").write_text(
        '[Desktop Entry]\nExec=printf [%s] "two  words" plain\nName=Words\n')
    found = {s["id"]: s for s in greeter.sessions([tmp_path])}

    def as_greetd_runs(cmd):
        return subprocess.run(["/bin/sh", "-c", "exec " + " ".join(cmd)], cwd=tmp_path, capture_output=True,
                              text=True, timeout=30).stdout

    assert as_greetd_runs(greeter.session_command(found["words.desktop"])) == "[two  words][plain]"
    assert greeter.session_command(found["plasma.desktop"]) == [PLASMA]


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
    done = login_install(tmp_path, "--theme", "matrix", "--login-screen")
    assert done.returncode == 0, done.stdout + done.stderr
    lib = tmp_path / "lib"
    assert json.loads((lib / "login.json").read_text()) == {
        "user": getpass.getuser(), "session": "plasma.desktop",
        "rain": ["--preset=matrix", "--glyphs", f"{lib}/glyphs.json"]}
    assert (lib / "BUILD_NUMBER").read_text().strip() == str(build.BUILD_NUMBER)
    assert os.access(lib / "syncrain/login/login.sh", os.X_OK) and sorted(p.name for p in (lib / "kde").iterdir()) == [
        "kwinoutputconfig.json", "kxkbrc"]
    assert list((lib / "cache").glob("glyphs-*.png")), "the big symbols were drawn at install"
    config = (tmp_path / "etc/greetd/config.toml").read_text()
    login = f"{lib}/syncrain/login/login.sh"
    assert f"command = \"sh -c '/bin/sh -n {login} 2>/dev/null && SYNCRAIN_LOGIN_TEXT={tmp_path}/bin/agreety exec /bin/sh {login}; exec {tmp_path}/bin/agreety --cmd startplasma-wayland'\"" in config
    assert 'user = "greeter"' in config
    import tomllib
    command = tomllib.loads(config)["default_session"]["command"]
    assert command == f"sh -c '/bin/sh -n {login} 2>/dev/null && SYNCRAIN_LOGIN_TEXT={tmp_path}/bin/agreety exec /bin/sh {login}; exec {tmp_path}/bin/agreety --cmd startplasma-wayland'"
    assert "agreety --cmd /bin/sh" in (tmp_path / "etc/greetd/config.toml.before-syncrain").read_text()
    record = tmp_path / "etc/greetd/display-manager.before-syncrain"
    assert record.read_text() == "sddm.service\n" and not (lib / "previous-display-manager").exists()
    added = (tmp_path / "etc/pam.d/greetd").read_text()
    assert added.startswith(pam) and "-auth       optional    pam_kwallet5.so" in added
    assert "-session    optional    pam_kwallet5.so         auto_start" in added
    assert "sudo systemctl enable --force sddm.service && sudo reboot" in done.stdout
    assert (tmp_path / "state").stat().st_mode & 0o777 == 0o700, "who logged in, and when, is greetd's user's alone"

    again = login_install(tmp_path)                   # a newer build: the login screen's copy follows
    assert again.returncode == 0 and "the login screen: build" in again.stdout, again.stdout + again.stderr
    assert json.loads((lib / "login.json").read_text())["rain"][:1] == ["--preset=matrix"]
    page = tmp_path / "page.json"                     # a settings file from the page: it decides there too
    page.write_text(json.dumps({"contract": "syncrain-config-1", "preset": "nixos"}))
    decided = login_install(tmp_path, "--config", str(page))
    assert decided.returncode == 0, decided.stdout + decided.stderr
    assert json.loads((lib / "login.json").read_text())["rain"] == ["--glyphs", f"{lib}/glyphs.json"]
    assert json.loads((lib / "config.json").read_text())["preset"] == "nixos"

    off = login_install(tmp_path, "--login-screen-off")
    assert off.returncode == 0, off.stdout + off.stderr
    assert (tmp_path / "systemctl.calls").read_text().splitlines() == [
        "enable --force greetd.service", "enable --force sddm.service"]
    assert "agreety --cmd /bin/sh" in (tmp_path / "etc/greetd/config.toml").read_text()
    assert (tmp_path / "etc/pam.d/greetd").read_text() == pam
    assert not lib.exists() and not (tmp_path / "state").exists() and not record.exists()


def test_the_way_back_keeps_what_was_changed_meanwhile(tmp_path):
    """--login-screen-off takes out what --login-screen put in, and only that: a second factor added
    to greetd's PAM file and a section added to its config while the login screen was on stay."""
    (tmp_path / "etc/greetd").mkdir(parents=True)
    config = '[terminal]\nvt = 1\n\n[default_session]\ncommand = "agreety --cmd /bin/sh"\nuser = "greeter"\n'
    (tmp_path / "etc/greetd/config.toml").write_text(config)
    (tmp_path / "etc/pam.d").mkdir(parents=True)
    pam = "#%PAM-1.0\nauth       include      system-local-login\nsession    include      system-local-login\n"
    (tmp_path / "etc/pam.d/greetd").write_text(pam)
    (tmp_path / "display-manager.service").symlink_to("/usr/lib/systemd/system/sddm.service")
    assert login_install(tmp_path, "--login-screen").returncode == 0
    greeter_pam = (tmp_path / "etc/pam.d/greetd-greeter").read_text()
    assert "pam_kwallet5" not in greeter_pam and "system-local-login" in greeter_pam
    totp = "auth       required     pam_google_authenticator.so\n"
    added = (tmp_path / "etc/pam.d/greetd").read_text().replace("auth       include      system-local-login\n",
                                                                 "auth       include      system-local-login\n" + totp)
    (tmp_path / "etc/pam.d/greetd").write_text(added)
    (tmp_path / "etc/greetd/config.toml").write_text(
        (tmp_path / "etc/greetd/config.toml").read_text() + '\n[initial_session]\ncommand = "sway"\nuser = "op"\n')
    again = login_install(tmp_path)                    # an upgrade: the greeter's file follows greetd's
    assert again.returncode == 0, again.stdout + again.stderr
    assert "pam_google_authenticator" in (tmp_path / "etc/pam.d/greetd-greeter").read_text()
    off = login_install(tmp_path, "--login-screen-off")
    assert off.returncode == 0, off.stdout + off.stderr
    assert (tmp_path / "etc/pam.d/greetd").read_text() == pam.replace(
        "auth       include      system-local-login\n", "auth       include      system-local-login\n" + totp)
    assert (tmp_path / "etc/greetd/config.toml").read_text() == \
        config + '\n[initial_session]\ncommand = "sway"\nuser = "op"\n'
    assert not (tmp_path / "etc/pam.d/greetd-greeter").exists()
    assert not list((tmp_path / "etc").rglob("*.before-syncrain"))


def test_debian_s_default_display_manager_file_goes_with_the_switch_and_back(tmp_path):
    """Debian's greetd package points what starts at boot at the display manager this file names, at
    every upgrade; Ubuntu's SDDM does not start unless it names SDDM."""
    (tmp_path / "etc/greetd").mkdir(parents=True)
    (tmp_path / "etc/greetd/config.toml").write_text('[terminal]\nvt = 7\n\n[default_session]\ncommand = "agreety"\n')
    (tmp_path / "etc/X11").mkdir(parents=True)
    ddm = tmp_path / "etc/X11/default-display-manager"
    ddm.write_text("/usr/bin/sddm\n")
    (tmp_path / "display-manager.service").symlink_to("/usr/lib/systemd/system/sddm.service")
    assert login_install(tmp_path, "--login-screen").returncode == 0
    assert ddm.read_text().strip().endswith("greetd")
    off = login_install(tmp_path, "--login-screen-off")
    assert off.returncode == 0, off.stdout + off.stderr
    assert ddm.read_text() == "/usr/bin/sddm\n" and not list((tmp_path / "etc").rglob("*.before-syncrain"))


def test_switched_back_by_hand_the_way_back_still_puts_debian_s_file_back(tmp_path):
    """The hint said `systemctl enable --force sddm.service`; --login-screen-off after it puts the
    file back too (it named greetd for good, and Ubuntu's SDDM would not start)."""
    (tmp_path / "etc/greetd").mkdir(parents=True)
    (tmp_path / "etc/greetd/config.toml").write_text('[terminal]\nvt = 7\n\n[default_session]\ncommand = "agreety"\n')
    (tmp_path / "etc/X11").mkdir(parents=True)
    ddm = tmp_path / "etc/X11/default-display-manager"
    ddm.write_text("/usr/bin/sddm\n")
    (tmp_path / "display-manager.service").symlink_to("/usr/lib/systemd/system/sddm.service")
    assert login_install(tmp_path, "--login-screen").returncode == 0
    (tmp_path / "display-manager.service").unlink()                     # by hand, as the hint says
    (tmp_path / "display-manager.service").symlink_to("/usr/lib/systemd/system/sddm.service")
    off = login_install(tmp_path, "--login-screen-off")
    assert off.returncode == 0, off.stdout + off.stderr
    assert ddm.read_text() == "/usr/bin/sddm\n" and not list((tmp_path / "etc").rglob("*.before-syncrain"))


def test_greetd_s_command_reads_login_sh_rather_than_running_it(tmp_path):
    """A policy that refuses to run the file (SELinux, fapolicyd) cannot stop sh reading it; and
    without it, greetd's text login asks. (A failed exec ended the shell before the text login.)"""
    (tmp_path / "etc/greetd").mkdir(parents=True)
    (tmp_path / "etc/greetd/config.toml").write_text('[terminal]\nvt = 1\n\n[default_session]\ncommand = "agreety"\n')
    assert login_install(tmp_path, "--login-screen").returncode == 0
    from syncrain import greetdconf
    command = greetdconf.unquote(greetdconf.read((tmp_path / "etc/greetd/config.toml").read_text())
                                 ["default_session"]["command"])
    import shlex
    login = tmp_path / "lib/syncrain/login/login.sh"
    login.write_text('echo "login.sh read"\n')
    login.chmod(0o644)                                 # not to be run: read
    assert subprocess.run(shlex.split(command), capture_output=True, text=True).stdout == "login.sh read\n"
    stub(tmp_path / "bin", "agreety", 'echo "text login $*"')
    login.unlink()
    said = subprocess.run(shlex.split(command), capture_output=True, text=True).stdout
    assert said == "text login --cmd startplasma-wayland\n"


def test_a_link_among_the_operator_s_files_brings_nothing_of_root_s_into_the_login_screen(another_user):
    """root writes the login screen's copies, but the user reads what goes into them: a link among the
    operator's settings to a file only root may read is left out, said so, and the install goes on."""
    user = another_user
    secret = user.unreadable("root's own\n")
    config = user.base / "config"
    config.mkdir()
    (config / "kxkbrc").symlink_to(secret)
    (config / "kcminputrc").write_text("[Keyboard]\nNumLock=0\n")
    done = user.install("--login-screen")
    assert done.returncode == 0, done.stdout + done.stderr
    lib = user.base / "lib"
    assert sorted(p.name for p in (lib / "kde").iterdir()) == ["kcminputrc"]
    assert f"not copied, this user cannot read it: {config}/kxkbrc" in done.stdout
    assert not [p for p in lib.rglob("*") if p.is_file() and "root's own" in p.read_text(errors="replace")]
    assert not [c for c in user.calls("sudo") if str(config) in c], "root opened none of the operator's settings"
    assert not [c for c in user.calls("sudo") if str(user.base / "home") in c], "nor the app in their folder"
    (lib / "kde/kxkbrc").write_text("root's own\n")    # what build 17 made of that link, as root,
    (user.base / "state/config").mkdir()                # and what login.sh copied of it at a start
    (user.base / "state/config/kxkbrc").write_text("root's own\n")
    again = user.install()                              # the next build copies the settings again, safely
    assert again.returncode == 0, again.stdout + again.stderr
    assert sorted(p.name for p in (lib / "kde").iterdir()) == ["kcminputrc"]
    assert not (user.base / "state/config/kxkbrc").exists()
    assert not [c for c in user.calls("sudo") if str(config) in c]


def test_a_link_in_place_of_the_app_is_copied_as_what_it_points_at_and_that_does_not_change(another_user):
    """The app the login screen copies is a folder the operator can change. Were it a link, root's copy
    holds what it points at, as root's files: greetd's user never runs code through a link the
    operator can still change. What the link points at keeps its permissions."""
    user = another_user
    elsewhere = user.base / "elsewhere"
    shutil.copytree(user.src / "syncrain", elsewhere / "syncrain", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(user.src / "BUILD_NUMBER", elsewhere / "BUILD_NUMBER")      # beside the package, where it looks
    release = user.base / "release"
    release.mkdir()
    for name in ("install.sh", "BUILD_NUMBER"):
        shutil.copy2(user.src / name, release / name)
    (release / "syncrain").symlink_to(elsewhere / "syncrain")
    first = user.install("--login-screen", src=release)
    assert first.returncode == 0, first.stdout + first.stderr
    (elsewhere / "syncrain").chmod(0o700)
    (elsewhere / "syncrain/app.py").chmod(0o600)
    again = user.install(src=release)                  # a newer build: the login screen's copy follows
    assert again.returncode == 0 and "the login screen: build" in again.stdout, again.stdout + again.stderr
    copy = user.base / "lib/syncrain"
    assert copy.is_dir() and not copy.is_symlink() and (copy / "app.py").is_file()
    assert not [p for p in copy.rglob("*") if p.is_symlink()]
    assert [oct(p.stat().st_mode & 0o777) for p in (elsewhere / "syncrain", elsewhere / "syncrain/app.py")] == [
        "0o700", "0o600"]


def test_each_start_takes_the_settings_as_installed_now(tmp_path):
    """Nothing left in the greeter's settings from an earlier start counts: not a copy of a setting no
    longer installed (build 17 copied a link's target as root), not a KWin setting someone put there."""
    write_sessions(tmp_path / "share")
    (tmp_path / "state/config").mkdir(parents=True)
    (tmp_path / "state/config/kxkbrc").write_text("root's own\n")
    (tmp_path / "state/config/kwinrc").write_text("[Wayland]\nInputMethod=/tmp/sees-every-key\n")
    (tmp_path / "state/data").mkdir()
    (tmp_path / "state/data/left.txt").write_text("from before\n")
    env = dict(os.environ, XDG_DATA_DIRS=str(tmp_path / "share"), SYNCRAIN_LOGIN_STATE=str(tmp_path / "state"),
               SYNCRAIN_LOGIN_KWIN="false", SYNCRAIN_LOGIN_TEXT=str(stub(tmp_path / "bin", "agreety", "exit 0")),
               SYNCRAIN_PYTHON=sys.executable, SYNCRAIN_LOGIN_CONFIG=str(tmp_path / "none.json"))
    done = subprocess.run(["sh", str(ROOT / "syncrain/login/login.sh")], env=env, capture_output=True, text=True,
                          timeout=60)
    assert done.returncode == 0, done.stdout + done.stderr
    assert not [p for p in (tmp_path / "state/config").rglob("*") if p.name in ("kxkbrc", "kwinrc")]
    assert not (tmp_path / "state/data/left.txt").exists()


def test_the_cache_stays_while_the_build_does(tmp_path):
    """Compiled shaders and QML save seconds at each start; made by another build, they go."""
    write_sessions(tmp_path / "share")
    cache = tmp_path / "state/cache"
    (cache / "qmlcache").mkdir(parents=True)
    (cache / "qmlcache/old.qmlc").write_text("another build's")
    (cache / "build").write_text("1\n")
    env = dict(os.environ, XDG_DATA_DIRS=str(tmp_path / "share"), SYNCRAIN_LOGIN_STATE=str(tmp_path / "state"),
               SYNCRAIN_LOGIN_KWIN="false", SYNCRAIN_LOGIN_TEXT=str(stub(tmp_path / "bin", "agreety", "exit 0")),
               SYNCRAIN_PYTHON=sys.executable, SYNCRAIN_LOGIN_CONFIG=str(tmp_path / "none.json"))

    def start():
        done = subprocess.run(["sh", str(ROOT / "syncrain/login/login.sh")], env=env, capture_output=True,
                              text=True, timeout=60)
        assert done.returncode == 0, done.stdout + done.stderr
    start()
    assert not (cache / "qmlcache").exists() and (cache / "build").read_text() == f"{build.BUILD_NUMBER}\n"
    (cache / "qmlcache").mkdir()
    (cache / "qmlcache/this.qmlc").write_text("this build's")
    start()
    assert (cache / "qmlcache/this.qmlc").exists()


def test_the_diagnosis_says_which_login_screen_starts_and_what_it_said(tmp_path, monkeypatch):
    from syncrain.diagnose import login_lines
    (tmp_path / "dm").symlink_to("/usr/lib/systemd/system/greetd.service")
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib/BUILD_NUMBER").write_text("16\n")
    (tmp_path / "config.toml").write_text(f'[default_session]\ncommand = "{tmp_path}/lib/syncrain/login/login.sh"\n')
    (tmp_path / "display-manager.before-syncrain").write_text("plasmalogin.service\n")
    (tmp_path / "state").mkdir()
    (tmp_path / "state/login.log").write_text("syncrain-login: 07:00:01.2 rain started (pid 9)\nnoise\n"
                                              "syncrain: 30.0 fps at 2560x1440 (area 0)\n"
                                              "syncrain-login: 07:00:01.9 box shown\n")
    for key, value in (("DM_LINK", "dm"), ("LOGIN_LIB", "lib"), ("GREETD_CONFIG", "config.toml"), ("LOGIN_STATE", "state")):
        monkeypatch.setenv(f"SYNCRAIN_{key}", str(tmp_path / value))
    assert login_lines() == [
        "display manager at boot: greetd.service", "greetd runs syncrain's login screen",
        f"syncrain's login screen: build 16 in {tmp_path}/lib",
        "before syncrain's login screen: plasmalogin.service (--login-screen-off goes back to it)",
        f"the last start ({tmp_path}/state/login.log):",
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


#: Runs a command as greetd's machine would: what it leaves behind is reaped at once (systemd does
#: that as PID 1; a sandbox's PID 1 may take a second or never), and SIGTERM is passed on to it.
REAPER = """
import ctypes, os, signal, sys
ctypes.CDLL(None).prctl(36, 1, 0, 0, 0)            # PR_SET_CHILD_SUBREAPER: orphans come here
child = os.fork()
if child == 0:
    os.execvp(sys.argv[1], sys.argv[1:])
signal.signal(signal.SIGTERM, lambda *_: os.kill(child, signal.SIGTERM))
while True:
    pid, status = os.waitpid(-1, 0)
    if pid == child:
        sys.exit(os.waitstatus_to_exitcode(status) & 0xFF)
"""


def alive(pid: int) -> bool:
    """The process is there and not a zombie waiting to be reaped."""
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return False


@pytest.mark.parametrize("hangs", [False, True], ids=["kwin goes", "kwin hangs"])
def test_when_greetd_stops_the_login_screen_its_kwin_goes_too(tmp_path, hangs):
    """greetd signals login.sh alone: when a login's session is due and the greeter is slow to go, and
    when greetd itself stops or restarts. KWin runs in a session of its own, so login.sh stops it, and
    goes only once it has gone: at once, or after 3 s for a KWin that hangs (greetd kills at 10)."""
    write_sessions(tmp_path / "share")
    started = tmp_path / "kwin.pid"
    deaf = "trap '' TERM; " if hangs else ""
    kwin = stub(tmp_path / "bin", "kwin", f"{deaf}echo $$ > {started}.new && mv {started}.new {started}; exec sleep 600")
    env = dict(os.environ, XDG_DATA_DIRS=str(tmp_path / "share"), SYNCRAIN_LOGIN_STATE=str(tmp_path / "state"),
               SYNCRAIN_LOGIN_KWIN=str(kwin), SYNCRAIN_LOGIN_TEXT=str(stub(tmp_path / "bin", "agreety", "exit 0")),
               SYNCRAIN_PYTHON=sys.executable, SYNCRAIN_LOGIN_CONFIG=str(tmp_path / "none.json"),
               SYNCRAIN_LOGIN_WATCHDOG="600")
    with open(tmp_path / "out.txt", "w") as out:
        login = subprocess.Popen([sys.executable, "-c", REAPER, "sh", str(ROOT / "syncrain/login/login.sh")],
                                 env=env, stdout=out, stderr=out)
    pid = None
    try:
        deadline = time.monotonic() + 30
        while not started.exists():
            assert login.poll() is None and time.monotonic() < deadline, "KWin never started"
            time.sleep(0.1)
        pid = int(started.read_text())
        signalled = time.monotonic()
        login.send_signal(signal.SIGTERM)
        assert login.wait(timeout=20) == 0, "login.sh did not stop KWin and leave"
        took = time.monotonic() - signalled
        settle = time.monotonic() + 1
        while alive(pid) and time.monotonic() < settle:     # the kernel finishing a kill
            time.sleep(0.05)
        assert not alive(pid), "login.sh went while KWin kept the screens"
        assert (2.5 < took < 8) if hangs else took < 2.5, took
    finally:
        if login.poll() is None:
            login.kill()
        if pid and alive(pid):
            os.kill(pid, signal.SIGKILL)


def test_what_pam_asks_after_the_password_goes_to_whoever_answers_it(tmp_path):
    """A second factor: the password answers only the first secret prompt; the code is asked for,
    and what PAM says comes as it comes."""
    fake = FakeGreetd(tmp_path / "sock", more=[("info", "Open the app on your phone", None),
                                               ("secret", "Verification code:", "123456")])
    asked, told = [], []
    ok, said = Greetd(fake.path).login("op", "right", ["x"], [], ask=lambda p, s: asked.append((p, s)) or "123456",
                                       tell=told.append)
    assert ok, said
    assert asked == [("Verification code:", True)] and told == ["Welcome", "Open the app on your phone"]
    assert [r.get("response") for r in fake.requests if r["type"] == "post_auth_message_response"] == [
        None, "right", None, "123456"], "the password went to the password prompt alone"
    fake.close()


def test_a_wrong_second_factor_is_not_called_a_wrong_password(tmp_path):
    fake = FakeGreetd(tmp_path / "sock", more=[("secret", "Verification code:", "123456")])
    ok, said = Greetd(fake.path).login("op", "right", ["x"], [], ask=lambda p, s: "000000")
    assert not ok and said.endswith("Not accepted") and {"type": "cancel_session"} in fake.requests
    fake.close()


def test_without_anyone_to_ask_the_login_stops_and_says_to_use_the_text_login(tmp_path):
    fake = FakeGreetd(tmp_path / "sock", more=[("visible", "Token:", "x")])
    ok, said = Greetd(fake.path).login("op", "right", ["x"], [])
    assert not ok and "Token: (more than a password: use Text login)" in said
    assert fake.requests[-1] == {"type": "cancel_session"} and not fake.started()
    fake.close()
