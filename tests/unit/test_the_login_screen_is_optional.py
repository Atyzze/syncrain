"""The login screen stays optional. Only --login-screen changes how this machine logs in, and
--login-screen-off (or --uninstall by the user who set it up) puts back what was there before, and
nothing else. Installing, upgrading and removing the wallpaper leave the login screen of someone who
wants only the wallpaper as it was: greetd's config and PAM file, what starts at boot, the splash.
install.sh runs for real as a user who is not root (tests.support.AnotherUser), so everything it
would do as root is written down, and for the wallpaper alone that is nothing."""
from __future__ import annotations

import json
import os

import pytest

from syncrain import build

GREETD_OWN = '[terminal]\nvt = 1\n\n[default_session]\ncommand = "agreety --cmd /bin/sh"\nuser = "greeter"\n'
PAM = "#%PAM-1.0\nauth       include      system-local-login\nsession    include      system-local-login\n"


def machine(base, before="plasmalogin.service"):
    """A desktop with a login screen of its own: `before` starts at boot (None: nothing does), and
    greetd is installed with its own config."""
    (base / "etc/greetd").mkdir(parents=True)
    (base / "etc/greetd/config.toml").write_text(GREETD_OWN)
    (base / "etc/pam.d").mkdir(parents=True)
    (base / "etc/pam.d/greetd").write_text(PAM)
    if before:
        (base / "display-manager.service").symlink_to(f"/usr/lib/systemd/system/{before}")
    (base / "config").mkdir()
    (base / "config/ksplashrc").write_text("[KSplash]\nTheme=org.kde.breeze.desktop\n")


def login_side(base) -> dict:
    """All of the machine's login: greetd's files and anything beside them, what starts at boot,
    Plasma's splash, and whether syncrain's login screen is there."""
    out = {str(p.relative_to(base)): p.read_text() if p.is_file() else "a folder"
           for p in sorted((base / "etc").rglob("*"))}
    link = base / "display-manager.service"
    out["starts at boot"] = os.readlink(link) if link.is_symlink() else None
    out["splash"] = (base / "config/ksplashrc").read_text()
    out["syncrain's login screen"] = [name for name in ("lib", "state") if (base / name).exists()]
    return out


WALLPAPER_ONLY = {
    "install": [()],
    "autostart": [("--autostart", "--theme", "matrix")],
    "upgrade": [(), "older", ()],
    "uninstall": [("--autostart",), ("--uninstall",)],
    "off without one": [("--login-screen-off",)],
}


@pytest.mark.parametrize("steps", WALLPAPER_ONLY.values(), ids=WALLPAPER_ONLY.keys())
def test_the_wallpaper_alone_leaves_the_login_screen_as_it_was(another_user, steps):
    base = another_user.base
    machine(base)
    was = login_side(base)
    for step in steps:
        if step == "older":
            (base / "home/.local/share/syncrain/BUILD_NUMBER").write_text(f"{build.BUILD_NUMBER - 1}\n")
            continue
        done = another_user.install(*step)
        assert done.returncode == 0, done.stdout + done.stderr
        if "--login-screen-off" in step:
            assert "syncrain's login screen is not installed: the login screen stays as it is" in done.stdout
    assert login_side(base) == was
    assert another_user.calls("sudo") == [], "nothing done as root"
    assert another_user.calls("systemctl") == [], "what starts at boot not asked to change"


