"""The Plasma wallpaper (syncrain/plasma/): the SyncRain item, the wallpaper package around it, and
its settings page, run by Qt's qml tool in a headless Sway.

Needs Nix (the item is built with Nix's Qt, as tests/nix/ builds the package) and sway. libplasma's
WallpaperItem is stood in for by tests/plasma/stub/: it needs a running Plasma shell, which no lane
has (`docs/agent/ENVIRONMENT.md`). The item draws with the native wallpaper's passes on the context
Qt Quick gives it; Nix's Mesa is not the GTK host's, so the frames agree to within a level or so,
not to the bit.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.conftest import need
from tests.support import MOMENT, headless_sway, mean_abs_diff

HERE = Path(__file__).resolve().parent
LOOK = ["--glow", "0", "--bg-gain", "0.5", "--snow", "off", "--hieroglyphs", "0.6", "--speed", "2"]


@pytest.fixture(scope="module")
def built(root, tmp_path_factory):
    need(shutil.which("nix-build") is not None, "no Nix")
    nixpkgs = os.environ.get("SYNCRAIN_NIXPKGS")
    need(bool(nixpkgs) and os.path.isdir(nixpkgs or ""), "SYNCRAIN_NIXPKGS does not name a nixpkgs checkout")
    need(shutil.which("sway") is not None, "no sway")
    out = {}
    for name in ("plugin", "qtdeclarative", "kirigami"):
        link = tmp_path_factory.mktemp("plasma") / name
        done = subprocess.run(["nix-build", str(HERE / "plasma.nix"), "-A", name, "--arg", "src", str(root),
                               "--arg", "nixpkgs", nixpkgs, "-o", str(link)],
                              capture_output=True, text=True, timeout=1800)
        assert done.returncode == 0, done.stderr[-3000:]
        out[name] = link.resolve()
    return out


@pytest.fixture
def qml(root, built, tmp_path):
    """Runs Qt's qml tool on a file of tests/plasma/ in a 640x360 headless Sway: (status, output)."""
    command = tmp_path / "syncrain"
    command.write_text(f"#!/bin/sh\ncd {root} && exec {sys.executable} -m syncrain \"$@\"\n")
    command.chmod(0o755)
    imports = [built["plugin"] / "lib/qt-6/qml", built["qtdeclarative"] / "lib/qt-6/qml",
               built["kirigami"] / "lib/qt-6/qml", HERE / "stub"]

    def run(name, *args, **extra):
        with headless_sway(tmp_path / f"run-{name}", screen="640x360") as session:
            env = {k: v for k, v in os.environ.items()
                   if k not in ("PYTHONPATH", "GI_TYPELIB_PATH", "LD_LIBRARY_PATH", "LD_PRELOAD", "DISPLAY",
                                "QT_PLUGIN_PATH", "QML_IMPORT_PATH", "QML2_IMPORT_PATH")}
            env.update(session, QT_QPA_PLATFORM="wayland", QSG_RHI_BACKEND="opengl", QT_FORCE_STDERR_LOGGING="1",
                       QML_IMPORT_PATH=":".join(map(str, imports)), SYNCRAIN_COMMAND=str(command),
                       XDG_CACHE_HOME=str(tmp_path / "cache"), XDG_RUNTIME_DIR=session["XDG_RUNTIME_DIR"])
            env.update(extra)
            done = subprocess.run([str(built["qtdeclarative"] / "bin/qml"), str(HERE / name), "--", *map(str, args)],
                                  env=env, capture_output=True, text=True, timeout=180)
        return done.returncode, done.stdout + done.stderr
    return run


@pytest.mark.parametrize("look", [[], LOOK], ids=["defaults", "every-option"])
def test_the_item_draws_the_gtk_host_s_frame(qml, app, tmp_path, look):
    item, gtk = tmp_path / "item.png", tmp_path / "gtk.png"
    code, said = qml("shot.qml", item, MOMENT, *look)
    assert code == 0 and item.exists(), said
    done = app(["--window", "--size", "640x360", "--time", str(MOMENT), "--screenshot", str(gtk), *look])
    assert done.returncode == 0, done.stderr
    assert mean_abs_diff(item, gtk) < 0.5


