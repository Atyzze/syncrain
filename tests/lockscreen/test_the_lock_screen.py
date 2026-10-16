"""syncrain's lock screen (syncrain/lockscreen/): the rain and syncrain's box inside KDE Plasma's own
locker, kscreenlocker_greet, the way install.sh --lock-screen sets it up.

Needs Nix (the module is built with Nix's Qt, and Plasma 6.7's locker, Qt's Wayland plugin and
libei come from the same nixpkgs: SYNCRAIN_NIXPKGS), sway and grim, KWin 6 (SYNCRAIN_KWIN), and, for
the real lock, root to give PAM a service `kde` of the test's own (/etc/pam.d/kde, only where there
is none, removed after). What is checked:

* the item draws the desktop's frame: the native wallpaper's from the same nixpkgs (the same Mesa),
  to the pixel, beside the box;
* the box answers PAM as Plasma 6.7's own lock screen does: a wrong password is said and cleared,
  PAM is asked again only after its delay, a password typed during it is kept for the next question,
  PAM's Dutch prompt does not hide the refusal, the right one quits the locker; and without the
  rain's module the box still unlocks, on black;
* a real headless KWin, locked over D-Bus, starts kscreenlocker_greet, which loads syncrain's lock
  screen from what KWin's unit is given (PLASMA_DEFAULT_SHELL, QML_IMPORT_PATH) on both screens; a
  wrong password typed on KWin's keyboard (libei, as a person types) leaves it locked, the right
  one a second after another wrong one (inside PAM's 2 s delay) unlocks it, and PAM saw exactly
  what was typed.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.conftest import ROOT, need
from tests.support import MOMENT, headless_sway

HERE = Path(__file__).resolve().parent
PACKAGE = ROOT / "syncrain/lockscreen/package"
LOCKSCREEN_QML = PACKAGE / "contents/lockscreen/LockScreen.qml"
PAM_SERVICE = Path("/etc/pam.d/kde")
PAM_MARK = "# syncrain tests/lockscreen"
#: The box's rectangle on a 640x360 screen, with room: the frames are compared outside it.
BOX = (150, 100, 490, 260)


@pytest.fixture(scope="module")
def built(root, tmp_path_factory):
    need(shutil.which("nix-build") is not None, "no Nix")
    nixpkgs = os.environ.get("SYNCRAIN_NIXPKGS")
    need(bool(nixpkgs) and os.path.isdir(nixpkgs or ""), "SYNCRAIN_NIXPKGS does not name a nixpkgs checkout")
    need(shutil.which("sway") is not None, "no sway")
    out = {}
    for name in ("lockscreen", "qtdeclarative", "plasma", "libei", "wallpaper"):
        link = tmp_path_factory.mktemp("lock") / name
        done = subprocess.run(["nix-build", str(HERE / "lockscreen.nix"), "-A", name, "--arg", "src", str(root),
                               "--arg", "nixpkgs", nixpkgs, "-o", str(link)],
                              capture_output=True, text=True, timeout=3600)
        assert done.returncode == 0, done.stderr[-3000:]
        out[name] = link.resolve()
    return out


@pytest.fixture(scope="module")
def scene(tmp_path_factory):
    """The scene install.sh writes, with no settings file: the default look."""
    path = tmp_path_factory.mktemp("scene") / "lock-screen.scene"
    done = subprocess.run([sys.executable, "-m", "syncrain", "--config", "none", "--write-scene", str(path)],
                          cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT)), capture_output=True, text=True,
                          timeout=120)
    assert done.returncode == 0 and path.stat().st_size > 1_000_000, done.stderr
    return path


def clean_env(**extra) -> dict:
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONPATH", "GI_TYPELIB_PATH", "LD_LIBRARY_PATH", "LD_PRELOAD", "DISPLAY", "WAYLAND_DISPLAY",
                        "QT_PLUGIN_PATH", "QML_IMPORT_PATH", "QML2_IMPORT_PATH", "DBUS_SESSION_BUS_ADDRESS")}
    env.update(extra)
    return env


@pytest.fixture
def greeter(built, scene, tmp_path):
    """tests/lockscreen/greeter.qml in a 640x360 headless Sway: greeter(what, *args, module=True) ->
    (status, output)."""
    def run(what, *args, module=True):
        imports = ([built["lockscreen"] / "lib/qt-6/qml"] if module else []) + [built["qtdeclarative"] / "lib/qt-6/qml"]
        with headless_sway(tmp_path / f"run-{what}", screen="640x360") as session:
            env = clean_env(**session, QT_QPA_PLATFORM="wayland", QSG_RHI_BACKEND="opengl",
                            QT_FORCE_STDERR_LOGGING="1", QML_IMPORT_PATH=":".join(map(str, imports)),
                            SYNCRAIN_LOCK_SCENE=str(scene), SYNCRAIN_TEST_TIME=str(MOMENT))
            done = subprocess.run([str(built["qtdeclarative"] / "bin/qml"), str(HERE / "greeter.qml"), "--",
                                   LOCKSCREEN_QML.as_uri(), what, *map(str, args)],
                                  env=env, capture_output=True, text=True, timeout=180)
        return done.returncode, done.stdout + done.stderr
    return run


def outside_the_box(a: Path, b: Path) -> float:
    """Mean absolute difference of two 640x360 frames, the box's rectangle left out."""
    from PIL import Image, ImageChops
    x0, y0, x1, y1 = BOX
    total = n = 0
    diff = ImageChops.difference(Image.open(a).convert("RGB"), Image.open(b).convert("RGB")).convert("L")
    for (left, top, right, bottom) in ((0, 0, 640, y0), (0, y1, 640, 360), (0, y0, x0, y1), (x1, y0, 640, y1)):
        region = diff.crop((left, top, right, bottom))
        hist = region.histogram()
        total += sum(i * c for i, c in enumerate(hist))
        n += region.width * region.height
    return total / n


