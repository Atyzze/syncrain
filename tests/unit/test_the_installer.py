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


def test_the_service_never_restarts_into_a_machine_without_opengl(root, home):
    tmp, env = home
    done = install(root, env, "--autostart", "--channel", CHANNEL, "--rainbow", "all")
    assert done.returncode == 0, done.stdout + done.stderr
    unit = (tmp / "config/systemd/user/syncrain.service").read_text()
    assert "RestartPreventExitStatus=69" in unit
    value = next(line for line in unit.splitlines() if line.startswith("ExecStart="))[len("ExecStart="):]
    assert systemd_exec_words(value) == [str(tmp / ".local/bin/syncrain"), "--channel", CHANNEL, "--rainbow", "all"]


def test_uninstall_takes_everything_it_put_there(root, home):
    tmp, env = home
    assert install(root, env, "--autostart").returncode == 0
    gone = subprocess.run(["bash", str(root / "install.sh"), "--uninstall"], cwd=root, env=env,
                          capture_output=True, text=True, timeout=60)
    assert gone.returncode == 0, gone.stdout + gone.stderr
    for path in (".local/share/syncrain", ".local/bin/syncrain", "config/systemd/user/syncrain.service"):
        assert not (tmp / path).exists(), path
