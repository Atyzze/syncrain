"""The Nix package and the NixOS and home-manager services, evaluated and built from this tree.

Needs nix-instantiate and nix-build, and local checkouts named by SYNCRAIN_NIXPKGS (nixpkgs) and
SYNCRAIN_HOME_MANAGER (home-manager), so nothing is fetched at evaluation time
(`docs/agent/ENVIRONMENT.md`). The build itself downloads its dependencies from the binary cache.
The package's native wallpaper is run in a headless Sway (sway and grim), with the OpenGL driver
where programs from Nix look for one (/run/opengl-driver).
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time

import pytest

from syncrain import build
from syncrain.app import NO_RESTART
from tests.conftest import need
from tests.support import MOMENT, grab, headless_sway, mean_abs_diff, said_when_stopped, systemd_exec_words

CHANNEL = "it's 100% $HOME \\ \"quoted\" %h"


@pytest.fixture(scope="module")
def checkouts():
    need(shutil.which("nix-instantiate") is not None and shutil.which("nix-build") is not None, "no Nix")
    nixpkgs, hm = os.environ.get("SYNCRAIN_NIXPKGS"), os.environ.get("SYNCRAIN_HOME_MANAGER")
    need(bool(nixpkgs) and os.path.isdir(nixpkgs or ""), "SYNCRAIN_NIXPKGS does not name a nixpkgs checkout")
    need(bool(hm) and os.path.isdir(hm or ""), "SYNCRAIN_HOME_MANAGER does not name a home-manager checkout")
    return nixpkgs, hm


@pytest.fixture(scope="module")
def evaluated(root, checkouts):
    nixpkgs, hm = checkouts
    done = subprocess.run(["nix-instantiate", "--eval", "--strict", "--json", str(root / "tests/nix/services.nix"),
                           "--arg", "src", str(root), "--arg", "nixpkgs", nixpkgs, "--arg", "homeManager", hm,
                           "--argstr", "channel", CHANNEL], capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-3000:]
    return json.loads(done.stdout)


def test_the_package_is_named_for_the_build(evaluated):
    assert evaluated["version"] == str(build.BUILD_NUMBER)
    assert evaluated["web"] == f"syncrain-web-{build.BUILD_NUMBER}"


@pytest.mark.parametrize("which", ["nixos", "hm"])
def test_the_services_pass_the_channel_through_systemd_intact(evaluated, which):
    service = evaluated[which]
    exec_start = service["exec"] if isinstance(service["exec"], str) else " ".join(service["exec"])
    words = systemd_exec_words(exec_start)
    assert words[0].endswith("/bin/syncrain")
    assert words[words.index("--channel") + 1] == CHANNEL, words
    assert str(service["prevent"]).split() == [str(status) for status in NO_RESTART]
    if which == "nixos":                      # set there; the home-manager service keeps the defaults
        assert words[words.index("--pause-under") + 1] == "fullscreen", words
        assert words[words.index("--lock-rest") + 1] == "300", words
        assert [words[words.index(o) + 1] for o in ("--speed", "--glow", "--snow", "--hieroglyphs", "--flavours",
                                                    "--flavour-layout", "--cycle", "--rain-colors")] == \
            ["0.500000", "0.000000", "off", "0.300000", "9", "wave", "30", "#202040,#8040c0,#e0c0ff,#ffffff"], words
        assert "--words=HI,THERE" in words, words
        assert "--preset" not in words and "--fps" not in words, "left to a settings file, else the preset"
    else:
        for o in ("--pause-under", "--lock-rest", "--speed", "--glow", "--snow", "--hieroglyphs"):
            assert o not in words, words
        assert words[words.index("--preset") + 1] == "matrix", words


@pytest.fixture(scope="module")
def built(root, checkouts, tmp_path_factory):
    nixpkgs, _ = checkouts
    out = tmp_path_factory.mktemp("nix") / "result"
    done = subprocess.run(["nix-build", str(root / "tests/nix/package.nix"), "--arg", "src", str(root),
                           "--arg", "nixpkgs", nixpkgs, "-o", str(out)], capture_output=True, text=True, timeout=1800)
    assert done.returncode == 0, done.stderr[-3000:]
    return out


def outside_env(**extra):
    """The environment without what points this tree's Python at its libraries, so the package
    finds its own."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONPATH", "GI_TYPELIB_PATH", "LD_LIBRARY_PATH", "SYNCRAIN_WALLPAPER", "LD_PRELOAD")}
    env.update(extra)
    return env