def native_frame(built, tmp_path: Path) -> Path:
    """The native wallpaper from the same nixpkgs as the lock screen, on its own 640x360 screen at
    MOMENT, as the compositor shows it (the desktop's frame there; the GTK host's is the same)."""
    from tests.support import grab, grab_settled
    need(shutil.which("grim") is not None, "no grim")
    shot = tmp_path / "native.png"
    with headless_sway(tmp_path / "run-native", screen="640x360") as session:
        empty = Path(session["XDG_RUNTIME_DIR"]) / "empty.png"
        grab(session, empty)
        # as clean as the lock screen's own: nothing of this machine's GL in the way of Nix's
        env = clean_env(**session, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1", XDG_CURRENT_DESKTOP="sway",
                        SYNCRAIN_WALLPAPER=str(built["wallpaper"] / "libexec/syncrain/syncrain-wallpaper"))
        proc = subprocess.Popen([sys.executable, "-m", "syncrain", "--config", "none", "--time", str(MOMENT)],
                                cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline, line = time.monotonic() + 60, ""
            while time.monotonic() < deadline and not line.startswith("syncrain build"):
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
            if ", native wallpaper, " not in line:
                proc.kill()
                _, err = proc.communicate(timeout=30)
                pytest.fail(f"the native wallpaper did not start: {line!r}\n{err[-3000:]}")
            grab_settled(session, shot, unlike=empty)
        finally:
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
                try:
                    proc.communicate(timeout=30)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate(timeout=10)
    return shot


def test_the_lock_screen_draws_the_desktop_s_frame(greeter, built, tmp_path):
    shot = tmp_path / "lock.png"
    code, said = greeter("shot", shot)
    assert code == 0 and shot.exists(), said
    assert "flow: rain drawing" in said and "the lock screen draws the rain" in said, said
    # the same Mesa as the lock screen's Qt: to the pixel. Against the GTK host on another Mesa
    # (25.2 here, the lane's Qt has 26.2) it was 1.8% darker, the two llvmpipes' own difference.
    assert outside_the_box(shot, native_frame(built, tmp_path)) == 0


def steps(said: str) -> list[str]:
    return [line.split("flow: ", 1)[1] for line in said.splitlines() if "flow: " in line]


def test_the_box_unlocks_with_what_pam_accepts_and_says_what_it_refused(greeter):
    """The right password typed at once after a wrong one, while PAM waits out its 2 s delay: kept,
    and handed over when PAM asks again; PAM is never started too soon, nothing typed is lost."""
    code, said = greeter("flow")
    assert code == 0, said
    lines = steps(said)
    assert lines[0] == "asked 1 times, focus true", lines
    assert lines[1:] == ["responded wrong", "after the wrong one, field '', message 'Unlocking failed'",
                         "responded right", "stopped"], lines


def test_pam_asking_again_in_dutch_leaves_the_refusal_said(greeter):
    code, said = greeter("again")
    assert code == 0, said
    assert steps(said)[1:] == ["responded wrong", "after the wrong one, field '', message 'Unlocking failed'",
                               "asked again, message 'Unlocking failed'", "responded right", "stopped"], said


def test_a_screen_plugged_in_again_while_pam_asks_still_unlocks(greeter):
    """kscreenlocker makes a screen's lock screen anew when it comes back; PAM's question is the
    locker's, not the screen's, so the new box's password still goes to it."""
    code, said = greeter("replug")
    assert code == 0, said
    assert steps(said) == ["replugged", "responded right", "stopped"], said


def test_a_question_whose_answer_shows_is_answered(greeter):
    code, said = greeter("visible")
    assert code == 0, said
    assert steps(said) == ["responded right", "stopped"], said


def test_a_question_asked_before_the_screen_came_is_still_answered(greeter):
    """Every screen gone while locked and one back: kscreenlocker 6.7 makes the new view on a new
    QML engine, whose singletons never saw PAM's question. The password typed there answers it."""
    code, said = greeter("fresh")
    assert code == 0, said
    assert steps(said) == ["loaded late", "responded right", "stopped"], said


def test_a_yes_said_while_no_screen_was_there_unlocks(greeter):
    code, said = greeter("unlocked")
    assert code == 0, said
    assert steps(said) == ["loaded late", "stopped"], said


def test_a_password_sent_again_during_the_check_does_not_answer_the_second_factor(greeter):
    """The password, then PAM's second question (a one-time code): what was typed while the password
    was checked is not the code, so it is not sent, and the second question is said."""
    code, said = greeter("twofactor")
    assert code == 0, said
    assert steps(said) == ["responded right",
                           "second question, answers so far [\"right\"], message 'Verificatiecode: '",
                           "responded 123456", "stopped"], said


def test_a_question_that_wants_only_enter_is_answered_by_enter(greeter):
    code, said = greeter("enter")
    assert code == 0, said
    assert steps(said) == ["responded ", "stopped"], said


def test_a_screen_back_while_pam_checks_sends_nothing_to_the_second_factor(greeter):
    """kscreenlocker 6.7 keeps an answer given while PAM checks the last one and hands it to the
    next question: a password typed on a screen that came back then would answer a second factor.
    The new screen sends nothing until PAM asks, and says the second question when it comes."""
    code, said = greeter("checking")
    assert code == 0, said
    assert steps(said) == ["responded right", "loaded late",
                           "second question, answers so far [\"right\"], message 'Verificatiecode: '",
                           "responded 123456", "stopped"], said


def test_a_screen_back_just_after_a_refusal_waits_out_the_delay(greeter):
    code, said = greeter("idle")
    assert code == 0, said
    assert "too soon" not in said, said
    assert steps(said) == ["responded wrong", "loaded late", "responded right", "stopped"], said


def test_two_screens_show_one_box_that_comes_and_goes_with_the_person(built):
    """tests/lockscreen/tst_two_screens.qml, real key and pointer events on two screens: the box is
    away until a key or a moved pointer (KWin's first placing of the pointer not counted), goes after
    the idle time and forgets what was typed, and every screen shows the same text and eye."""
    qd = built["qtdeclarative"]
    # standin/: Plasma's keyboard layout module as KeyboardName.qml uses it
    done = subprocess.run([str(qd / "bin/qmltestrunner"), "-input", str(HERE / "tst_two_screens.qml")],
                          env=clean_env(QT_QPA_PLATFORM="offscreen",
                                        QML_IMPORT_PATH=f"{qd / 'lib/qt-6/qml'}:{HERE / 'standin'}"),
                          capture_output=True, text=True, timeout=180)
    said = done.stdout + done.stderr
    assert done.returncode == 0 and "0 failed" in said, said[-4000:]
    assert said.count("PASS   : qmltestrunner::TwoScreens::test_") == 19, said[-4000:]


def test_without_the_rain_s_module_the_box_still_unlocks(greeter, tmp_path):
    code, said = greeter("flow", module=False)
    assert code == 0 and "responded right" in said, said
    assert "draws no rain" in said, said
    code, said = greeter("shot", tmp_path / "black.png", module=False)
    assert code == 3 and "flow: rain no item" in said, said
    from PIL import Image
    corner = Image.open(tmp_path / "black.png").convert("L").crop((0, 0, 100, 60))
    assert corner.getextrema()[1] < 8, "black where the rain would be"


# ------------------------------------------------------------------ a real lock in KWin

@pytest.fixture
def pam(tmp_path):
    """Plasma's locker asks PAM's service `kde`: here one that accepts "right" and records every try.
    It is in a copy of /etc/pam.d that KWin (and the locker it starts) sees in a mount namespace of
    its own: the machine's PAM is never changed, so a stopped lane leaves nothing that unlocks."""
    need(os.geteuid() == 0, "a mount namespace for PAM's test service needs root")
    need(shutil.which("unshare") is not None, "no unshare (util-linux)")
    # an earlier build's run wrote its test service into the machine's /etc/pam.d, and one stopped
    # half way left it there, unlocking with "right": it goes, and nothing else of PAM's is touched
    if PAM_SERVICE.is_file() and PAM_SERVICE.read_text(errors="replace").startswith(PAM_MARK):
        PAM_SERVICE.unlink()
    tries = tmp_path / "tries.log"
    check = tmp_path / "check-password.sh"
    check.write_text(f'#!/bin/sh\nIFS= read -r pw\necho "$pw" >> "{tries}"\n[ "$pw" = "right" ]\n')
    check.chmod(0o755)
    pam_dir = tmp_path / "pam.d"
    shutil.copytree(PAM_SERVICE.parent, pam_dir, symlinks=True)
    (pam_dir / PAM_SERVICE.name).unlink(missing_ok=True)
    # pam_faildelay: a refusal asks for 2 s, as Arch's pam_unix does
    (pam_dir / PAM_SERVICE.name).write_text(f"{PAM_MARK}\nauth optional pam_faildelay.so delay=2000000\n"
                                            f"auth required pam_exec.so expose_authtok quiet {check}\n"
                                            "account required pam_permit.so\n")
    return tries, pam_dir


class Kwin:
    """A private session bus and a headless KWin with its lock screen, given what install.sh's
    drop-in gives KWin's unit."""

    def __init__(self, tmp, env_extra, pam_dir=None):
        run = Path(f"/tmp/syncrain-lock-{os.getpid()}")      # a socket path stays under 108 bytes
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(mode=0o700)
        self.run = run
        for d in ("home", "config", "cache"):
            (tmp / d).mkdir()
        self.bus = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1",
                                     f"--address=unix:path={run}/bus"], stdout=subprocess.PIPE, text=True,
                                    start_new_session=True)
        self.address = self.bus.stdout.readline().strip()
        self.env = clean_env(XDG_RUNTIME_DIR=str(run), DBUS_SESSION_BUS_ADDRESS=self.address,
                             HOME=str(tmp / "home"), XDG_CONFIG_HOME=str(tmp / "config"),
                             XDG_CACHE_HOME=str(tmp / "cache"), QT_FORCE_STDERR_LOGGING="1", **env_extra)
        self.log_path = tmp / "kwin.log"
        self.log = open(self.log_path, "w")
        # with pam_dir: KWin, and the locker it starts, in a mount namespace where it is /etc/pam.d
        private = [] if pam_dir is None else [
            "unshare", "--mount", "--propagation", "private", "--", "sh", "-c",
            'mount --bind "$0" /etc/pam.d && exec "$@"', str(pam_dir)]
        self.kwin = subprocess.Popen([*private, os.environ["SYNCRAIN_KWIN"], "--virtual", "--width", "640",
                                      "--height", "360", "--output-count", "2", "--no-global-shortcuts",
                                      "--no-kactivities", "--socket", "wayland-kwin"],
                                     env=self.env, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        self.wait(lambda: (run / "wayland-kwin").exists() and self.screensaver() is not None, 40, "KWin did not start")

    def send(self, *args):
        return subprocess.run(["dbus-send", "--session", "--print-reply", *args], env=self.env,
                              capture_output=True, text=True, timeout=30)

    def screensaver(self):
        """Whether KWin's screen is locked (None: KWin does not answer yet)."""
        done = self.send("--dest=org.freedesktop.ScreenSaver", "/ScreenSaver", "org.freedesktop.ScreenSaver.GetActive")
        if done.returncode != 0:
            return None
        return "boolean true" in done.stdout

    def said(self) -> str:
        self.log.flush()
        return self.log_path.read_text(errors="replace")

    def wait(self, ready, seconds, why):
        deadline = time.monotonic() + seconds
        while not ready():
            if self.kwin.poll() is not None or time.monotonic() > deadline:
                raise AssertionError(f"{why}; KWin's log:\n{self.said()[-3000:]}")
            time.sleep(0.25)

    def type(self, built, tmp, *words):
        """Each word and Enter on KWin's keyboard, a second apart, through libei (KWin's RemoteDesktop EIS)."""
        from gi.repository import Gio, GLib
        typer = tmp / "type"
        if not typer.exists():
            ei = built["libei"]
            done = subprocess.run(["cc", "-O2", "-Wall", f"-I{ei}/include/libei-1.0", str(HERE / "type.c"),
                                   f"-L{ei}/lib", f"-Wl,-rpath,{ei}/lib", "-lei", "-o", str(typer)],
                                  capture_output=True, text=True, timeout=120)
            assert done.returncode == 0, done.stderr
        conn = Gio.DBusConnection.new_for_address_sync(
            self.address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, None)
        result, fds = conn.call_with_unix_fd_list_sync(
            "org.kde.KWin", "/org/kde/KWin/EIS/RemoteDesktop", "org.kde.KWin.EIS.RemoteDesktop", "connectToEIS",
            GLib.Variant("(i)", (1,)), GLib.VariantType("(hi)"), Gio.DBusCallFlags.NONE, 10000, None, None)
        fd = fds.get(result.unpack()[0])
        try:
            done = subprocess.run([str(typer), str(fd), *words], pass_fds=(fd,), capture_output=True, text=True,
                                  timeout=60)
        finally:
            os.close(fd)
            conn.close_sync(None)
        assert done.returncode == 0, done.stderr

    def stop(self):
        for p in (self.kwin, self.bus):
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
                try:
                    p.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)
                    p.wait(timeout=5)
        self.log.close()
        shutil.rmtree(self.run, ignore_errors=True)


