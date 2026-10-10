"""The web page in Chromium (software WebGL2): the same stream as the app, and a page that fits.

Needs node with Playwright and its Chromium (`docs/agent/ENVIRONMENT.md`). The page and the app
are separate implementations of the host side (JavaScript and Python) over the same shaders, so
the frame they draw at one moment is the test that they agree.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

from syncrain import build
from tests.conftest import need
from tests.support import MOMENT, mean_abs_diff


@pytest.fixture(scope="module")
def page(root):
    node = shutil.which("node")
    need(node is not None, "no node for the browser lane")
    env = dict(os.environ)
    if "NODE_PATH" not in env and shutil.which("npm"):
        env["NODE_PATH"] = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    probe = subprocess.run([node, "-e", "require('playwright')"], env=env, capture_output=True, text=True)
    need(probe.returncode == 0, "Playwright is not installed for node (npm i -g playwright)")

    def run(*args):
        done = subprocess.run([node, str(root / "tests/browser/page.js"), *map(str, args)], env=env,
                              capture_output=True, text=True, timeout=300)
        assert done.returncode == 0, done.stderr[-2000:]
        result = json.loads(done.stdout.strip().splitlines()[-1])
        assert not result.pop("errors"), "the page logged errors"
        return result
    return run


#: Every picture option, as the page's URL says it and as the command line does.
LOOK = {"speed": "0.5", "density": "1.7", "glow": "0.3", "bloom": "0.5", "bg-gain": "0.6", "snow": "off",
        "hieroglyphs": "0.6"}


@pytest.mark.parametrize("look", [{}, LOOK], ids=["defaults", "every-option"])
def test_the_page_and_the_app_draw_the_same_frame(page, app, tmp_path, look):
    web, native = tmp_path / "web.png", tmp_path / "native.png"
    page("shot", web, 1280, 720, f"t={MOMENT}&hud=0" + "".join(f"&{k}={v}" for k, v in look.items()))
    options = [x for k, v in look.items() for x in ("--" + k, v)]
    done = app(["--window", "--size", "1280x720", "--time", str(MOMENT), "--screenshot", str(native), *options])
    assert done.returncode == 0, done.stderr
    assert mean_abs_diff(web, native) < 1.0


def test_screens_of_one_shape_share_one_stream(page):
    small = page("state", 1280, 720, f"t={MOMENT}&hud=0")
    large = page("state", 1920, 1080, f"t={MOMENT}&hud=0")
    assert small == large


def test_another_channel_is_another_stream(page):
    public = page("state", 1280, 720, f"t={MOMENT}&hud=0&channel=public")
    friends = page("state", 1280, 720, f"t={MOMENT}&hud=0&channel=friends")
    assert public["rows"] == friends["rows"] and public["hash"] != friends["hash"]


def test_the_page_says_which_build_and_stream_it_is(page):
    said = page("identity")
    assert said == {"build": build.BUILD_NUMBER, "stream": build.stream_id(),
                    "ident": f"Build {build.BUILD_NUMBER} · stream {build.stream_id()}"}


def test_the_controls_fit_a_desk_and_a_phone(page):
    for size, seen in page("controls").items():
        assert seen == {"overflow": False, "shown": True}, size
