"""greetd's config.toml as install.sh --login-screen changes it: only [default_session]'s command
and user, so whatever else the operator set there stays (a PAM service of their own in [general],
an [initial_session] that logs in automatically, the terminal, source_profile).

greetd does not read it as TOML. Its own reader (greetd 0.10, `inish`) goes line by line: a line
that starts with `#` is a comment, `[name]` starts a section, anything else is `key = value`; a
section named again replaces the earlier one, and a key named again in a section replaces the
earlier one; there are no values over several lines. A value that starts with a quote is unquoted,
backslash escapes and all. Everything here reads it that way, and an edit is read back that way
before it is written: it must say what was meant, and every other section what it said before.

    python -m syncrain.greetdconf config COMMAND USER < config.toml > new.toml
    python -m syncrain.greetdconf restore BEFORE < config.toml > new.toml   # [default_session] as BEFORE had it
    python -m syncrain.greetdconf service < config.toml      # the PAM service greetd logs users in with
    python -m syncrain.greetdconf greeter-service < config.toml   # the one its greeter runs under
    python -m syncrain.greetdconf user < config.toml         # the user it runs its greeter as
"""
from __future__ import annotations

import json
import re
import sys

MARK = "# [default_session] set by syncrain's install.sh --login-screen; --login-screen-off puts it back"
SESSION = "default_session"
LOGIN_SH = "syncrain/login/login.sh"           # in syncrain's command, wherever the app is
OURS = ("command", "user")


class Unreadable(ValueError):
    """What greetd itself would refuse to start with."""


#: What Rust's trim() takes away (Unicode White_Space): Python's strip() also takes \x1c to \x1f.
_SPACE = "".join(chr(c) for c in range(0x110000) if chr(c).isspace() and not 0x1c <= c <= 0x1f)


def _trim(s: str) -> str:
    return s.strip(_SPACE)


def _lines(text: str) -> list[str]:
    """Lines as Rust's lines() gives them: split at \\n only, one \\r before it dropped."""
    out = [line.removesuffix("\r") for line in text.split("\n")]
    return out[:-1] if out and out[-1] == "" else out


def _kind(line: str) -> tuple[str, str | None]:
    """How greetd reads one line: ("blank" | "comment" | "section" | "key", the name)."""
    s = _trim(line)
    if not s:
        return "blank", None
    if s.startswith("#"):
        return "comment", None
    if s.startswith("["):
        if not s.endswith("]"):
            raise Unreadable(f"a section without its ']': {s!r}")
        return "section", _trim(s[1:-1])
    if "=" not in s:
        raise Unreadable(f"no '=' in {s!r}")
    return "key", _trim(s.split("=", 1)[0])


def _raw(line: str) -> str:
    return _trim(_trim(line).split("=", 1)[1].strip("="))


def read(text: str) -> dict[str, dict[str, str]]:
    """The config as greetd reads it: each section's keys and their values as written (quotes and
    all). The keys before any section are under ""."""
    sections: dict[str, dict[str, str]] = {}
    name, current = "", {}
    for line in _lines(text):
        kind, what = _kind(line)
        if kind == "section":
            sections[name] = current
            name, current = what, {}
        elif kind == "key":
            current[what] = _raw(line)
    sections[name] = current
    return sections


_ESCAPES = {"a": "\x07", "b": "\x08", "f": "\x0c", "n": "\n", "r": "\r", "t": "\t", "v": "\x0b"}


def _take(chars: list, n: int) -> str:
    out = "".join(chars[:n])
    del chars[:n]
    return out + "\0" * (n - len(out))             # as Rust's unwrap_or_default


def _radix(text: str, base: int, top: int) -> int:
    if not text or not all(c in "0123456789abcdefABCDEF"[:base + (6 if base == 16 else 0)] for c in text):
        raise Unreadable("an escape greetd does not know")
    value = int(text, base)
    if value > top:
        raise Unreadable("an escape greetd does not know")
    return value


