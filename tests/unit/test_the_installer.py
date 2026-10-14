"""install.sh, run for real into a throwaway home: what lands where, and what the launcher starts.

pacman is skipped (--no-deps) and systemctl is a stub that reports no user session, so the
installer writes its service file without enabling anything. The Python that runs the checks is
the one running these tests, which has the app's libraries.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest

from syncrain import build
from syncrain.app import NO_RESTART
from tests.conftest import native_build_tools, need
from tests.support import systemd_exec_words

#: A channel name with everything systemd would otherwise expand or unescape.
CHANNEL = "it's 100% $HOME \\ \"quoted\" %h"


@pytest.fixture
def home(tmp_path):
    bin_dir = tmp_path / "stub-bin"
    bin_dir.mkdir()
    (bin_dir / "systemctl").write_text("#!/bin/sh\nexit 1\n")
    (bin_dir / "systemctl").chmod(0o755)
    # the directory of the interpreter running the tests comes first, so its `python3` is the one used
    env = {"HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "config"), "LANG": "C.UTF-8",
           "PATH": f"{bin_dir}:{os.path.dirname(sys.executable)}:/usr/bin:/bin"}
    for key in ("DISPLAY", "GI_TYPELIB_PATH", "LD_LIBRARY_PATH", "PKG_CONFIG_PATH"):
        if key in os.environ:
            env[key] = os.environ[key]
    return tmp_path, env


def install(root, env, *args):
    return subprocess.run(["bash", str(root / "install.sh"), "--no-deps", *args], cwd=root, env=env,
                          capture_output=True, text=True, timeout=120)


def test_the_installer_passes_shellcheck(root):
    need(shutil.which("shellcheck") is not None, "no shellcheck")
    result = subprocess.run(["shellcheck", str(root / "install.sh")], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


def test_it_installs_this_build_and_the_launcher_says_so(root, home):
    tmp, env = home
    done = install(root, env)
    assert done.returncode == 0, done.stdout + done.stderr
    assert f"Installing syncrain build {build.BUILD_NUMBER}" in done.stdout
    app_dir, launcher = tmp / ".local/share/syncrain", tmp / ".local/bin/syncrain"
    assert (app_dir / "BUILD_NUMBER").read_text().strip() == str(build.BUILD_NUMBER)
    said = subprocess.run([str(launcher), "--build"], env=env, capture_output=True, text=True, timeout=60)
    assert said.stdout.strip() == build.describe()


def test_the_native_wallpaper_is_built_where_syncrain_looks_for_it(root, home):
    missing = native_build_tools()
    need(missing is None, f"the native wallpaper cannot be built here: {missing}")
    tmp, env = home
    done = install(root, env)
    assert done.returncode == 0 and "native wallpaper: built" in done.stdout, done.stdout + done.stderr
    program = tmp / ".local/share/syncrain/syncrain/native/syncrain-wallpaper"
    assert program.is_file() and os.access(program, os.X_OK)
    found = subprocess.run([sys.executable, "-c", "from syncrain import native; print(native.binary())"],
                           env=dict(env, PYTHONPATH=str(tmp / ".local/share/syncrain"), PYTHONSAFEPATH="1"),
                           capture_output=True, text=True, timeout=60)
    assert found.stdout.strip() == str(program), found.stdout + found.stderr


def test_without_a_compiler_the_gtk_host_draws_and_the_install_goes_on(root, home):
    tmp, env = home
    done = install(root, dict(env, CC=str(tmp / "no-compiler-here")))
    assert done.returncode == 0, done.stdout + done.stderr
    assert "the native wallpaper did not build, so the Python and GTK host draws instead" in done.stdout
    assert not (tmp / ".local/share/syncrain/syncrain/native/syncrain-wallpaper").exists()


def test_the_launcher_ignores_a_syncrain_folder_in_the_current_directory(root, home):
    """Build 2 started the unpacked copy when run from inside the release folder (python -m puts the
    current directory first). Harmless that day, wrong the day the two differ."""
    tmp, env = home
    assert install(root, env).returncode == 0
    decoy = tmp / "unpacked" / "syncrain"
    decoy.mkdir(parents=True)
    (decoy / "__init__.py").write_text("")
    (decoy / "__main__.py").write_text("print('the decoy ran')\n")
    said = subprocess.run([str(tmp / ".local/bin/syncrain"), "--build"], cwd=decoy.parent, env=env,
                          capture_output=True, text=True, timeout=60)
    assert said.stdout.strip() == build.describe(), said.stdout + said.stderr


def test_an_older_install_is_upgraded_and_named(root, home):
    tmp, env = home
    assert install(root, env).returncode == 0
    (tmp / ".local/share/syncrain/BUILD_NUMBER").write_text(f"{build.BUILD_NUMBER - 1}\n")
    again = install(root, env)
    assert f"Upgrading syncrain from build {build.BUILD_NUMBER - 1} to build {build.BUILD_NUMBER}" in again.stdout


def test_the_service_never_restarts_into_a_failure_a_restart_cannot_change(root, home):
    """No OpenGL, no wallpaper layer (GNOME), an unknown option, a native wallpaper from another
    build: each would otherwise start again every 3 s, for good."""
    tmp, env = home
    done = install(root, env, "--autostart", "--channel", CHANNEL, "--rainbow", "all")
    assert done.returncode == 0, done.stdout + done.stderr
    unit = (tmp / "config/systemd/user/syncrain.service").read_text()
    prevent = next(line for line in unit.splitlines() if line.startswith("RestartPreventExitStatus="))
    assert prevent.split("=", 1)[1].split() == [str(status) for status in NO_RESTART]
    value = next(line for line in unit.splitlines() if line.startswith("ExecStart="))[len("ExecStart="):]
    assert systemd_exec_words(value) == [str(tmp / ".local/bin/syncrain"), f"--channel={CHANNEL}", "--rainbow=all"]


def test_an_unknown_option_ends_with_a_status_the_service_does_not_restart_on(root):
    done = subprocess.run([sys.executable, "-m", "syncrain", "--no-such-option"], cwd=root, capture_output=True,
                          text=True, timeout=60, env=dict(os.environ, PYTHONPATH=str(root), PYTHONSAFEPATH="1"))
    assert done.returncode in NO_RESTART and "--no-such-option" in done.stderr, done.stderr


def test_uninstall_takes_everything_it_put_there(root, home):
    tmp, env = home
    assert install(root, env, "--autostart").returncode == 0
    gone = subprocess.run(["bash", str(root / "install.sh"), "--uninstall"], cwd=root, env=env,
                          capture_output=True, text=True, timeout=60)
    assert gone.returncode == 0, gone.stdout + gone.stderr
    for path in (".local/share/syncrain", ".local/bin/syncrain", "config/systemd/user/syncrain.service"):
        assert not (tmp / path).exists(), path


def test_build_13_and_14_s_plasma_wallpaper_is_taken_away_again(root, home):
    """It was dropped in build 15: an install or an uninstall removes it and gives Plasma its image
    wallpaper back (Plasma's scripting and kscreenlockerrc are stubs here)."""
    tmp, env = home
    stubs, calls, qml = tmp / "stub-bin", tmp / "calls.log", tmp / "qt-qml"
    for name, body in {"qtpaths6": f'echo "{qml}"', "sudo": '"$@"', "dbus-send": f'echo "dbus-send $*" >> "{calls}"',
                       "kreadconfig6": "echo org.syncrain.wallpaper",
                       "kwriteconfig6": f'echo "kwriteconfig6 $*" >> "{calls}"'}.items():
        (stubs / name).write_text(f"#!/bin/sh\n{body}\n")
        (stubs / name).chmod(0o755)
    package = tmp / ".local/share/plasma/wallpapers/org.syncrain.wallpaper"
    for d in (package, qml / "org/syncrain"):
        d.mkdir(parents=True)
    done = install(root, env)
    assert done.returncode == 0, done.stdout + done.stderr
    assert not package.exists() and not (qml / "org/syncrain").exists()
    said = calls.read_text()
    assert "d.wallpaperPlugin = 'org.kde.image'" in said and "WallpaperPlugin --delete" in said, said


def test_a_settings_file_from_the_page_is_kept_where_the_wallpaper_reads_it(root, home):
    """./install.sh --config: checked, kept as ~/.config/syncrain/config.json, and the service written
    again without the options an earlier install gave it, which would go over the file."""
    import json
    tmp, env = home
    assert install(root, env, "--autostart", "--theme", "matrix").returncode == 0
    page = tmp / "config.json"
    page.write_text(json.dumps({"contract": "syncrain-config-1", "theme": "nixos", "speed": 1.5}))
    done = install(root, env, "--config", str(page))
    assert done.returncode == 0, done.stdout + done.stderr
    assert (tmp / "config/syncrain/config.json").read_text() == page.read_text()
    unit = (tmp / "config/systemd/user/syncrain.service").read_text()
    value = next(line for line in unit.splitlines() if line.startswith("ExecStart="))[len("ExecStart="):]
    assert systemd_exec_words(value) == [str(tmp / ".local/bin/syncrain")]
    said = subprocess.run([str(tmp / ".local/bin/syncrain"), "--check-config"], env=env, capture_output=True,
                          text=True, timeout=60)
    assert "theme nixos" in said.stdout, said.stdout + said.stderr
    again = install(root, env, "--config", str(tmp / "config/syncrain/config.json"))
    assert again.returncode == 0, "the kept file given again: " + again.stdout + again.stderr
    page.write_text(json.dumps({"contract": "syncrain-config-1", "speed": "fast"}))
    bad = install(root, env, "--config", str(page))
    assert bad.returncode != 0 and "cannot be used" in bad.stderr
    assert '"speed": 1.5' in (tmp / "config/syncrain/config.json").read_text(), "the file before stays"
    (tmp / "config/syncrain/config.json").write_text('{"contract": "syncrain-config-1", "speeed": 1}')
    page.write_text(json.dumps({"contract": "syncrain-config-1", "theme": "matrix"}))
    mended = install(root, env, "--config", str(page))
    assert mended.returncode == 0, "a broken file is put right: " + mended.stdout + mended.stderr
