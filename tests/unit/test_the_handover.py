"""After a login, Plasma's splash and its wallpaper show a still frame of the rain (build 17), and go
back to what they were (syncrain/handover.py). Plasma's shell is a stand-in here: the Arch root ran
the real one by hand."""
from __future__ import annotations

import json

from syncrain import handover


def test_one_key_of_a_kde_file_changes_and_the_rest_stays(tmp_path):
    rc = tmp_path / "ksplashrc"
    rc.write_text("[Other]\nTheme=keep\n\n[KSplash]\nEngine=KSplashQML\nTheme=org.kde.breeze.desktop\n")
    handover.write_ini(rc, "KSplash", "Theme", "org.syncrain.splash")
    assert handover.read_ini(rc, "KSplash", "Theme") == "org.syncrain.splash"
    assert handover.read_ini(rc, "Other", "Theme") == "keep"
    handover.write_ini(rc, "KSplash", "Theme", None)
    assert handover.read_ini(rc, "KSplash", "Theme") is None
    assert handover.read_ini(rc, "KSplash", "Engine") == "KSplashQML"
    fresh = tmp_path / "none"
    handover.write_ini(fresh, "KSplash", "Theme", "x")
    assert fresh.read_text() == "[KSplash]\nTheme=x\n"


class Shell:
    """Plasma's shell as far as the hand-over uses it: two desktops and their wallpapers."""

    def __init__(self):
        self.desktops = [["org.kde.image", "file:///usr/share/wallpapers/mountains.png", "1"],
                         ["org.kde.color", "", "2"], ["org.kde.image", "", "3"]]
        self.scripts = []

    def __call__(self, script):
        self.scripts.append(script)
        if script == handover.READ_WALLPAPERS:
            return json.dumps(self.desktops)
        want = json.loads(script.split("var want = ", 1)[1].split(";\n", 1)[0])
        out = []
        for i, (_plugin, _image, did) in enumerate(self.desktops):
            w = want[min(i, len(want) - 1)]
            w = next((e for e in want if len(e) > 2 and e[2] == did), w)
            out.append([w[0], w[1], did])
        self.desktops = out
        return ""


def test_on_shows_the_still_after_login_and_off_puts_everything_back(tmp_path, monkeypatch):
    for key, sub in (("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"), ("XDG_STATE_HOME", "state")):
        monkeypatch.setenv(key, str(tmp_path / sub))
    (tmp_path / "config").mkdir()
    (tmp_path / "config/ksplashrc").write_text("[KSplash]\nTheme=org.kde.breeze.desktop\n")
    made = []

    def still(rain, path):
        made.append(rain)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"png")
        return True
    monkeypatch.setattr(handover, "make_still", still)
    shell = Shell()
    said = handover.on(["--theme", "matrix"], shell=shell)
    assert made == [["--theme", "matrix"]] and len(said) == 2, said
    package = tmp_path / "data/plasma/look-and-feel/org.syncrain.splash"
    assert json.loads((package / "metadata.json").read_text())["KPackageStructure"] == "Plasma/LookAndFeel"
    assert (package / "contents/splash/images/still.png").read_bytes() == b"png"
    assert "images/still.png" in (package / "contents/splash/Splash.qml").read_text()
    rc = tmp_path / "config/ksplashrc"
    assert handover.read_ini(rc, "KSplash", "Theme") == "org.syncrain.splash"
    assert handover.read_ini(rc, "KSplash", "Engine") == "KSplashQML"
    still_uri = (tmp_path / "data/wallpapers/syncrain.png").as_uri()
    assert [d[:2] for d in shell.desktops] == [["org.kde.image", still_uri]] * 3
    shell.desktops.reverse()                                  # desktops come in another order now

    handover.on(["--theme", "matrix"], shell=shell)          # a newer build: what was there first is kept
    assert handover.off(shell=shell) == ["splash after login: as before", "Plasma's wallpaper: as before"]
    assert sorted(shell.desktops, key=lambda d: d[2]) == [
        ["org.kde.image", "file:///usr/share/wallpapers/mountains.png", "1"], ["org.kde.color", "", "2"],
        ["org.kde.image", "", "3"]]
    assert 'd.writeConfig("Image", w[1])' in shell.scripts[-1] and "&& w[1]" not in shell.scripts[-1]
    assert handover.read_ini(rc, "KSplash", "Theme") == "org.kde.breeze.desktop"
    assert handover.read_ini(rc, "KSplash", "Engine") is None
    assert not package.exists() and not (tmp_path / "data/wallpapers/syncrain.png").exists()
    assert handover.off(shell=shell) == [], "nothing to put back twice"