@pytest.mark.parametrize("before, calls", [
    ("plasmalogin.service", ["enable --force greetd.service", "enable --force plasmalogin.service"]),
    ("greetd.service", ["enable --force greetd.service"]),
    (None, ["enable --force greetd.service", "disable greetd.service"]),
], ids=["plasma login", "greetd itself", "no display manager"])
def test_off_puts_back_what_started_at_boot_before_and_only_that(another_user, before, calls):
    base = another_user.base
    machine(base, before)
    was = login_side(base)
    on = another_user.install("--login-screen")
    assert on.returncode == 0, on.stdout + on.stderr
    assert (base / "etc/greetd/display-manager.before-syncrain").read_text() == f"{before or 'none'}\n"
    assert "syncrain" in (base / "etc/greetd/config.toml").read_text()
    off = another_user.install("--login-screen-off")
    assert off.returncode == 0, off.stdout + off.stderr
    assert another_user.calls("systemctl") == calls
    assert login_side(base) == was, "greetd's config and PAM file as they were, nothing of syncrain's left"
    again = another_user.install("--login-screen-off")
    assert "syncrain's login screen is not installed" in again.stdout, again.stdout + again.stderr
    assert another_user.calls("systemctl") == calls, "a second --login-screen-off changes nothing"


@pytest.mark.parametrize("upgrade", [True, False], ids=["upgraded first", "straight off"])
def test_the_record_builds_16_and_17_kept_in_the_copy_still_counts(another_user, upgrade):
    base = another_user.base
    machine(base, "plasmalogin.service")
    assert another_user.install("--login-screen").returncode == 0
    record = base / "etc/greetd/display-manager.before-syncrain"
    record.unlink()
    (base / "lib/previous-display-manager").write_text("plasmalogin.service\n")
    if upgrade:                             # a newer build moves it beside greetd's config
        up = another_user.install()
        assert up.returncode == 0 and record.read_text() == "plasmalogin.service\n", up.stdout + up.stderr
    off = another_user.install("--login-screen-off")
    assert off.returncode == 0, off.stdout + off.stderr
    assert another_user.calls("systemctl")[-1] == "enable --force plasmalogin.service"
    assert not record.exists() and not (base / "lib").exists()


def test_with_nothing_recorded_off_takes_syncrain_s_out_and_leaves_what_starts_at_boot(another_user):
    """Builds 16 and 17 recorded nothing when greetd itself, or nothing, started at boot before. With
    syncrain's greetd starting at boot now, what came before is not known, and so it is recorded."""
    base = another_user.base
    machine(base, "greetd.service")
    was = login_side(base)
    assert another_user.install("--login-screen").returncode == 0
    record = base / "etc/greetd/display-manager.before-syncrain"
    record.unlink()                                     # as builds 16 and 17 left it
    again = another_user.install("--login-screen")
    assert again.returncode == 0 and record.read_text() == "unknown\n", again.stdout + again.stderr
    off = another_user.install("--login-screen-off")
    assert off.returncode == 0, off.stdout + off.stderr
    assert "what started at boot before is not known, so greetd stays, with its own config" in off.stdout
    assert another_user.calls("systemctl") == ["enable --force greetd.service"] * 2
    assert login_side(base) == was


def test_off_leaves_a_display_manager_picked_since(another_user):
    """The operator went back by hand (the console line --login-screen prints), then picked another."""
    base = another_user.base
    machine(base, "plasmalogin.service")
    assert another_user.install("--login-screen").returncode == 0
    link = base / "display-manager.service"
    link.unlink()
    link.symlink_to("/usr/lib/systemd/system/sddm.service")
    off = another_user.install("--uninstall")
    assert off.returncode == 0, off.stdout + off.stderr
    assert "what starts at boot (sddm.service) stays" in off.stdout
    assert another_user.calls("systemctl") == ["enable --force greetd.service"]
    assert os.readlink(link) == "/usr/lib/systemd/system/sddm.service"
    assert (base / "etc/greetd/config.toml").read_text() == GREETD_OWN
    assert (base / "etc/pam.d/greetd").read_text() == PAM
    assert not (base / "lib").exists() and not (base / "etc/greetd/display-manager.before-syncrain").exists()


