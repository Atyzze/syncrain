"""install.sh, run for real into a throwaway home: what lands where, and what the launcher starts.

pacman is skipped (--no-deps) and systemctl is a stub that reports no user session, so the
installer writes its service file without enabling anything (`with_systemd` gives it one, whose
answers the test sets). The Python that runs the checks is the one running these tests, which has
the app's libraries: it is named with SYNCRAIN_PYTHON, since /usr/bin/python3 may have them too.
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
    env = {"HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "config"), "LANG": "C.UTF-8",
           "PATH": f"{bin_dir}:{os.path.dirname(sys.executable)}:/usr/bin:/bin", "SYNCRAIN_PYTHON": sys.executable}
    for key in ("DISPLAY", "GI_TYPELIB_PATH", "LD_LIBRARY_PATH", "PKG_CONFIG_PATH"):
        if key in os.environ:
            env[key] = os.environ[key]
    return tmp_path, env


#: A user systemd whose answers are files in its folder: `active`, `failed`, `enabled` (the service)
#: and `session` (graphical-session.target). Every call is written to `calls`.
SYSTEMD = """#!/bin/sh
d="$(dirname "$0")"
echo "$*" >> "$d/calls"
case "$*" in
  "--user show-environment") exit 0 ;;
  *"is-active --quiet graphical-session.target"*) [ -e "$d/session" ] ;;
  *"is-active --quiet syncrain.service"*) [ -e "$d/active" ] ;;
  *"is-failed --quiet syncrain.service"*) [ -e "$d/failed" ] ;;
  *"is-enabled --quiet syncrain.service"*) [ -e "$d/enabled" ] ;;
  *) exit 0 ;;
esac
"""


def with_systemd(tmp, *state):
    """The stub systemctl answering as a user systemd would, in the given state; its calls file."""
    stub = tmp / "stub-bin"
    (stub / "systemctl").write_text(SYSTEMD)
    for name in ("active", "failed", "enabled", "session", "calls"):
        (stub / name).unlink(missing_ok=True)
    for name in state:
        (stub / name).write_text("")
    return stub / "calls"


def restarted(calls):
    return calls.exists() and "--user restart syncrain.service" in calls.read_text()


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
    assert "preset nixos" in said.stdout, said.stdout + said.stderr
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


def unit_words(tmp):
    unit = (tmp / "config/systemd/user/syncrain.service").read_text()
    return unit, systemd_exec_words(next(line for line in unit.splitlines()
                                         if line.startswith("ExecStart="))[len("ExecStart="):])


def test_a_misspelt_option_is_refused_before_the_service_keeps_it(root, home):
    """Written into the service unchecked, it stopped the wallpaper at every login (exit 2, kept down)."""
    tmp, env = home
    done = install(root, env, "--autostart", "--preset", "matirx")
    assert done.returncode != 0 and "cannot be used" in done.stderr, done.stdout + done.stderr
    assert not (tmp / "config/systemd/user/syncrain.service").exists()


def test_the_service_is_written_again_at_every_install(root, home):
    """A fix to the service reaches an upgrade; options given later reach it; none given keeps its own."""
    tmp, env = home
    assert install(root, env, "--autostart", "--preset", "matrix").returncode == 0
    path = tmp / "config/systemd/user/syncrain.service"
    path.write_text(path.read_text().replace("StartLimitBurst=30\n", "").replace("RestartPreventExitStatus=2 69 70 78",
                                                                                 "RestartPreventExitStatus=69"))
    assert install(root, env).returncode == 0                      # an upgrade, no options
    unit, words = unit_words(tmp)
    assert "StartLimitBurst=30" in unit and "RestartPreventExitStatus=2 69 70 78" in unit
    assert not path.with_name("syncrain.service.before").exists(), "syncrain's own lines are no hand edit"
    assert words == [str(tmp / ".local/bin/syncrain"), "--preset=matrix"], "its options stay"
    done = install(root, env, "--preset", "nixos")
    assert done.returncode == 0 and "options from before go" in done.stdout, done.stdout + done.stderr
    assert unit_words(tmp)[1] == [str(tmp / ".local/bin/syncrain"), "--preset=nixos"]


def test_a_checkout_where_the_app_goes_is_never_emptied(root, home):
    """A clone kept at ~/.local/share/syncrain and run from there was emptied, uncommitted work and
    all; a folder that is not this script's install is not removed either."""
    tmp, env = home
    checkout = tmp / ".local/share/syncrain"
    shutil.copytree(root, checkout, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.png", "*.mp4"),
                    symlinks=True)
    (checkout / "mine.txt").write_text("uncommitted\n")
    done = subprocess.run(["bash", str(checkout / "install.sh"), "--no-deps"], cwd=checkout, env=env,
                          capture_output=True, text=True, timeout=120)
    assert done.returncode != 0 and "unpack the release elsewhere" in done.stderr, done.stdout + done.stderr
    assert (checkout / "mine.txt").exists() and (checkout / "install.sh").exists()
    done = install(root, env)                                         # from elsewhere: it is not an install
    assert done.returncode != 0 and "stays as it is" in done.stderr, done.stdout + done.stderr
    gone = install(root, env, "--uninstall")
    assert gone.returncode != 0 and (checkout / "mine.txt").exists()


