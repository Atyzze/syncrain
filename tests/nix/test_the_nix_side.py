"""The Nix package and the NixOS and home-manager services, evaluated and built from this tree.

Needs nix-instantiate and nix-build, and local checkouts named by SYNCRAIN_NIXPKGS (nixpkgs) and
SYNCRAIN_HOME_MANAGER (home-manager), so nothing is fetched at evaluation time
(`docs/agent/ENVIRONMENT.md`). The build itself downloads its dependencies from the binary cache.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

from syncrain import build
from tests.conftest import need
from tests.support import MOMENT, mean_abs_diff, systemd_exec_words

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
    assert service["prevent"] == 69
    if which == "nixos":                      # set there; the home-manager service keeps the default
        assert words[words.index("--pause-under") + 1] == "fullscreen", words
    else:
        assert "--pause-under" not in words, words


def test_the_built_package_says_its_build_and_draws_the_same_frame(root, checkouts, tmp_path, app, x_display):
    nixpkgs, _ = checkouts
    out = tmp_path / "result"
    done = subprocess.run(["nix-build", str(root / "tests/nix/package.nix"), "--arg", "src", str(root),
                           "--arg", "nixpkgs", nixpkgs, "-o", str(out)], capture_output=True, text=True, timeout=1800)
    assert done.returncode == 0, done.stderr[-3000:]
    said = subprocess.run([str(out / "bin/syncrain"), "--build"], capture_output=True, text=True, timeout=60)
    assert said.stdout.strip() == build.describe(), said.stdout + said.stderr
    nix_shot, tree_shot = tmp_path / "nix.png", tmp_path / "tree.png"
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "GI_TYPELIB_PATH", "LD_LIBRARY_PATH")}
    env.update(DISPLAY=x_display, GDK_BACKEND="x11")
    drew = subprocess.run([str(out / "bin/syncrain"), "--window", "--size", "960x540", "--time", str(MOMENT),
                           "--screenshot", str(nix_shot)], env=env, capture_output=True, text=True, timeout=300)
    assert drew.returncode == 0, drew.stderr[-2000:]
    assert app(["--window", "--size", "960x540", "--time", str(MOMENT), "--screenshot", str(tree_shot)]).returncode == 0
    assert mean_abs_diff(nix_shot, tree_shot) < 1.0