def test_a_display_manager_removed_since_does_not_stop_the_way_back(another_user):
    """greetd stays then, with its own config: still a way to log in, and the wallpaper goes."""
    base = another_user.base
    machine(base, "gone-dm.service")
    assert another_user.install("--login-screen").returncode == 0
    gone = another_user.install("--uninstall")
    assert gone.returncode == 0, gone.stdout + gone.stderr
    assert "gone-dm.service is not installed any more, so greetd stays, with its own config" in gone.stdout
    assert (base / "etc/greetd/config.toml").read_text() == GREETD_OWN
    assert (base / "etc/pam.d/greetd").read_text() == PAM
    assert not (base / "lib").exists() and not (base / "home/.local/share/syncrain").exists()


def test_another_user_s_wallpaper_leaves_the_login_screen_as_its_owner_set_it_up(another_user):
    """On a machine with more users, the one who set the login screen up is the one who changes it."""
    base = another_user.base
    machine(base)
    assert another_user.install("--login-screen").returncode == 0
    login = base / "lib/login.json"
    login.write_text(json.dumps(dict(json.loads(login.read_text()), user="someone-else")))
    was, as_root = login_side(base), another_user.calls("sudo")
    for step in ((), ("--uninstall",)):
        done = another_user.install(*step)
        assert done.returncode == 0, done.stdout + done.stderr
        assert "the login screen stays as someone-else set it up" in done.stdout
    assert login_side(base) == was
    assert another_user.calls("sudo") == as_root, "nothing more done as root"


def test_a_way_back_systemctl_refused_keeps_its_record_for_the_next_run(another_user):
    """A passing failure (sudo refused, say) leaves greetd for now, and the record for the next run."""
    base = another_user.base
    machine(base, "plasmalogin.service")
    assert another_user.install("--login-screen").returncode == 0
    (base / "systemctl.refuse").write_text("")
    first = another_user.install("--login-screen-off")
    assert first.returncode == 0, first.stdout + first.stderr
    assert "systemctl could not enable plasmalogin.service: greetd stays for now" in first.stdout
    record = base / "etc/greetd/display-manager.before-syncrain"
    assert record.read_text() == "plasmalogin.service\n" and not (base / "lib").exists()
    second = another_user.install("--login-screen-off")
    assert second.returncode == 0, second.stdout + second.stderr
    assert os.readlink(base / "display-manager.service") == "/usr/lib/systemd/system/plasmalogin.service"
    assert not record.exists()


def test_a_new_login_screen_records_what_starts_at_boot_then(another_user):
    """A record counts while greetd starts at boot: once the operator picks another display manager,
    that is what the next --login-screen comes after."""
    base = another_user.base
    machine(base, "plasmalogin.service")
    assert another_user.install("--login-screen").returncode == 0
    (base / "systemctl.refuse").write_text("")
    assert another_user.install("--login-screen-off").returncode == 0     # Plasma Login's record stays
    link = base / "display-manager.service"
    link.unlink()
    link.symlink_to("/usr/lib/systemd/system/sddm.service")
    assert another_user.install("--login-screen").returncode == 0
    assert (base / "etc/greetd/display-manager.before-syncrain").read_text() == "sddm.service\n"
    off = another_user.install("--login-screen-off")
    assert off.returncode == 0, off.stdout + off.stderr
    assert os.readlink(link) == "/usr/lib/systemd/system/sddm.service"


def test_build_17_s_record_survives_a_refused_way_back(another_user):
    """Builds 16 and 17 kept the record in the app copy, which the first run takes out."""
    base = another_user.base
    machine(base, "plasmalogin.service")
    assert another_user.install("--login-screen").returncode == 0
    record = base / "etc/greetd/display-manager.before-syncrain"
    record.unlink()
    (base / "lib/previous-display-manager").write_text("plasmalogin.service\n")
    (base / "systemctl.refuse").write_text("")
    first = another_user.install("--login-screen-off")
    assert first.returncode == 0 and record.read_text() == "plasmalogin.service\n", first.stdout + first.stderr
    second = another_user.install("--login-screen-off")
    assert second.returncode == 0, second.stdout + second.stderr
    assert os.readlink(base / "display-manager.service") == "/usr/lib/systemd/system/plasmalogin.service"
    assert not record.exists()