def test_a_shell_that_does_not_answer_leaves_the_wallpaper_and_says_so(tmp_path, monkeypatch):
    for key, sub in (("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"), ("XDG_STATE_HOME", "state")):
        monkeypatch.setenv(key, str(tmp_path / sub))
    monkeypatch.setattr(handover, "make_still", lambda rain, path: (path.parent.mkdir(parents=True), path.write_bytes(b"p")))

    def gone(_script):
        raise OSError("no plasmashell")
    said = handover.on([], shell=gone)
    assert said[0] == "splash after login: the still frame" and "did not answer: no plasmashell" in said[1]


def test_off_outside_plasma_keeps_what_it_needs_to_try_again(tmp_path, monkeypatch):
    for key, sub in (("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"), ("XDG_STATE_HOME", "state")):
        monkeypatch.setenv(key, str(tmp_path / sub))
    monkeypatch.setattr(handover, "make_still", lambda rain, path: (path.parent.mkdir(parents=True), path.write_bytes(b"p")))
    shell = Shell()
    handover.on([], shell=shell)

    def gone(_script):
        raise OSError("no plasmashell")
    said = handover.off(shell=gone)
    assert "run ./install.sh --login-screen-off again" in said[-1]
    assert handover.state_path().exists() and handover.still_path().exists()
    assert handover.off(shell=shell)[-1] == "Plasma's wallpaper: as before"
    assert not handover.state_path().exists()


def _homes(tmp_path, monkeypatch):
    for key, sub in (("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"), ("XDG_STATE_HOME", "state")):
        monkeypatch.setenv(key, str(tmp_path / sub))
    (tmp_path / "config").mkdir(exist_ok=True)
    monkeypatch.setattr(handover, "make_still",
                        lambda rain, path: (path.parent.mkdir(parents=True, exist_ok=True), path.write_bytes(b"p"), True)[2])
    return tmp_path / "config/ksplashrc"


def test_a_newer_build_makes_the_still_again_and_changes_nothing_chosen_since(tmp_path, monkeypatch):
    rc = _homes(tmp_path, monkeypatch)
    shell = Shell()
    handover.on([], shell=shell)
    handover.write_ini(rc, "KSplash", "Theme", "org.kde.breeze.desktop")        # chosen since, in Plasma
    shell.desktops[1] = ["org.kde.image", "file:///home/op/beach.png", shell.desktops[1][2]]
    chosen = [list(d) for d in shell.desktops]
    scripts = len(shell.scripts)
    assert handover.still(["--theme", "matrix"]) == ["the still frame: made again"]
    assert len(shell.scripts) == scripts and shell.desktops == chosen
    assert handover.read_ini(rc, "KSplash", "Theme") == "org.kde.breeze.desktop"
    said = handover.off(shell=shell)
    assert said == ["splash after login: the one chosen since stays",
                    "Plasma's wallpaper: as before where the still was; 1 chosen since stay"]
    assert shell.desktops[1][1] == "file:///home/op/beach.png", "the beach stays"
    assert shell.desktops[0][1] == "file:///usr/share/wallpapers/mountains.png"
    assert handover.read_ini(rc, "KSplash", "Theme") == "org.kde.breeze.desktop"


def test_a_run_that_broke_off_does_not_make_syncrain_s_splash_the_one_to_go_back_to(tmp_path, monkeypatch):
    rc = _homes(tmp_path, monkeypatch)
    rc.write_text("[KSplash]\nEngine=KSplashQML\nTheme=org.syncrain.splash\n")     # left, with no record
    shell = Shell()
    handover.on([], shell=shell)
    assert json.loads(handover.state_path().read_text())["splash"] == {"Engine": None, "Theme": None}
    handover.off(shell=shell)
    assert handover.read_ini(rc, "KSplash", "Theme") is None, "Plasma's own splash"