def test_the_built_package_says_its_build_and_draws_the_same_frame(built, tmp_path, app, x_display):
    out = built
    said = subprocess.run([str(out / "bin/syncrain"), "--build"], capture_output=True, text=True, timeout=60)
    assert said.stdout.strip() == build.describe(), said.stdout + said.stderr
    nix_shot, tree_shot = tmp_path / "nix.png", tmp_path / "tree.png"
    env = outside_env(DISPLAY=x_display, GDK_BACKEND="x11")
    drew = subprocess.run([str(out / "bin/syncrain"), "--window", "--size", "960x540", "--time", str(MOMENT),
                           "--screenshot", str(nix_shot)], env=env, capture_output=True, text=True, timeout=300)
    assert drew.returncode == 0, drew.stderr[-2000:]
    assert app(["--window", "--size", "960x540", "--time", str(MOMENT), "--screenshot", str(tree_shot)]).returncode == 0
    assert mean_abs_diff(nix_shot, tree_shot) < 1.0


def test_the_built_package_draws_the_wallpaper_natively_on_wayland(root, built, tmp_path, native_wallpaper):
    """The package's own native wallpaper (libexec/syncrain, named by its wrapper) opens EGL through
    libglvnd and draws what the tree's draws."""
    need(shutil.which("sway") is not None and shutil.which("grim") is not None, "no sway and grim for a Wayland session")
    assert (built / "libexec/syncrain/syncrain-wallpaper").is_file()
    shots = {}
    with headless_sway(tmp_path / "run") as session:
        for name, argv, env in (
                ("nix", [str(built / "bin/syncrain")], outside_env(**session)),
                ("tree", [sys.executable, "-m", "syncrain"], dict(os.environ, **session, PYTHONPATH=str(root)))):
            env.pop("DISPLAY", None)
            env.update(XDG_CURRENT_DESKTOP="sway", GDK_BACKEND="wayland")
            proc = subprocess.Popen([*argv, "--time", str(MOMENT)], cwd=root, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                line = proc.stdout.readline()
                assert ", native wallpaper, " in line, line + said_when_stopped(proc)
                time.sleep(2.0)
                shots[name] = tmp_path / f"{name}.png"
                grab(session, shots[name])
            finally:
                proc.send_signal(signal.SIGTERM)
                proc.communicate(timeout=30)
            assert proc.returncode == 0, name
    assert mean_abs_diff(shots["nix"], shots["tree"]) < 1.0


def test_the_package_finds_fc_list_without_a_path_of_its_own(built):
    """A service starts with almost no PATH; symbols that are not shipped come from the machine's
    fonts through fc-list, so the wrapper brings fontconfig's."""
    import re
    wrapper = (built / "bin" / "syncrain").read_text(errors="replace")
    found = re.findall(r"(/nix/store/[^:'\"\s\x00]*fontconfig[^:'\"\s\x00/]*/bin)", wrapper)
    assert found and any(os.access(os.path.join(d, "fc-list"), os.X_OK) for d in found), wrapper[-2000:]


@pytest.fixture(scope="module")
def nixos_login(root, checkouts, tmp_path_factory):
    """The NixOS module's login screen folder and the package it runs (tests/nix/login.nix)."""
    nixpkgs, _ = checkouts
    out = tmp_path_factory.mktemp("nixlogin") / "result"
    done = subprocess.run(["nix-build", str(root / "tests/nix/login.nix"), "--arg", "src", str(root),
                           "--arg", "nixpkgs", nixpkgs, "-o", str(out)], capture_output=True, text=True, timeout=1800)
    assert done.returncode == 0, done.stderr[-3000:]
    return out


def test_the_nixos_login_screen_logs_in_through_the_box(nixos_login, tmp_path):
    """The module's folder, as greetd would run it: login.sh with the package's Python (the app,
    GTK, gtk4-layer-shell and the native wallpaper, nothing of this tree's), in a headless KWin with
    two screens; the rain draws, a box on each, a wrong and then the right password, Plasma asked for."""
    from tests.kwin.test_a_login_in_kwin import PLASMA, run_login
    folder = nixos_login / "folder"
    assert json.loads((folder / "login.json").read_text()) == {
        "user": "op", "session": "plasma.desktop", "rain": ["--preset", "matrix", "--fps", "10", "--scale", "1.000000"]}
    log, greetd = run_login(tmp_path, [{"password": "wrong", "wait": 4}, {"password": "right"}],
                            folder=folder, python=nixos_login / "package/libexec/syncrain/python3")
    assert "native wallpaper, 2 screens" in log, f"the rain never drew:\n{log[-4000:]}"
    shown = [line for line in log.splitlines() if " box shown on " in line]
    assert len({line.split()[-1] for line in shown}) == 2, log[-4000:]
    assert [s["cmd"] for s in greetd.started()] == [[PLASMA]], log[-4000:]
    assert f"build {build.BUILD_NUMBER}" in log.splitlines()[0]


def test_the_nixos_module_sets_up_the_login_and_lock_screens(evaluated):
    """Evaluated on a Plasma 6 system (tests/nix/services.nix): greetd runs the folder's login.sh
    as greeter, with Plasma's KWin, the package's Python and greetd's text login; the lock screen's
    drop-in names syncrain's shell package to KWin alone; the wallpaper writes the lock scene first."""
    s = evaluated["screens"]
    assert s["failed"] == [] and s["greetd"] and s["greeter"] == "greeter"
    words = s["command"].replace("'", "").split()
    assert words[0].endswith("/bin/env") and words[-1].endswith("-syncrain-login-31/syncrain/login/login.sh".replace(
        "31", str(build.BUILD_NUMBER)))
    env = dict(w.split("=", 1) for w in words[1:-1])
    assert env["PATH"].startswith("/run/wrappers/bin:") and "-kwin-" in env["PATH"]
    assert env["SYNCRAIN_PYTHON"].endswith("/libexec/syncrain/python3")
    assert env["SYNCRAIN_LOGIN_TEXT"].endswith("/bin/agreety") and "-desktops/share:" in env["XDG_DATA_DIRS"]
    assert "d /var/lib/syncrain-login 0700 greeter greeter -" in s["tmpfiles"]
    path = env["PATH"].split(":")
    assert any(os.access(os.path.join(d, "systemctl"), os.X_OK) for d in path), "the box's power buttons"
    assert path[-1] == "/run/current-system/sw/bin" and env["XDG_DATA_DIRS"].endswith(":/run/current-system/sw/share")
    assert s["session"] == "plasma" and any("no session of this system" in m for m in s["badSession"])
    assert s["kwinDropin"].splitlines()[0] == "[Service]" and "\"PATH=" not in s["kwinDropin"]
    assert 'Environment="PLASMA_DEFAULT_SHELL=org.syncrain.lockscreen"' in s["kwinDropin"]
    assert "-syncrain-lockscreen-" in s["kwinDropin"] and s["shells"]
    assert s["pre"].startswith("-/nix/store/") and "--write-scene %h/.local/state/syncrain/lock-screen.scene" in s["pre"]
    assert s["pre"].split("lock-screen.scene", 1)[1].strip() == s["exec"].split("/bin/syncrain", 1)[1].strip()
    assert evaluated["nixos"]["pre"] is None, "no lock screen asked for, no scene written"
    assert any("sddm.enable = false" in m for m in s["sddm"])
    assert any("services.xserver.displayManager.lightdm.enable = false" in m for m in s["lightdm"])
    assert any("services.syncrain.enable = true" in m for m in s["noWallpaper"])


def test_the_flake_template_is_a_whole_backdrop_system(root, checkouts):
    """`nix flake init -t github:Atyzze/syncrain`: the template's configuration with
    syncrain.nixosModules.backdrop and the machine's own configuration (machine.nix) evaluates to a
    NixOS system (tests/nix/template.nix, stand-ins for the machine): Plasma 6, the rain's login and
    lock screens, no SDDM, no Plymouth; the machine's boot loader, keyboard, users and release as
    they were (the template once replaced the whole configuration.nix)."""
    nixpkgs, _ = checkouts
    done = subprocess.run(["nix-instantiate", "--eval", "--strict", "--json", str(root / "tests/nix/template.nix"),
                           "--arg", "src", str(root), "--arg", "nixpkgs", nixpkgs],
                          capture_output=True, text=True, timeout=900)
    assert done.returncode == 0, done.stderr[-3000:]
    t = json.loads(done.stdout)
    assert t["failed"] == [] and "-nixos-system-backdrop-" in t["toplevel"], t
    assert (t["plasma"], t["sddm"], t["greetd"], t["login"], t["lock"], t["plymouth"]) == \
        (True, False, True, True, True, False)
    assert t["loginUser"] == "" and "PLASMA_DEFAULT_SHELL=org.syncrain.lockscreen" in t["kwinDropin"]
    assert (t["keyboard"], t["grub"], t["systemdBoot"], t["stateVersion"], t["alice"], t["swap"]) == \
        ("de", True, False, "24.11", True, True), "the machine's own, as it was, with what it imports"
    assert t["lightdm"] is False and t["git"], "the installer's other login screen off; git for the flake"
    flake = (root / "flake.nix").read_text()
    assert "templates.default" in flake and "path = ./nix/template;" in flake
    assert 'key = "syncrain"' in flake and "nixosModules.backdrop" in flake
    template = root / "nix/template"
    assert sorted(p.name for p in template.iterdir()) == ["README.md", "configuration.nix", "flake.nix"]
    assert "syncrain.nixosModules.backdrop" in (template / "flake.nix").read_text()
    assert 'inputs.nixpkgs.follows = "nixpkgs"' in (template / "flake.nix").read_text()
    configuration = (template / "configuration.nix").read_text()
    assert "CHANGE" in configuration and "./machine/configuration.nix" in (template / "flake.nix").read_text()
    for theirs in ("boot.loader", "users.users", "stateVersion", "xkb", "initialPassword"):
        assert theirs not in configuration, f"{theirs}: the machine's, in machine/"
    # what `nix flake init` prints first and the README both say to copy the machine's folder whole
    assert "cp -r /etc/nixos machine" in (template / "README.md").read_text()
    assert "cp -r /etc/nixos machine" in flake.split("welcomeText", 1)[1].split(";", 1)[0]


def test_the_flake_pins_the_nixpkgs_this_lane_tests(root, checkouts):
    """flake.lock holds nixpkgs to one revision, so `nix run github:Atyzze/syncrain` builds against
    what was tested here, until the lock is updated on purpose; this lane's checkout is that one."""
    lock = json.loads((root / "flake.lock").read_text())
    pinned = lock["nodes"]["nixpkgs"]
    assert pinned["original"] == {"owner": "NixOS", "ref": "nixos-unstable", "repo": "nixpkgs", "type": "github"}
    assert pinned["locked"]["type"] == "github" and pinned["locked"]["narHash"].startswith("sha256-")
    nixpkgs, _ = checkouts
    revision = pathlib.Path(nixpkgs) / ".git-revision"             # a channel's tarball says it here
    if revision.is_file():
        here = revision.read_text().strip()
    else:                                                          # a git checkout
        done = subprocess.run(["git", "-C", nixpkgs, "rev-parse", "HEAD"], capture_output=True, text=True)
        need(done.returncode == 0, f"{nixpkgs} does not say its revision")
        here = done.stdout.strip()
    assert here == pinned["locked"]["rev"], \
        "the lane tests another nixpkgs than the lock pins: update one of them (docs/agent/ENVIRONMENT.md)"
    if revision.is_file():
        # the revision alone passes a lock whose hash is wrong, which `nix run` then refuses: the
        # tree GitHub serves for it is this one without what the channel adds
        assert nar_hash(pathlib.Path(nixpkgs), CHANNEL_ONLY) == pinned["locked"]["narHash"]


#: What a nixpkgs channel adds to the tree of its git revision.
CHANNEL_ONLY = {".git-revision", ".version-suffix", "nixpkgs", "programs.sqlite", "svn-revision"}


def nar_hash(top: pathlib.Path, leave_out=frozenset()) -> str:
    """Nix's hash of a folder: SHA-256 over its NAR serialisation, in SRI form; `leave_out` names
    entries of the top folder that are not part of it."""
    import base64
    import hashlib
    import stat
    h = hashlib.sha256()

    def put(b: bytes) -> None:
        h.update(len(b).to_bytes(8, "little") + b + b"\0" * (-len(b) % 8))

    def node(path: pathlib.Path, skip=frozenset()) -> None:
        put(b"(")
        put(b"type")
        st = path.lstat()
        if stat.S_ISLNK(st.st_mode):
            put(b"symlink"); put(b"target"); put(os.fsencode(os.readlink(path)))
        elif stat.S_ISDIR(st.st_mode):
            put(b"directory")
            for name in sorted(os.fsencode(n) for n in os.listdir(path) if n not in skip):
                put(b"entry"); put(b"("); put(b"name"); put(name); put(b"node")
                node(path / os.fsdecode(name))
                put(b")")
        else:
            put(b"regular")
            if st.st_mode & 0o100:
                put(b"executable"); put(b"")
            data = path.read_bytes()
            put(b"contents"); put(data)
        put(b")")

    put(b"nix-archive-1")
    node(top, leave_out)
    return "sha256-" + base64.b64encode(h.digest()).decode()