def test_greetd_s_own_settings_stay_and_the_wallet_goes_to_the_service_it_names(another_user):
    """Only [default_session] is syncrain's: a PAM service with a second factor, an automatic login and
    the terminal stay, and the wallet lines go to that service, not to one greetd does not use. The
    greeter itself runs without them (greetd-greeter, the service greetd runs its greeter under)."""
    base = another_user.base
    machine(base, "plasmalogin.service")
    own = ('[terminal]\nvt = 2\n\n[general]\nservice = "greetd-otp"  # with a second factor\n\n'
           '[default_session]\ncommand = "agreety --cmd /bin/sh"\nuser = "greeter"\n\n'
           '[initial_session]\ncommand = "startplasma-wayland"\nuser = "op"\n')
    (base / "etc/greetd/config.toml").write_text(own)
    otp = PAM + "auth       required     pam_google_authenticator.so\n"
    (base / "etc/pam.d/greetd-otp").write_text(otp)
    was = login_side(base)
    on = another_user.install("--login-screen")
    assert on.returncode == 0, on.stdout + on.stderr
    import tomllib
    config = tomllib.loads((base / "etc/greetd/config.toml").read_text())
    assert config["terminal"] == {"vt": 2} and config["general"] == {"service": "greetd-otp"}
    assert config["initial_session"] == {"command": "startplasma-wayland", "user": "op"}
    assert config["default_session"]["user"] == "greeter" and "login.sh" in config["default_session"]["command"]
    assert (base / "etc/pam.d/greetd").read_text() == PAM, "a service greetd does not use is left alone"
    added = (base / "etc/pam.d/greetd-otp").read_text()
    assert added.startswith(otp) and "pam_kwallet5.so" in added
    greeter = (base / "etc/pam.d/greetd-greeter").read_text()      # greetd's own name for the greeter's
    assert greeter.splitlines()[1:] == otp.splitlines() and "kwallet" not in greeter
    off = another_user.install("--login-screen-off")
    assert off.returncode == 0, off.stdout + off.stderr
    assert login_side(base) == was



def test_an_upgrade_from_build_18_gets_greetd_s_own_settings_and_the_greeter_s_file(another_user):
    """Build 18 wrote greetd's whole config and gave the greeter no PAM file of its own; a plain
    ./install.sh of this build puts both right."""
    base = another_user.base
    machine(base, "plasmalogin.service")
    own = '[terminal]\nvt = 2\n\n[default_session]\ncommand = "agreety --cmd /bin/sh"\nuser = "greeter"\n'
    (base / "etc/greetd/config.toml").write_text(own)
    assert another_user.install("--login-screen").returncode == 0
    (base / "etc/pam.d/greetd-greeter").unlink()
    login = base / "lib/syncrain/login/login.sh"
    (base / "etc/greetd/config.toml").write_text(              # as build 18 left it
        f'# written by syncrain\'s install.sh --login-screen\n[terminal]\nvt = 1\n\n[default_session]\n'
        f'command = "sh -c \'test -x {login} && exec {login}; exec agreety --cmd startplasma-wayland\'"\n'
        'user = "greeter"\n')
    up = another_user.install()
    assert up.returncode == 0, up.stdout + up.stderr
    import tomllib
    config = tomllib.loads((base / "etc/greetd/config.toml").read_text())
    assert config["terminal"] == {"vt": 2} and "login.sh" in config["default_session"]["command"]
    assert "kwallet" not in (base / "etc/pam.d/greetd-greeter").read_text()
    assert another_user.install("--login-screen-off").returncode == 0
    assert (base / "etc/greetd/config.toml").read_text() == own
    assert not (base / "etc/pam.d/greetd-greeter").exists()
