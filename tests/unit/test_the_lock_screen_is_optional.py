"""install.sh --lock-screen and --lock-screen-off, run for real into a throwaway home.

The lock screen is optional, as the login screen is: nothing but --lock-screen writes its files,
the one setting it gives goes to KWin's unit alone (Plasma's shell keeps its layout under the name
of its own shell package, so it must never see PLASMA_DEFAULT_SHELL), and --lock-screen-off takes
away exactly what --lock-screen made. systemctl, cmake and Plasma's config tools are stand-ins
here; the lock screen itself is drawn and unlocked in tests/lockscreen/.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from tests.unit.test_the_installer import install

SHELL = ".local/share/plasma/shells/org.syncrain.lockscreen"
MODULE = ".local/lib/syncrain/qml/org/syncrain"
SCENE = ".local/state/syncrain/lock-screen.scene"
DROPIN = "config/systemd/user/plasma-kwin_wayland.service.d/syncrain-lock-screen.conf"


def stub(folder: Path, name: str, body: str) -> None:
    (folder / name).write_text("#!/bin/sh\n" + body + "\n")
    (folder / name).chmod(0o755)


@pytest.fixture
def plasma(tmp_path):
    """A home on a Plasma started by systemd, as far as install.sh asks: (home, env, calls log)."""
    bin_dir = tmp_path / "stub-bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.log"
    # systemctl: a user session whose KWin is plasma-kwin_wayland.service; every call is logged
    stub(bin_dir, "systemctl", f'echo "systemctl $*" >> "{calls}"\n'
                               'case "$*" in *is-active*) exit 1 ;; esac\nexit 0')
    # cmake: the configure step does nothing, the build step leaves the module where Qt's would
    stub(bin_dir, "cmake", f'echo "cmake $*" >> "{calls}"\n'
                           'if [ "$1" = --build ]; then d="$2/qml/org/syncrain"; mkdir -p "$d"\n'
                           '  echo "module org.syncrain" > "$d/qmldir"; : > "$d/syncrainplugin.qmltypes"\n'
                           '  : > "$d/libsyncrainplugin.so"; fi\nexit 0')
    shell = tmp_path / "shellpackage"                  # what kreadconfig6 says plasmashellrc names
    shell.write_text("")
    stub(bin_dir, "kreadconfig6", f'cat "{shell}"')
    stub(bin_dir, "kwriteconfig6", f'echo "kwriteconfig6 $*" >> "{calls}"')
    env = {"HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "config"), "LANG": "C.UTF-8",
           "PATH": f"{bin_dir}:{os.path.dirname(sys.executable)}:/usr/bin:/bin"}
    for key in ("DISPLAY", "GI_TYPELIB_PATH", "LD_LIBRARY_PATH", "PKG_CONFIG_PATH"):
        if key in os.environ:
            env[key] = os.environ[key]
    return tmp_path, env, calls, shell


def read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def test_an_install_without_it_touches_no_lock_screen(root, plasma):
    tmp, env, calls, _ = plasma
    done = install(root, env, "--autostart")
    assert done.returncode == 0, done.stdout + done.stderr
    for path in (SHELL, MODULE, SCENE, DROPIN):
        assert not (tmp / path).exists(), path
    assert "cmake" not in read(calls) and "kwriteconfig6" not in read(calls)


def test_it_puts_the_lock_screen_in_place_through_kwin_alone(root, plasma):
    tmp, env, calls, _ = plasma
    done = install(root, env, "--lock-screen")
    assert done.returncode == 0, done.stdout + done.stderr
    assert (tmp / SHELL / "contents/lockscreen/LockScreen.qml").is_file()
    assert (tmp / SHELL / "metadata.json").is_file()
    assert (tmp / MODULE / "qmldir").is_file() and (tmp / MODULE / "libsyncrainplugin.so").is_file()
    assert (tmp / SCENE).stat().st_size > 1_000_000, "the scene, made by syncrain --write-scene"
    dropin = read(tmp / DROPIN)
    assert 'Environment="PLASMA_DEFAULT_SHELL=org.syncrain.lockscreen"' in dropin
    assert f'Environment="QML_IMPORT_PATH={tmp / ".local/lib/syncrain/qml"}"' in dropin
    assert f'Environment="SYNCRAIN_LOCK_SCENE={tmp / SCENE}"' in dropin
    assert "systemctl --user daemon-reload" in read(calls)
    assert "log out and back in once" in done.stdout
    # the variable is set nowhere Plasma's shell or anything else would read it
    named = [p for p in tmp.rglob("*") if p.is_file() and p.suffix in ("", ".conf", ".sh", ".service")
             and "stub-bin" not in p.parts and "PLASMA_DEFAULT_SHELL" in p.read_text(errors="replace")]
    assert named == [tmp / DROPIN], named


def test_off_takes_away_exactly_what_it_made(root, plasma):
    tmp, env, calls, _ = plasma
    assert install(root, env, "--lock-screen").returncode == 0
    (tmp / "config/systemd/user/plasma-kwin_wayland.service.d/mine.conf").write_text("[Service]\n")
    done = install(root, env, "--lock-screen-off")
    assert done.returncode == 0, done.stdout + done.stderr
    for path in (SHELL, MODULE, SCENE, DROPIN, ".local/lib/syncrain"):
        assert not (tmp / path).exists(), path
    assert (tmp / "config/systemd/user/plasma-kwin_wayland.service.d/mine.conf").exists(), "not syncrain's"
    assert (tmp / ".local/share/syncrain/syncrain/app.py").exists(), "the wallpaper stays"
    assert "Plasma's own again" in done.stdout
    again = install(root, env, "--lock-screen-off")
    assert again.returncode == 0 and "nothing to undo" in again.stdout


def test_without_plasma_by_systemd_it_changes_nothing(root, plasma):
    tmp, env, calls, _ = plasma
    stub(tmp / "stub-bin", "systemctl", "exit 1")
    done = install(root, env, "--lock-screen")
    assert done.returncode != 0 and "plasma-kwin_wayland.service" in done.stderr
    for path in (SHELL, MODULE, SCENE, DROPIN):
        assert not (tmp / path).exists(), path


def test_a_shell_package_named_in_plasmashellrc_is_left_alone(root, plasma):
    """A shell named outright decides the lock screen too: syncrain's could not show, so nothing
    is written; the default spelled out is taken out, and put back by --lock-screen-off."""
    tmp, env, calls, shell = plasma
    shell.write_text("org.kde.plasma.mobileshell")
    done = install(root, env, "--lock-screen")
    assert done.returncode != 0 and "org.kde.plasma.mobileshell" in done.stderr
    assert not (tmp / DROPIN).exists() and "kwriteconfig6" not in read(calls)
    shell.write_text("org.kde.plasma.desktop")
    done = install(root, env, "--lock-screen")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "kwriteconfig6 --file plasmashellrc --group Shell --key ShellPackage --delete" in read(calls)
    assert install(root, env, "--lock-screen-off").returncode == 0
    assert "kwriteconfig6 --file plasmashellrc --group Shell --key ShellPackage org.kde.plasma.desktop" in read(calls)


def test_every_install_brings_the_lock_screen_to_its_build(root, plasma):
    tmp, env, calls, _ = plasma
    assert install(root, env, "--lock-screen").returncode == 0
    calls.write_text("")
    (tmp / SCENE).unlink()
    done = install(root, env)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "cmake --build" in read(calls) and (tmp / SCENE).exists()
    assert "the lock screen: build" in done.stdout


def test_uninstall_takes_the_lock_screen_too(root, plasma):
    tmp, env, calls, _ = plasma
    assert install(root, env, "--lock-screen").returncode == 0
    import subprocess
    gone = subprocess.run(["bash", str(root / "install.sh"), "--uninstall"], cwd=root, env=env,
                          capture_output=True, text=True, timeout=60)
    assert gone.returncode == 0, gone.stdout + gone.stderr
    for path in (SHELL, MODULE, SCENE, DROPIN):
        assert not (tmp / path).exists(), path


def test_the_wallpaper_keeps_the_lock_screen_s_scene_current(tmp_path, monkeypatch):
    """Each start of the wallpaper writes its scene for the lock screen, where one is installed."""
    from syncrain import native
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.delenv("SYNCRAIN_LOCK_SCENE", raising=False)
    path = tmp_path / "syncrain/lock-screen.scene"
    native.refresh_lock_scene(b"new")
    assert not path.exists(), "no lock screen, no scene"
    path.parent.mkdir()
    path.write_bytes(b"old")
    native.refresh_lock_scene(b"new")
    assert path.read_bytes() == b"new" and list(path.parent.iterdir()) == [path]
