"""install.sh on four families of Linux: which family it takes a system for, what it asks each
family's package tool for, greetd's user and text login as each family names them, and what it
says on a system it does not know.

The package tools are stubs that write what they are asked to base/<tool>.calls. Each family was also
installed for real in a root of its own before the build (docs/agent/ENVIRONMENT.md).
"""
from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from syncrain import greetdconf
from tests.conftest import ROOT
from tests.support import login_install, stub

#: os-release as each family's releases write it (the words install.sh reads: ID and ID_LIKE).
OS_RELEASES = {
    "arch": 'ID=arch\n', "cachyos": 'NAME="CachyOS Linux"\nID=cachyos\nID_LIKE=arch\n',
    "endeavouros": 'ID=endeavouros\nID_LIKE=arch\n', "manjaro": 'ID=manjaro\nID_LIKE=arch\n',
    "debian": 'ID=debian\n', "ubuntu": 'ID=ubuntu\nID_LIKE=debian\n',
    "linuxmint": 'ID=linuxmint\nID_LIKE="ubuntu debian"\n', "pop": 'ID=pop\nID_LIKE="ubuntu debian"\n',
    "fedora": 'ID=fedora\n', "nobara": 'ID=nobara\nID_LIKE="rhel centos fedora"\n',
    "tumbleweed": 'ID="opensuse-tumbleweed"\nID_LIKE="opensuse suse"\n',
    "leap": 'ID="opensuse-leap"\nID_LIKE="suse opensuse"\n',
    "gentoo": 'ID=gentoo\n',
}
FAMILY = {"arch": "arch", "cachyos": "arch", "endeavouros": "arch", "manjaro": "arch", "debian": "debian",
          "ubuntu": "debian", "linuxmint": "debian", "pop": "debian", "fedora": "fedora", "nobara": "fedora",
          "tumbleweed": "suse", "leap": "suse", "gentoo": "unknown"}