def test_the_wallpaper_package_passes_its_settings_on(qml, app, root, tmp_path):
    """main.qml turns the settings into syncrain's options: the frame is the GTK host's with them."""
    config = {"Theme": "matrix", "Channel": "friends", "Fps": 30, "Logo": "", "Rainbow": "off", "Glow": 1,
              "Bloom": 0.5, "BgGain": 0.7, "Speed": 1.5, "Density": 1.2, "Hieroglyphs": 0, "Snow": True,
              "PauseUnder": "maximized", "Scale": 1, "ExtraArgs": "--drift 0"}
    item, gtk = tmp_path / "item.png", tmp_path / "gtk.png"
    main = root / "syncrain/plasma/package/contents/ui/main.qml"
    code, said = qml("package.qml", item, main.as_uri(), json.dumps(config), SYNCRAIN_TEST_TIME=str(MOMENT))
    assert code == 0 and item.exists(), said
    assert ('"--theme","matrix","--channel","friends","--rainbow","off","--glow","1","--bloom","0.5",'
            '"--bg-gain","0.7","--speed","1.5","--density","1.2","--hieroglyphs","0","--drift","0"') in said, said
    done = app(["--window", "--size", "640x360", "--time", str(MOMENT), "--screenshot", str(gtk), "--theme", "matrix",
                "--channel", "friends", "--rainbow", "off", "--bloom", "0.5", "--bg-gain", "0.7", "--speed", "1.5",
                "--density", "1.2", "--hieroglyphs", "0", "--drift", "0"])
    assert done.returncode == 0, done.stderr
    assert mean_abs_diff(item, gtk) < 0.5


def test_the_settings_page_loads(qml, root):
    code, said = qml("settings.qml", (root / "syncrain/plasma/package/contents/ui/config.qml").as_uri())
    assert code == 0, said
    assert "loaded: matrix 20" in said, said
    assert not [line for line in said.splitlines() if "Error" in line or "is not defined" in line], said


def test_without_syncrain_the_item_says_why(qml, tmp_path):
    code, said = qml("shot.qml", tmp_path / "none.png", MOMENT, SYNCRAIN_COMMAND=str(tmp_path / "missing"))
    assert code == 3, said
    assert "could not be started" in said or "write-scene failed" in said, said


def test_under_kwin_a_maximized_window_stops_the_drawing(root, built, tmp_path):
    """On the desktop the item asks KWin which screens a window covers (syncrain/native/kwin.c, as
    the native wallpaper does) and draws nothing on a covered one."""
    from tests.kwin.test_the_kwin_desktop import Proc, Session
    kwin = os.environ.get("SYNCRAIN_KWIN") or shutil.which("kwin_wayland")
    need(kwin is not None, "no KWin 6 (set SYNCRAIN_KWIN)")
    command = tmp_path / "syncrain"
    command.write_text(f"#!/bin/sh\ncd {root} && exec {sys.executable} -m syncrain \"$@\"\n")
    command.chmod(0o755)
    (tmp_path / "kwin").mkdir()
    session = Session(tmp_path / "kwin", screens=1, size=(320, 180))
    item = None
    try:
        imports = [built["plugin"] / "lib/qt-6/qml", built["qtdeclarative"] / "lib/qt-6/qml"]
        env = {k: v for k, v in session.env().items() if k not in ("PYTHONPATH", "GI_TYPELIB_PATH", "LD_LIBRARY_PATH")}
        env.update(QT_QPA_PLATFORM="wayland", QSG_RHI_BACKEND="opengl", QT_FORCE_STDERR_LOGGING="1",
                   QML_IMPORT_PATH=":".join(map(str, imports)), SYNCRAIN_COMMAND=str(command))
        item = Proc([str(built["qtdeclarative"] / "bin/qml"), str(HERE / "covered.qml")], env)
        item.wait_for(r"status: drawing", timeout=60)

        def frames(after):
            return [int(line.split()[-1]) for t, line in list(item.lines) if t >= after and "frames:" in line]

        win = session.window("maximized", 0)
        try:
            t, _ = item.wait_for(r"covered: true", timeout=30)
            time.sleep(3)
            counts = frames(t + 0.6)
            assert counts and counts[-1] == counts[0], f"frames drawn on a covered screen: {counts}"
        finally:
            win.stop()
        t, _ = item.wait_for(r"covered: false", after=t, timeout=30)
        time.sleep(2)
        counts = frames(t)
        assert counts and counts[-1] > counts[0] + 10, f"no frames once the screen showed again: {counts}"
    finally:
        if item:
            item.stop()
        session.stop()


