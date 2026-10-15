"""greetd's config.toml as install.sh --login-screen changes it: only [default_session]'s command
and user, so whatever else the operator set there stays (a PAM service of their own in [general],
an [initial_session] that logs in automatically, the terminal, source_profile).

    python -m syncrain.greetdconf config COMMAND USER < config.toml > new.toml
    python -m syncrain.greetdconf service < config.toml      # the PAM service greetd logs users in with
    python -m syncrain.greetdconf greeter-service < config.toml   # the one its greeter runs under
    python -m syncrain.greetdconf user < config.toml         # the user it runs its greeter as
"""
from __future__ import annotations

import json
import re
import sys

MARK = "# [default_session] set by syncrain's install.sh --login-screen; --login-screen-off puts it back"
SECTION = re.compile(r"^\s*\[\s*([A-Za-z0-9_.-]+)\s*\]\s*(#.*)?$")
KEY = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*=")


def _lines_of_values(lines: list[str]) -> list[tuple[int, int, str | None]]:
    """(first line, line after, key) for each line or multi-line value; key None for anything else."""
    out, i = [], 0
    while i < len(lines):
        line, start = lines[i], i
        key = KEY.match(line)
        i += 1
        if key:
            rest = line.split("=", 1)[1]
            for quote in ('"""', "'''"):
                if rest.count(quote) == 1:                  # a value over several lines
                    while i < len(lines) and quote not in lines[i]:
                        i += 1
                    i += 1
                    break
        out.append((start, min(i, len(lines)), key.group(1) if key else None))
    return out


def _quote(value: str) -> str:
    return json.dumps(value)                                # a TOML basic string is a JSON string


def edit(text: str, command: str, user: str) -> str:
    """`text` with [default_session] running `command` as `user`; everything else as it was."""
    lines = [line for line in text.splitlines() if line.strip() != MARK]
    out, section, seen, done = [], None, False, False
    wanted = {"command": f"command = {_quote(command)}", "user": f"user = {_quote(user)}"}

    def finish():
        nonlocal done
        if section == "default_session" and not done:
            while out and not out[-1].strip():
                out.pop()
            out.extend(wanted.values())
            out.append("")
            done = True

    for start, end, key in _lines_of_values(lines):
        head = SECTION.match(lines[start])
        if head:
            finish()
            section = head.group(1)
            if section == "default_session":
                seen = True
            out.append(lines[start])
            continue
        if section == "default_session" and key in wanted:
            continue                                        # written once, at the section's end
        out.extend(lines[start:end])
    finish()
    if not seen:
        while out and not out[-1].strip():
            out.pop()
        out += ["", "[default_session]", *wanted.values()]
    if not any((m := SECTION.match(line)) and m.group(1) == "terminal" for line in out):
        while out and not out[0].strip():
            out.pop(0)
        out = ["[terminal]", "vt = 1", "", *out]            # greetd's own default; it needs one
    while out and not out[-1].strip():
        out.pop()
    return "\n".join([MARK, *out]) + "\n"


def ours(text: str) -> bool:
    return any(line.strip() == MARK for line in text.splitlines())


def _value(text: str, wanted_section: str, wanted_key: str) -> str | None:
    """A one-line value that is a plain name, or None."""
    section, lines = None, text.splitlines()
    for start, _end, key in _lines_of_values(lines):
        head = SECTION.match(lines[start])
        if head:
            section = head.group(1)
        elif section == wanted_section and key == wanted_key:
            value = lines[start].split("=", 1)[1].split("#", 1)[0].strip().strip("\"'")
            return value if re.fullmatch(r"[A-Za-z0-9._-]+", value) else None
    return None


def service(text: str) -> str:
    """The PAM service greetd logs users in with: [general] service, else "greetd"."""
    return _value(text, "general", "service") or "greetd"


def greeter_service(text: str) -> str:
    """The PAM service greetd runs its greeter under, where that file exists ([default_session]
    service, else "greetd-greeter"); without the file, greetd uses service() for the greeter too."""
    return _value(text, "default_session", "service") or "greetd-greeter"


def user(text: str) -> str | None:
    """The user greetd runs its greeter as ([default_session] user), which each family names its
    own way (greeter, _greetd, greetd); None if it names none."""
    return _value(text, "default_session", "user")


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
    if argv[:1] == ["config"] and len(argv) == 3:
        out = edit(text, argv[1], argv[2])
        # A config strict TOML reads must read after the change too; greetd reads more than strict
        # TOML (vt = next, unquoted), and such a config is changed as it is.
        if parses(text) is not False and parses(out) is False:
            print("syncrain: greetd's config would not read after the change", file=sys.stderr)
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