def test_an_upgrade_swaps_the_app_in_whole_and_marks_it(root, home):
    tmp, env = home
    assert install(root, env).returncode == 0
    app = tmp / ".local/share/syncrain"
    assert (app / ".installed-by-syncrain").exists()
    assert not (tmp / ".local/share/syncrain.new").exists() and not (tmp / ".local/share/syncrain.old").exists()
    marker = app / "left-by-hand"
    marker.write_text("x")
    assert install(root, env).returncode == 0 and not marker.exists()


def test_a_native_program_from_the_source_folder_is_not_installed_when_the_build_fails(root, home, tmp_path):
    tmp, env = home
    src = tmp_path / "release"
    shutil.copytree(root, src, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.mp4"), symlinks=True)
    stale = src / "syncrain/native/syncrain-wallpaper"
    stale.write_text("#!/bin/sh\necho another build\n")
    stale.chmod(0o755)
    done = install(src, dict(env, CC=str(tmp / "no-compiler-here")))
    assert done.returncode == 0, done.stdout + done.stderr
    assert not (tmp / ".local/share/syncrain/syncrain/native/syncrain-wallpaper").exists()


def test_the_launcher_runs_the_python_the_install_checked(root, home):
    """Not whichever python3 comes first on PATH where the launcher runs (pyenv, conda, a venv)."""
    tmp, env = home
    assert install(root, env).returncode == 0
    launcher = (tmp / ".local/bin/syncrain").read_text()
    line = next(line for line in launcher.splitlines() if line.startswith("exec "))
    assert line.startswith('exec "${SYNCRAIN_PYTHON:-/'), line
    decoy = tmp / "decoy-bin"
    decoy.mkdir()
    (decoy / "python3").write_text("#!/bin/sh\necho the decoy ran\nexit 9\n")
    (decoy / "python3").chmod(0o755)
    said = subprocess.run([str(tmp / ".local/bin/syncrain"), "--config", "none", "--build"],
                          env=dict(env, PATH=f"{decoy}:{env['PATH']}"), capture_output=True, text=True, timeout=60)
    assert said.stdout.strip() == build.describe(), said.stdout + said.stderr


def test_a_prefix_is_a_whole_path_without_characters_the_service_reads(root, home):
    tmp, env = home
    done = install(root, env, "--prefix", f"{tmp}/x/../p")
    assert done.returncode == 0, done.stdout + done.stderr
    assert f'APPDIR="{tmp}/p/share/syncrain"' in (tmp / "p/bin/syncrain").read_text()
    bad = install(root, env, "--prefix", str(tmp / "a$b"))
    assert bad.returncode != 0 and "cannot carry" in bad.stderr
    moved = install(root, dict(env, PREFIX=str(tmp / "elsewhere")))
    assert moved.returncode == 0 and not (tmp / "elsewhere").exists(), "a PREFIX left by a build of something else"


def test_uninstall_after_the_ways_back_and_what_it_keeps(root, home):
    """--uninstall with --lock-screen-off: both run (the first used to end the script); the cache and
    state go, the settings stay, and only what was there is said to be removed."""
    tmp, env = home
    assert install(root, env).returncode == 0
    (tmp / ".cache/syncrain").mkdir(parents=True)
    (tmp / "config/syncrain").mkdir(parents=True)
    (tmp / "config/syncrain/config.json").write_text("{}")
    gone = install(root, env, "--lock-screen-off", "--uninstall")
    assert gone.returncode == 0, gone.stdout + gone.stderr
    assert not (tmp / ".local/share/syncrain").exists() and not (tmp / ".cache/syncrain").exists()
    assert (tmp / "config/syncrain/config.json").exists() and "kept your settings" in gone.stdout
    assert f"removed {tmp}/.local/state/syncrain" not in gone.stdout, "it was never there"


def test_a_service_another_prefix_wrote_starts_this_install(root, home):
    """Build 36 under a stray PREFIX wrote the service with that install's launcher: an upgrade keeps
    the options, never the other launcher (it would go on starting the old build)."""
    tmp, env = home
    assert install(root, env, "--autostart", "--preset", "matrix").returncode == 0
    path = tmp / "config/systemd/user/syncrain.service"
    path.write_text(path.read_text().replace(f"'{tmp}/.local/bin/syncrain'", f"'{tmp}/opt/bin/syncrain'"))
    done = install(root, env)
    assert done.returncode == 0 and "it now starts" in done.stdout, done.stdout + done.stderr
    assert unit_words(tmp)[1] == [str(tmp / ".local/bin/syncrain"), "--preset=matrix"]


def test_lines_added_to_the_service_by_hand_are_kept_beside_it(root, home):
    tmp, env = home
    assert install(root, env, "--autostart").returncode == 0
    path = tmp / "config/systemd/user/syncrain.service"
    path.write_text(path.read_text().replace("[Service]\n", "[Service]\nEnvironment=MINE=1\n"))
    done = install(root, env)
    assert done.returncode == 0 and "systemctl --user edit syncrain" in done.stdout
    assert "Environment=MINE=1" in path.with_name("syncrain.service.before").read_text()


def test_a_bad_option_or_settings_file_stops_the_install_before_anything_changes(root, home):
    tmp, env = home
    assert install(root, env, "--autostart").returncode == 0
    app = tmp / ".local/share/syncrain"
    (app / "left-by-hand").write_text("x")
    unit = (tmp / "config/systemd/user/syncrain.service").read_text()
    settings = tmp / "config/syncrain/config.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("{not json")
    done = install(root, env, "--preset", "nixos")
    assert done.returncode != 0 and "your settings file" in done.stderr, done.stdout + done.stderr
    assert (app / "left-by-hand").exists(), "the installed app stays as it was"
    assert not (tmp / ".local/share/syncrain.new").exists()
    assert (tmp / "config/systemd/user/syncrain.service").read_text() == unit


def test_an_install_from_before_the_marker_is_upgraded(root, home):
    """What build 36 left: the app with no marker beside it."""
    tmp, env = home
    assert install(root, env).returncode == 0
    (tmp / ".local/share/syncrain/.installed-by-syncrain").unlink()
    again = install(root, env)
    assert again.returncode == 0, again.stdout + again.stderr
    assert (tmp / ".local/share/syncrain/.installed-by-syncrain").exists()


def test_an_empty_folder_where_the_app_goes_is_taken(root, home):
    tmp, env = home
    (tmp / ".local/share/syncrain").mkdir(parents=True)
    done = install(root, env)
    assert done.returncode == 0, done.stdout + done.stderr


def test_an_uninstall_that_refuses_the_folder_takes_nothing_else(root, home):
    tmp, env = home
    assert install(root, env, "--autostart").returncode == 0
    app = tmp / ".local/share/syncrain"
    (app / ".installed-by-syncrain").unlink()
    (app / ".git").mkdir()
    gone = install(root, env, "--uninstall")
    assert gone.returncode != 0 and "a .git in it" in gone.stderr, gone.stdout + gone.stderr
    assert (tmp / "config/systemd/user/syncrain.service").exists() and (tmp / ".local/bin/syncrain").exists()


def test_uninstall_keeps_the_record_a_way_back_still_needs(root, home):
    """A record kept because a way back could not finish (here Plasma's shell package, when its
    config could not be written; handover.json when Plasma's shell did not answer) is what running
    it again needs."""
    tmp, env = home
    assert install(root, env).returncode == 0
    state = tmp / ".local/state/syncrain"
    state.mkdir(parents=True)
    record = state / "plasmashellrc-ShellPackage.before-syncrain"
    record.write_text("org.kde.plasma.desktop\n")
    gone = install(root, env, "--uninstall")
    assert gone.returncode == 0 and record.exists() and "kept" in gone.stdout, gone.stdout + gone.stderr
    record.unlink()
    (state / "last.json").write_text("{}")
    assert install(root, env).returncode == 0 and install(root, env, "--uninstall").returncode == 0
    assert not state.exists()


def test_a_running_service_restarts_on_the_new_build_wherever_it_runs(root, home):
    """Started by hand on a compositor without graphical-session.target, it still gets the new build."""
    tmp, env = home
    assert install(root, env, "--autostart").returncode == 0
    calls = with_systemd(tmp, "active")
    done = install(root, env)
    assert done.returncode == 0 and restarted(calls) and "restarted, on build" in done.stdout


def test_a_service_turned_off_stays_off(root, home):
    tmp, env = home
    assert install(root, env, "--autostart").returncode == 0
    calls = with_systemd(tmp, "failed", "session")
    assert install(root, env).returncode == 0 and not restarted(calls), "failed, but disabled"
    calls = with_systemd(tmp, "failed", "enabled", "session")
    assert install(root, env).returncode == 0 and restarted(calls), "failed and enabled: the cause may be mended"
    calls = with_systemd(tmp)
    done = install(root, env)
    assert done.returncode == 0 and not restarted(calls) and "enable it" not in done.stdout