def test_kwin_locks_with_syncrain_s_lock_screen_and_pam_unlocks_it(built, scene, pam, tmp_path):
    kwin_path = os.environ.get("SYNCRAIN_KWIN")
    need(bool(kwin_path) and os.access(kwin_path or "", os.X_OK), "no KWin 6 (set SYNCRAIN_KWIN)")
    need(shutil.which("dbus-daemon") is not None and shutil.which("cc") is not None, "no dbus-daemon or cc")
    plasma = built["plasma"]
    # what install.sh's drop-in gives KWin's unit, and where an Arch system keeps the rest
    kwin = Kwin(tmp_path, {"PLASMA_DEFAULT_SHELL": "org.syncrain.lockscreen",
                           "QML_IMPORT_PATH": f"{built['lockscreen'] / 'lib/qt-6/qml'}:{plasma / 'lib/qt-6/qml'}",
                           "SYNCRAIN_LOCK_SCENE": str(scene),
                           "XDG_DATA_DIRS": f"{built['lockscreen'] / 'share'}:{plasma / 'share'}",
                           "QT_PLUGIN_PATH": str(plasma / "lib/qt-6/plugins")}, pam_dir=pam[1])
    try:
        assert kwin.screensaver() is False
        done = kwin.send("--dest=org.freedesktop.ScreenSaver", "/ScreenSaver", "org.freedesktop.ScreenSaver.Lock")
        assert done.returncode == 0, done.stderr
        kwin.wait(lambda: kwin.said().count("the lock screen draws the rain on") >= 2, 60,
                  "syncrain's lock screen did not draw on both screens")
        said = kwin.said()
        assert "Virtual-0" in said and "Virtual-1" in said
        # kscreenlocker's words when it would not use the package's lock screen
        assert "Failed to load lockscreen QML" not in said and "Lockscreen QML outdated" not in said, said[-3000:]
        assert kwin.screensaver() is True
        kwin.type(built, tmp_path, "wrong")
        time.sleep(4)
        assert kwin.screensaver() is True, "a wrong password leaves it locked"
        # the right one a second after a wrong one, inside PAM's 2 s delay: kept, not lost
        kwin.type(built, tmp_path, "wrong", "right")
        kwin.wait(lambda: kwin.screensaver() is False, 20, "the right password did not unlock it")
        assert pam[0].read_text().splitlines() == ["wrong", "wrong", "right"]
        assert "Authentication attempt too soon" not in kwin.said(), "PAM restarted inside its delay"
    finally:
        kwin.stop()