def unquote(value: str) -> str:
    """A value as greetd takes it (`maybe_unquote`, then enquote's `unquote`): one that starts with
    a quote loses its quotes and has its escapes undone, an unescaped quote of its kind inside is
    refused; any other value is as it is."""
    if not value or value[0] not in "\"'":
        return value
    quote = value[0]
    if len(value) < 2 or value[-1] != quote:
        raise Unreadable(f"an unended quote: {value!r}")
    chars, out = list(value[1:-1]), []
    while chars:
        c = chars.pop(0)
        if c == quote:
            raise Unreadable(f"a quote inside a quoted value: {value!r}")
        if c != "\\":
            out.append(c)
            continue
        if not chars:
            raise Unreadable(f"a value ending in a backslash: {value!r}")
        c = chars.pop(0)
        if c in "\\\"'`":
            out.append(c)
        elif c in _ESCAPES:
            out.append(_ESCAPES[c])
        elif c in "0123456789":
            out.append(chr(_radix(c + _take(chars, 2), 8, 255)))
        elif c == "x":
            out.append(chr(_radix(_take(chars, 2), 16, 255)))
        elif c in "uU":
            code = _radix(_take(chars, 4 if c == "u" else 8), 16, 0x10FFFF)
            if 0xD800 <= code <= 0xDFFF:
                raise Unreadable(f"no character: {value!r}")
            out.append(chr(code))
        else:
            raise Unreadable(f"an escape greetd does not know in {value!r}")
    return "".join(out)


def _quote(value: str) -> str:
    # a JSON string reads back as greetd unquotes it (and as a TOML basic string), for what a
    # command holds: no control characters but tabs and newlines, which both escape alike
    return json.dumps(value, ensure_ascii=False)


def _last_section(lines: list[str], name: str) -> tuple[int, int] | None:
    """(header line, the line after the section) of the last section called `name`, or None."""
    found, start = None, None
    for i, line in enumerate(lines):
        kind, what = _kind(line)
        if kind == "section":
            if start is not None:
                found, start = (start, i), None
            if what == name:
                start = i
    if start is not None:
        found = (start, len(lines))
    return found


def _set_keys(lines: list[str], wanted: list[str], drop: tuple[str, ...]) -> list[str]:
    """`lines` with the last [default_session]'s `drop` keys taken out and `wanted` at its end (a
    new section at the end of the file when there is none)."""
    span = _last_section(lines, SESSION)
    if span is None:
        out = list(lines)
        while out and not out[-1].strip():
            out.pop()
        return out + ([""] if out else []) + [f"[{SESSION}]", *wanted]
    head, end = span
    body = [line for line in lines[head + 1:end] if not (_kind(line)[0] == "key" and _kind(line)[1] in drop)]
    tail = []
    while body and not body[-1].strip():
        tail.insert(0, body.pop())
    return [*lines[:head + 1], *body, *wanted, *(tail or ([""] if end < len(lines) else [])), *lines[end:]]


def edit(text: str, command: str, user: str) -> str:
    """`text` with the [default_session] greetd uses running `command` as `user`; everything else as
    it was. greetd needs a [terminal]: its own default goes in where there is none."""
    lines = [line for line in _lines(text) if _trim(line) != MARK]
    out = _set_keys(lines, [f"command = {_quote(command)}", f"user = {_quote(user)}"], OURS)
    if "terminal" not in read("\n".join(out)):
        while out and not out[0].strip():
            out.pop(0)
        out = ["[terminal]", "vt = 1", "", *out]
    while out and not out[-1].strip():
        out.pop()
    return "\n".join([MARK, *out]) + "\n"


def restore(text: str, before: str) -> str:
    """`text` with [default_session]'s command and user as `before` had them, written as it wrote
    them; everything changed since (another section, a key of the operator's) stays."""
    lines = [line for line in _lines(text) if _trim(line) != MARK]
    old = _lines(before)
    span = _last_section(old, SESSION)
    wanted = []
    if span is not None:
        keep = {}
        for line in old[span[0] + 1:span[1]]:
            kind, key = _kind(line)
            if kind == "key" and key in OURS:
                keep[key] = _trim(line)          # greetd takes the last of each
        wanted = [keep[k] for k in OURS if k in keep]
    out = _set_keys(lines, wanted, OURS)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out) + "\n"