def family_of(tmp_path, os_release: str) -> str:
    """detect_family, with only sed and what tmp_path/bin holds on PATH (this machine's own apt-get
    must not answer)."""
    (tmp_path / "os-release").write_text(os_release)
    (tmp_path / "bin").mkdir(exist_ok=True)
    if not (tmp_path / "bin/sed").exists():
        (tmp_path / "bin/sed").symlink_to(shutil.which("sed"))
    script = f'set -eu; eval "$(sed -n "/^OS_RELEASE=/,/^}}/p" {ROOT}/install.sh)"; detect_family'
    done = subprocess.run(["/bin/bash", "-c", script], env={"PATH": str(tmp_path / "bin"),
                                                            "SYNCRAIN_OS_RELEASE": str(tmp_path / "os-release")},
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


@pytest.mark.parametrize("name", sorted(OS_RELEASES))
def test_each_system_is_taken_for_its_family(tmp_path, name):
    assert family_of(tmp_path, OS_RELEASES[name]) == FAMILY[name]


@pytest.mark.parametrize("tool, family", [("pacman", "arch"), ("apt-get", "debian"), ("dnf", "fedora"),
                                          ("zypper", "suse")])
def test_without_os_release_the_package_tool_says_the_family(tmp_path, tool, family):
    stub(tmp_path / "bin", tool, "exit 0")
    assert family_of(tmp_path, "") == family


#: For each family: its tool, the stub that says nothing is installed yet, how --yes reaches the
#: tool, and a package of each kind it must ask for.
TOOLS = {
    "arch": ("pacman", {"pacman": 'case "$1" in -Q*) exit 1 ;; esac'},
             ["-S", "--needed", "--noconfirm"], ["python-gobject", "gtk4", "gcc", "gtk4-layer-shell"]),
    "debian": ("apt-get", {"dpkg-query": "exit 1"}, ["install", "-y"],
               ["python3-gi", "python3-gi-cairo", "gir1.2-gtk-4.0", "libwayland-dev", "libgtk4-layer-shell0",
                "gir1.2-gtk4layershell-1.0"]),
    "fedora": ("dnf", {"rpm": "exit 1"}, ["install", "-y"],
               ["python3-gobject", "gtk4", "wayland-devel", "gtk4-layer-shell"]),
    "suse": ("zypper", {"rpm": "exit 1"}, ["--non-interactive", "install"],
             ["python3-gobject", "typelib-1_0-Gtk-4_0", "dbus-1-devel", "typelib-1_0-Gtk4LayerShell-1_0"]),
}


def package_stubs(tmp_path, family, refuse=""):
    """The family's tools as stubs: nothing installed, each install written down; one whose words
    include `refuse` fails, as a tool does for a package its release lacks."""
    tool, checks, _, _ = TOOLS[family]
    for name, body in checks.items():
        if name != tool:
            stub(tmp_path / "bin", name, body)
    check = checks.get(tool, "")
    stub(tmp_path / "bin", tool, f'{check}\necho "$@" >> {tmp_path}/{tool}.calls\n'
                                 + (f'case "$*" in *{refuse}*) echo "no such package" >&2; exit 100 ;; esac\n'
                                    if refuse else "") + "exit 0")
    return tool


@pytest.mark.parametrize("family", sorted(TOOLS))
def test_each_family_s_tool_is_asked_for_its_packages(tmp_path, family):
    tool = package_stubs(tmp_path, family)
    done = login_install(tmp_path, "--yes", deps=True, env_extra={"SYNCRAIN_FAMILY": family})
    assert done.returncode == 0, done.stdout + done.stderr
    calls = (tmp_path / f"{tool}.calls").read_text().splitlines()
    _, _, yes, wanted = TOOLS[family]
    assert all(" ".join(yes) in call for call in calls), calls
    asked = " ".join(calls).split()
    assert all(p in asked for p in wanted), (wanted, calls)
    assert f"Installing packages ({tool.replace('-get', '')})" in done.stdout
    if os.getuid() != 0:                                                        # as root, through sudo
        assert tool in (tmp_path / "sudo.calls").read_text()


@pytest.mark.parametrize("family", sorted(TOOLS))
def test_without_gtk4_layer_shell_the_install_goes_on(tmp_path, family):
    """Ubuntu 24.04 and openSUSE Leap 16.0 have no gtk4-layer-shell: the native wallpaper draws."""
    layer = TOOLS[family][3][-1]
    package_stubs(tmp_path, family, refuse=layer)
    done = login_install(tmp_path, "--yes", deps=True, env_extra={"SYNCRAIN_FAMILY": family})
    assert done.returncode == 0, done.stdout + done.stderr
    assert "gtk4-layer-shell is not available here" in done.stdout and "the native wallpaper draws" in done.stdout


@pytest.mark.parametrize("family", sorted(TOOLS))
def test_a_tool_that_cannot_install_says_what_to_try(tmp_path, family):
    tool = package_stubs(tmp_path, family, refuse=TOOLS[family][3][0])     # the PyGObject package
    done = login_install(tmp_path, "--yes", deps=True, env_extra={"SYNCRAIN_FAMILY": family})
    assert done.returncode == 1
    assert "could not install the packages" in done.stderr and tool.replace("-get", "") in done.stderr
    assert "update" in done.stderr or "refresh" in done.stderr or "-Syu" in done.stderr


def test_a_system_of_no_known_family_is_told_what_to_install_and_who_can_help(tmp_path):
    done = login_install(tmp_path, deps=True, env_extra={"SYNCRAIN_FAMILY": "unknown"})
    assert done.returncode == 1
    for words in ("none of the four families", "--no-deps", "PyGObject", "gtk4-layer-shell", "AI agent"):
        assert words in done.stderr, words


def test_the_lock_screen_s_packages_include_a_c_plus_plus_compiler_and_make():
    """Debian's and openSUSE's Qt packages bring none (found by building it in their roots)."""
    script = f'eval "$(sed -n "/^set_packages() {{/,/^}}/p" {ROOT}/install.sh)"; ' \
             'for f in arch debian fedora suse; do set_packages $f; echo "$f ${LOCK_PACKAGES[*]}"; done'
    said = dict(line.split(" ", 1) for line in subprocess.run(["bash", "-c", script], capture_output=True,
                                                               text=True).stdout.splitlines())
    assert "g++" in said["debian"] and "gcc-c++" in said["fedora"] and "gcc-c++" in said["suse"]
    assert all("cmake" in v and " make " in v for v in said.values())    # a minimal Arch has no make


@pytest.mark.parametrize("config, users, expected", [
    ('[default_session]\ncommand = "agreety --cmd /bin/sh"\nuser = "_greetd"\n', ["_greetd"], "_greetd"),  # Debian
    ('[default_session]\ncommand = "agreety --cmd /bin/sh"\nuser = "greetd"\n', ["greetd"], "greetd"),     # Fedora
    ('[default_session]\ncommand = "sway"\nuser = "greeter"\n', ["greeter"], "greeter"),                # Arch, openSUSE
    ('[default_session]\ncommand = "x"\nuser = "nobody-here"\n', ["_greetd"], "_greetd"),
    ('[terminal]\nvt = 1\n', ["greetd"], "greetd"),
])
def test_greetd_s_user_is_the_one_its_family_named(tmp_path, config, users, expected):
    (tmp_path / "config.toml").write_text(config)
    stub(tmp_path / "bin", "getent", 'case " ' + " ".join(users) + ' " in *" $2 "*) echo "$2:x:1:1::/:/bin/false" ;; '
                                     '*) exit 2 ;; esac')
    script = (f'SRC={ROOT} APPDIR=/nonexistent GREETD_CONFIG={tmp_path}/config.toml; as_root() {{ "$@"; }}; '
              f'eval "$(sed -n "/^read_system_file()/p; /^greetdconf() {{/,/^}}/p; /^greeter_user() {{/,/^}}/p" '
              f'{ROOT}/install.sh)"; greeter_user')
    done = subprocess.run(["bash", "-c", script], env={"PATH": f"{tmp_path}/bin:/usr/bin:/bin",
                                                       "PYTHONDONTWRITEBYTECODE": "1"},
                          capture_output=True, text=True)
    assert done.stdout.strip() == expected, done.stderr


def test_greetdconf_reads_the_user():
    assert greetdconf.user('[default_session]\nuser = "_greetd"\n') == "_greetd"
    assert greetdconf.user('[general]\nuser = "x"\n') is None


def test_greetd_s_text_login_on_path_counts_only_if_it_is_root_s_and_outside_the_home(tmp_path):
    """greetd runs it as its own user, reading passwords: /usr/bin and /usr/sbin (Debian's) first;
    one on PATH only if root's, not in this user's home and safe inside greetd's sh -c '...'."""
    if os.path.exists("/usr/bin/agreety") or os.path.exists("/usr/sbin/agreety"):
        # not a missing environment: on such a machine the case does not arise, so even the release
        # run skips it
        pytest.skip("this machine has its own agreety, which comes first")
    script = f'eval "$(sed -n "/^agreety_path() {{/,/^}}/p" {ROOT}/install.sh)"; agreety_path'

    def found(folder, home="/nonexistent-home"):
        stub(folder, "agreety", "exit 0")
        return subprocess.run(["bash", "-c", script], env={"PATH": f"{folder}:/usr/bin:/bin", "HOME": home},
                              capture_output=True, text=True).stdout.strip()
    elsewhere = tmp_path / "opt"
    assert found(elsewhere) == (f"{elsewhere}/agreety" if os.getuid() == 0 else "")
    assert found(tmp_path / "home/.local/bin", home=str(tmp_path / "home")) == ""
    assert found(tmp_path / "a folder") == ""
    text = (ROOT / "install.sh").read_text()
    assert text.index("/usr/bin/agreety /usr/sbin/agreety") < text.index('command -v agreety')


def test_what_starts_at_boot_is_seen_before_greetd_is_installed(tmp_path):
    """Debian's greetd package makes itself what starts at boot where nothing did (with a display
    manager set it leaves the link alone): what was there is seen first, and recorded."""
    package_stubs(tmp_path, "debian")
    link = tmp_path / "display-manager.service"
    link.symlink_to("/usr/lib/systemd/system/sddm.service")
    # apt-get installing greetd moves the link, as Debian's package does
    stub(tmp_path / "bin", "apt-get", f'echo "$@" >> {tmp_path}/apt-get.calls\n'
                                      f'case "$*" in *greetd*) ln -sfn /usr/lib/systemd/system/greetd.service {link} ;; esac\n'
                                      'exit 0')
    (tmp_path / "etc/pam.d").mkdir(parents=True)
    (tmp_path / "etc/pam.d/greetd").write_text("#%PAM-1.0\nauth include common-auth\n")
    done = login_install(tmp_path, "--yes", "--login-screen", deps=True, env_extra={"SYNCRAIN_FAMILY": "debian"})
    assert done.returncode == 0, done.stdout + done.stderr
    assert "greetd" in (tmp_path / "apt-get.calls").read_text()
    assert (tmp_path / "etc/greetd/display-manager.before-syncrain").read_text().strip() == "sddm.service"


def test_a_login_screen_whose_greetd_cannot_be_installed_leaves_no_record(tmp_path):
    """A refused or failed install (a 404, a 'no' at the prompt) changes nothing about the way back."""
    package_stubs(tmp_path, "debian", refuse="greetd")
    (tmp_path / "display-manager.service").symlink_to("/usr/lib/systemd/system/sddm.service")
    done = login_install(tmp_path, "--yes", "--login-screen", deps=True, env_extra={"SYNCRAIN_FAMILY": "debian"})
    assert done.returncode == 1 and "could not install greetd" in done.stderr
    assert not (tmp_path / "etc/greetd/display-manager.before-syncrain").exists()


def test_a_tool_that_fails_after_installing_everything_is_not_a_failure(tmp_path):
    """zypper's 107: a package's script failed, the packages are in. What counts is what is missing."""
    stub(tmp_path / "bin", "rpm", f'[ -f {tmp_path}/installed ]')
    stub(tmp_path / "bin", "zypper", f'echo "$@" >> {tmp_path}/zypper.calls; touch {tmp_path}/installed; exit 107')
    done = login_install(tmp_path, "--yes", deps=True, env_extra={"SYNCRAIN_FAMILY": "suse"})
    assert done.returncode == 0, done.stdout + done.stderr


def test_greetd_s_own_user_goes_into_its_config(tmp_path):
    """Without the tests' fixed user: Debian's _greetd, from greetd's packaged config."""
    (tmp_path / "etc/greetd").mkdir(parents=True)
    (tmp_path / "etc/greetd/config.toml").write_text(
        '[terminal]\nvt = 7\n\n[default_session]\ncommand = "/usr/sbin/agreety --cmd /bin/sh"\nuser = "_greetd"\n')
    (tmp_path / "etc/pam.d").mkdir(parents=True)
    (tmp_path / "etc/pam.d/greetd").write_text("#%PAM-1.0\nauth include common-auth\n")
    stub(tmp_path / "bin", "getent", 'case "$2" in _greetd) echo "_greetd:x:101:101::/var/lib/greetd:/bin/false" ;; '
                                     '*) exit 2 ;; esac')
    done = login_install(tmp_path, "--login-screen", env_extra={"SYNCRAIN_GREETER_USER": ""})
    assert done.returncode == 0, done.stdout + done.stderr
    config = (tmp_path / "etc/greetd/config.toml").read_text()
    assert 'user = "_greetd"' in config and "login.sh" in config
