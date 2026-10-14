"""greetd's config as --login-screen changes it (syncrain/greetdconf.py): [default_session] and
nothing else, again and again alike; the PAM service it names."""
from __future__ import annotations

import tomllib

from syncrain import greetdconf

OWN = ('# the operator\'s\n[terminal]\nvt = 1\n\n[general]\nservice = "greetd-otp"\nsource_profile = false\n\n'
       '[default_session]\ncommand = """agreety\n  --cmd /bin/sh"""\nuser = "greeter"\n\n'
       "[initial_session]\ncommand = 'startplasma-wayland'\nuser = \"op\"\n")
LOGIN = "sh -c 'test -x /usr/local/lib/syncrain/syncrain/login/login.sh && exec it'"


def test_only_the_default_session_changes():
    out = greetdconf.edit(OWN, LOGIN, "greeter")
    was, now = tomllib.loads(OWN), tomllib.loads(out)
    assert now["default_session"] == {"command": LOGIN, "user": "greeter"}
    assert {k: v for k, v in now.items() if k != "default_session"} == \
        {k: v for k, v in was.items() if k != "default_session"}
    assert "# the operator's" in out and greetdconf.ours(out) and not greetdconf.ours(OWN)


def test_a_second_run_changes_nothing_more():
    once = greetdconf.edit(OWN, LOGIN, "greeter")
    assert greetdconf.edit(once, LOGIN, "greeter") == once


def test_a_config_without_a_default_session_or_terminal_gets_both():
    out = tomllib.loads(greetdconf.edit("[general]\nservice = \"x\"\n", "c", "greeter"))
    assert out == {"general": {"service": "x"}, "terminal": {"vt": 1},
                   "default_session": {"command": "c", "user": "greeter"}}
    assert tomllib.loads(greetdconf.edit("", "c", "greeter"))["terminal"] == {"vt": 1}


def test_the_pam_service_is_the_one_greetd_names():
    assert greetdconf.service(OWN) == "greetd-otp"
    assert greetdconf.service("[terminal]\nvt = 1\n") == "greetd"
    assert greetdconf.service('[general]\nservice = "../../etc/shadow"\n') == "greetd", "a name, never a path"


def test_greetd_s_own_looser_syntax_is_changed_as_it_is(capsys, monkeypatch):
    """greetd reads vt = next unquoted, which strict TOML does not: still only [default_session]."""
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("[terminal]\nvt = next\n\n[default_session]\ncommand = 'x'\n"))
    assert greetdconf.main(["config", "c", "greeter"]) == 0
    out = capsys.readouterr().out
    assert "vt = next" in out and 'command = "c"' in out and "command = 'x'" not in out


def test_the_greeter_s_service_is_the_one_greetd_runs_it_under():
    assert greetdconf.greeter_service(OWN) == "greetd-greeter", "greetd's default, whatever [general] says"
    assert greetdconf.greeter_service('[default_session]\nservice = "mine-greeter"\n') == "mine-greeter"