def check(before: str, after: str, wanted: dict[str, str]) -> str | None:
    """Why greetd would not read `after` as meant, or None: [default_session]'s keys as `wanted`
    says (unquoted; a key missing from `wanted` must be missing), and every other section as in
    `before`."""
    try:
        was, now = read(before), read(after)
        session = {k: unquote(v) for k, v in now.get(SESSION, {}).items() if k in OURS}
    except Unreadable as e:
        return f"greetd would not read it: {e}"
    if session != wanted:
        return f"greetd would read [{SESSION}] as {session}, not {wanted}"
    for name in (set(was) | set(now)) - {SESSION, "terminal"}:
        if was.get(name, {}) != now.get(name, {}):
            return f"[{name}] would change" if name else "the keys before any section would change"
    if was.get("terminal") and was["terminal"] != now.get("terminal"):
        return "[terminal] would change"
    if "vt" not in now.get("terminal", {}):
        return "greetd needs [terminal]'s vt"
    rest = {k: v for k, v in now.get(SESSION, {}).items() if k not in OURS}
    if rest != {k: v for k, v in was.get(SESSION, {}).items() if k not in OURS}:
        return f"[{SESSION}]'s other keys would change"
    return None


def _value(text: str, wanted_section: str, wanted_key: str) -> str | None:
    """A value that is a plain name, as greetd reads it, or None."""
    try:
        value = unquote(read(text).get(wanted_section, {}).get(wanted_key, ""))
    except Unreadable:
        return None
    return value if re.fullmatch(r"[A-Za-z0-9._-]+", value) else None


def ours(text: str) -> bool:
    return any(_trim(line) == MARK for line in _lines(text))


def service(text: str) -> str:
    """The PAM service greetd logs users in with: [general] service, else "greetd"."""
    return _value(text, "general", "service") or "greetd"


def greeter_service(text: str) -> str:
    """The PAM service greetd runs its greeter under, where that file exists ([default_session]
    service, else "greetd-greeter"); without the file, greetd uses service() for the greeter too."""
    return _value(text, SESSION, "service") or "greetd-greeter"


def user(text: str) -> str | None:
    """The user greetd runs its greeter as ([default_session] user), which each family names its
    own way (greeter, _greetd, greetd); None if it names none."""
    return _value(text, SESSION, "user")


def parses(text: str) -> bool | None:
    """Whether strict TOML reads it (tomllib, where this Python has it; None without)."""
    try:
        import tomllib
    except ImportError:
        return None
    try:
        tomllib.loads(text)
    except Exception:  # noqa: BLE001 - any refusal is the answer
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    text = sys.stdin.read()
    if argv[:1] in (["config"], ["restore"]):
        try:
            read(text)
        except Unreadable as e:
            print(f"syncrain: greetd's config was left as it is: greetd would not read it: {e}", file=sys.stderr)
            return 1
        if argv[0] == "config" and len(argv) == 3:
            out, wanted = edit(text, argv[1], argv[2]), {"command": argv[1], "user": argv[2]}
        elif argv[0] == "restore" and len(argv) == 2:
            with open(argv[1], encoding="utf-8") as fh:
                before = fh.read()
            try:
                wanted = {k: unquote(v) for k, v in read(before).get(SESSION, {}).items() if k in OURS}
            except Unreadable as e:
                print(f"syncrain: greetd's config before syncrain does not read: {e}", file=sys.stderr)
                return 1
            if "command" not in wanted:          # greetd would not start: syncrain's command is safer
                print("syncrain: greetd's config before syncrain names no [default_session] command", file=sys.stderr)
                return 1
            now = read(text).get(SESSION, {}).get("command", "")
            if LOGIN_SH not in now:
                # a greeter chosen while the login screen was on stays: only the mark goes
                sys.stdout.write("\n".join(line for line in _lines(text) if _trim(line) != MARK) + "\n")
                print("syncrain: greetd's [default_session] was changed since; it stays", file=sys.stderr)
                return 0
            out = restore(text, before)
        else:
            print(__doc__, file=sys.stderr)
            return 2
        why = check(text, out, wanted)
        # A config strict TOML reads must read after the change too (other tools read it so); on
        # the way back, only when the one before was strict TOML too (a bare word is greetd's own)
        strict_before = parses(before if argv[0] == "restore" else text)
        if why is None and strict_before is True and parses(out) is False:
            why = "strict TOML would not read it"
        if why:
            print(f"syncrain: greetd's config was left as it is: {why}", file=sys.stderr)
            return 1
        sys.stdout.write(out)
        return 0
    if argv[:1] == ["service"]:
        print(service(text))
        return 0
    if argv[:1] == ["greeter-service"]:
        print(greeter_service(text))
        return 0
    if argv[:1] == ["user"]:
        found = user(text)
        if found:
            print(found)
        return 0 if found else 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