def test_install_sh_puts_it_where_plasma_and_the_lock_screen_look(root, built, tmp_path):
    """install.sh --plasma, with Nix's Qt and CMake standing in for Arch's: the module in Qt's QML
    folder, the package where Plasma looks for wallpapers, both made the wallpaper (the shell's
    scripting and kscreenlockerrc, stubs here); --uninstall takes it all back."""
    nixpkgs = os.environ["SYNCRAIN_NIXPKGS"]
    stubs, qmldir, log = tmp_path / "stubs", tmp_path / "qt-qml", tmp_path / "calls.log"
    stubs.mkdir()
    for name, body in {
        "qtpaths6": f'echo "{qmldir}"',
        "sudo": '"$@"',
        "systemctl": "exit 1",
        "dbus-send": f'echo "dbus-send $*" >> "{log}"',
        "kwriteconfig6": f'echo "kwriteconfig6 $*" >> "{log}"',
        "kreadconfig6": "echo org.syncrain.wallpaper",
    }.items():
        (stubs / name).write_text(f"#!/bin/sh\n{body}\n")
        (stubs / name).chmod(0o755)
    home = tmp_path / "home"
    env = {"HOME": str(home), "LANG": "C.UTF-8", "PATH": f"{stubs}:{os.path.dirname(sys.executable)}:/usr/bin:/bin",
           "NIX_PATH": f"nixpkgs={nixpkgs}"}
    for key in ("GI_TYPELIB_PATH", "NIX_REMOTE", "NIX_SSL_CERT_FILE", "SSL_CERT_FILE"):
        if key in os.environ:
            env[key] = os.environ[key]

    def install(*args):
        inner = f"export PATH={stubs}:{os.path.dirname(sys.executable)}:$PATH; bash {root}/install.sh --no-deps {' '.join(args)}"
        return subprocess.run([shutil.which("nix-shell"), "-p", "cmake", "pkg-config", "dbus", "qt6.qtbase",
                               "qt6.qtdeclarative", "--run", inner], cwd=root, env=env, capture_output=True,
                              text=True, timeout=1200)

    done = install("--plasma", "--theme", "matrix")
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-3000:]
    module = qmldir / "org/syncrain"
    assert (module / "qmldir").is_file() and list(module.glob("*.so")), done.stdout
    package = home / ".local/share/plasma/wallpapers/org.syncrain.wallpaper"
    assert json.loads((package / "metadata.json").read_text())["KPlugin"]["Id"] == "org.syncrain.wallpaper"
    calls = log.read_text()
    assert "org.kde.PlasmaShell.evaluateScript" in calls and 'd.wallpaperPlugin = "org.syncrain.wallpaper"' in calls
    assert '{"Theme": "matrix"}' in calls, calls
    assert "kwriteconfig6 --file kscreenlockerrc --group Greeter --key WallpaperPlugin org.syncrain.wallpaper" in calls
    assert ("kwriteconfig6 --file kscreenlockerrc --group Greeter --group Wallpaper --group org.syncrain.wallpaper "
            "--group General --key Theme matrix") in calls

    log.write_text("")
    done = install("--uninstall")
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-3000:]
    assert not module.exists() and not package.exists()
    calls = log.read_text()
    assert "d.wallpaperPlugin = 'org.kde.image'" in calls and "WallpaperPlugin --delete" in calls, calls
