"""greetd's config as --login-screen changes it (syncrain/greetdconf.py): [default_session] and
nothing else, again and again alike, read as greetd 0.10 reads it (its own line-by-line reader, not
TOML); --login-screen-off's way back; the PAM service it names."""
from __future__ import annotations

import io
import tomllib

from syncrain import greetdconf

OWN = ('# the operator\'s\n[terminal]\nvt = 1\n\n[general]\nservice = "greetd-otp"\nsource_profile = false\n\n'
       '[default_session]\ncommand = "agreety --cmd /bin/sh"\nuser = "greeter"\n\n'
       "[initial_session]\ncommand = 'startplasma-wayland'\nuser = \"op\"\n")
LOGIN = ("sh -c 'test -r /usr/local/lib/syncrain/syncrain/login/login.sh && "
         "exec /bin/sh /usr/local/lib/syncrain/syncrain/login/login.sh'")


def greetd_reads(text):
    """[default_session]'s command and user as greetd takes them."""
    session = greetdconf.read(text)["default_session"]
    return {k: greetdconf.unquote(v) for k, v in session.items() if k in ("command", "user")}


def run(argv, text, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    code = greetdconf.main(argv)
    said = capsys.readouterr()
    return code, said.out, said.err


def test_only_the_default_session_changes():
    out = greetdconf.edit(OWN, LOGIN, "greeter")
    was, now = tomllib.loads(OWN), tomllib.loads(out)
    assert now["default_session"] == {"command": LOGIN, "user": "greeter"}
    assert {k: v for k, v in now.items() if k != "default_session"} == \
        {k: v for k, v in was.items() if k != "default_session"}
    assert greetd_reads(out) == {"command": LOGIN, "user": "greeter"}
    assert "# the operator's" in out and greetdconf.ours(out) and not greetdconf.ours(OWN)
    assert greetdconf.check(OWN, out, {"command": LOGIN, "user": "greeter"}) is None


def test_a_second_run_changes_nothing_more():
    once = greetdconf.edit(OWN, LOGIN, "greeter")
    assert greetdconf.edit(once, LOGIN, "greeter") == once


def test_a_config_without_a_default_session_or_terminal_gets_both():
    out = tomllib.loads(greetdconf.edit("[general]\nservice = \"x\"\n", "c", "greeter"))
    assert out == {"general": {"service": "x"}, "terminal": {"vt": 1},
                   "default_session": {"command": "c", "user": "greeter"}}
    assert tomllib.loads(greetdconf.edit("", "c", "greeter"))["terminal"] == {"vt": 1}


def test_the_section_greetd_uses_is_the_one_changed():
    """greetd takes the last [default_session] when there are two (an earlier build's edit wrote
    into the first and emptied the second: greetd then had no command and did not start)."""
    two = ('[terminal]\nvt = 1\n\n[default_session]\ncommand = "agreety --cmd /bin/sh"\nuser = "greeter"\n\n'
           '# switched later\n[default_session]\ncommand = "tuigreet --cmd sway"\nuser = "greeter"\n')
    out = greetdconf.edit(two, LOGIN, "greeter")
    assert greetd_reads(out) == {"command": LOGIN, "user": "greeter"}
    assert 'command = "agreety --cmd /bin/sh"' in out, "the section greetd does not read stays as it was"
    back = greetdconf.restore(out, two)
    assert greetd_reads(back) == {"command": "tuigreet --cmd sway", "user": "greeter"}


def test_a_triple_quote_in_a_value_is_just_characters():
    """greetd has no values over several lines: a ''' in a command swallows nothing after it."""
    text = ('[terminal]\nvt = 1\n\n[default_session]\ncommand = "agreety --cmd \'\'\'"\nuser = "greeter"\n\n'
            '[initial_session]\ncommand = "sway"\nuser = "op"\n')
    out = greetdconf.edit(text, LOGIN, "greeter")
    assert greetdconf.read(out)["initial_session"] == {"command": '"sway"', "user": '"op"'}
    assert greetdconf.check(text, out, {"command": LOGIN, "user": "greeter"}) is None


def test_a_config_greetd_cannot_read_is_left_as_it_is(capsys, monkeypatch):
    """A TOML value over several lines is no greetd config (greetd stops at it): nothing is written."""
    text = '[terminal]\nvt = 1\n\n[default_session]\ncommand = """agreety\n  --cmd /bin/sh"""\n'
    code, out, err = run(["config", LOGIN, "greeter"], text, capsys, monkeypatch)
    assert code == 1 and out == "" and "greetd would not read it" in err


def test_greetd_s_own_looser_syntax_is_changed_as_it_is(capsys, monkeypatch):
    """greetd reads vt = next unquoted, which strict TOML does not: still only [default_session]."""
    code, out, _ = run(["config", "c", "greeter"], "[terminal]\nvt = next\n\n[default_session]\ncommand = 'x'\n",
                       capsys, monkeypatch)
    assert code == 0
    assert "vt = next" in out and 'command = "c"' in out and "command = 'x'" not in out


def test_the_way_back_keeps_what_changed_since(tmp_path, capsys, monkeypatch):
    """--login-screen-off: [default_session]'s command and user as they were written before, and a
    section the operator added while the login screen was on stays."""
    out = greetdconf.edit(OWN, LOGIN, "greeter")
    later = out + '\n[general2]\nkey = "theirs"\n'
    before = tmp_path / "before"
    before.write_text(OWN)
    code, back, err = run(["restore", str(before)], later, capsys, monkeypatch)
    assert code == 0, err
    assert greetd_reads(back) == greetd_reads(OWN) and 'command = "agreety --cmd /bin/sh"' in back
    assert greetdconf.read(back)["general2"] == {"key": '"theirs"'} and not greetdconf.ours(back)
    assert greetdconf.restore(out, OWN) == OWN, "with nothing changed since, the file as it was"


def test_greetd_s_unquoting():
    assert greetdconf.unquote('"a \\"b\\" \\\\ c"') == 'a "b" \\ c'
    assert greetdconf.unquote("'it'") == "it" and greetdconf.unquote("next") == "next"
    for bad in ('"open', '"x" # a comment'):
        try:
            greetdconf.unquote(bad)
        except greetdconf.Unreadable:
            continue
        raise AssertionError(bad)


def test_the_pam_service_is_the_one_greetd_names():
    assert greetdconf.service(OWN) == "greetd-otp"
    assert greetdconf.service("[terminal]\nvt = 1\n") == "greetd"
    assert greetdconf.service('[general]\nservice = "../../etc/shadow"\n') == "greetd", "a name, never a path"
    assert greetdconf.service('[general]\nservice = "a"\n[general]\nservice = "b"\n') == "b", "greetd's: the last"


def test_the_greeter_s_service_is_the_one_greetd_runs_it_under():
    assert greetdconf.greeter_service(OWN) == "greetd-greeter", "greetd's default, whatever [general] says"
    assert greetdconf.greeter_service('[default_session]\nservice = "mine-greeter"\n') == "mine-greeter"


def test_the_way_back_with_greetd_s_own_bare_words(tmp_path, capsys, monkeypatch):
    """`command = tuigreet --cmd sway` is greetd's own syntax, no TOML: it comes back as it was."""
    before = '[terminal]\nvt = 1\n\n[default_session]\ncommand = tuigreet --cmd sway\nuser = greeter\n'
    (tmp_path / "before").write_text(before)
    code, back, err = run(["restore", str(tmp_path / "before")], greetdconf.edit(before, LOGIN, "greeter"),
                          capsys, monkeypatch)
    assert code == 0, err
    assert greetd_reads(back) == {"command": "tuigreet --cmd sway", "user": "greeter"}


def test_no_way_back_to_a_config_greetd_would_not_start_with(tmp_path, capsys, monkeypatch):
    (tmp_path / "before").write_text("[terminal]\nvt = 1\n")
    code, out, err = run(["restore", str(tmp_path / "before")], greetdconf.edit("[terminal]\nvt = 1\n", LOGIN, "g"),
                         capsys, monkeypatch)
    assert code == 1 and out == "" and "no [default_session] command" in err


def test_a_greeter_chosen_since_stays(tmp_path, capsys, monkeypatch):
    (tmp_path / "before").write_text(OWN)
    theirs = greetdconf.edit(OWN, LOGIN, "greeter").replace(greetdconf._quote(LOGIN), '"tuigreet --cmd sway"')
    code, out, err = run(["restore", str(tmp_path / "before")], theirs, capsys, monkeypatch)
    assert code == 0 and "changed since" in err
    assert greetd_reads(out)["command"] == "tuigreet --cmd sway" and not greetdconf.ours(out)


def test_quotes_and_escapes_as_greetd_reads_them():
    """enquote's rules (greetd's): \\uXXXX, \\x41, octal, \\a; a quote of its kind inside is refused."""
    assert greetdconf.unquote('"\\u0041\\x42\\103\\a"') == "ABC\x07"
    for bad in ('"a"b"', "'it's'", '"\\u{41}"', '"\\q"'):
        try:
            greetdconf.unquote(bad)
        except greetdconf.Unreadable:
            continue
        raise AssertionError(bad)
    # lines as greetd splits them: a lone carriage return or form feed is no line end
    assert greetdconf.read('[a]\nk = x\fy\n')["a"] == {"k": "x\fy"}
    assert greetdconf.read('[a]\r\nk = v\r\n')["a"] == {"k": "v"}
