"""Helpers the lanes share (imported as `tests.support`; fixtures live in conftest.py)."""
from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: GTK 4.14 and 4.15 take these as GDK_DEBUG flags; 4.16 and later as GDK_DISABLE features.
#: Setting both reaches every GTK the app supports; each ignores the other's spelling.
GL_ONLY_ES = {"GDK_DEBUG": "gl-disable-gl", "GDK_DISABLE": "gl-api"}
GL_ONLY_DESKTOP = {"GDK_DEBUG": "gl-disable-gles", "GDK_DISABLE": "gles-api"}
GL_NONE = {"GDK_DEBUG": "gl-disable", "GDK_DISABLE": "gl"}

#: A fixed moment every lane draws, so their pictures can be compared (2026-10-07 00:00:07 UTC).
MOMENT = 1791331207


def mean_abs_diff(a: Path, b: Path) -> float:
    from PIL import Image, ImageChops, ImageStat
    x, y = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    assert x.size == y.size, f"{a.name} is {x.size}, {b.name} is {y.size}"
    return sum(ImageStat.Stat(ImageChops.difference(x, y)).mean) / 3


def brightness(path: Path) -> float:
    from PIL import Image, ImageStat
    return sum(ImageStat.Stat(Image.open(path).convert("RGB")).mean) / 3


class Session(dict):
    """The environment a client reaches a compositor with; `compositor` is the compositor's process."""

    compositor: subprocess.Popen


@contextlib.contextmanager
def headless_sway(run: Path, screen: str = "1280x720"):
    """A headless Sway with one screen of `screen` (WxH), run from the new runtime directory `run`:
    yields the environment a client reaches it with (XDG_RUNTIME_DIR, WAYLAND_DISPLAY, SWAYSOCK), as a
    Session."""
    run.mkdir(mode=0o700, parents=True)
    (run / "sway.conf").write_text(f"output * resolution {screen}\ndefault_border none\n")
    env = dict(os.environ, XDG_RUNTIME_DIR=str(run), WLR_BACKENDS="headless", WLR_LIBINPUT_NO_DEVICES="1",
               WLR_RENDERER="pixman", WLR_HEADLESS_OUTPUTS="1")
    env.pop("WAYLAND_DISPLAY", None)
    env.pop("DISPLAY", None)
    compositor = subprocess.Popen(["sway", "-c", str(run / "sway.conf")], env=env, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        deadline = time.monotonic() + 20
        while not (list(run.glob("wayland-*[0-9]")) and list(run.glob("sway-ipc.*"))):
            if compositor.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("headless sway did not start")
            time.sleep(0.1)
        session = Session(XDG_RUNTIME_DIR=str(run), WAYLAND_DISPLAY=sorted(p.name for p in run.glob("wayland-*[0-9]"))[0],
                          SWAYSOCK=str(sorted(run.glob("sway-ipc.*"))[0]))
        session.compositor = compositor
        yield session
    finally:
        if compositor.poll() is None:
            compositor.send_signal(signal.SIGTERM)
        try:
            compositor.wait(timeout=10)
        except subprocess.TimeoutExpired:
            compositor.kill()


def grab(session: dict, path: Path) -> None:
    """What the Wayland session's screen shows, as a PNG (grim)."""
    subprocess.run(["grim", str(path)], env=dict(os.environ, **session), check=True, timeout=30)


def our_text_files() -> list[Path]:
    """Every text file this project wrote (not generated pages, not binary assets, not caches)."""
    skip_dirs = {".git", "__pycache__", "var", "result", "build", "dist", ".pytest_cache"}
    suffixes = {".py", ".md", ".sh", ".nix", ".toml", ".glsl", ".frag", ".vert", ".js", ".json", ".txt", ".c",
                ".h"}
    generated = {ROOT / "web" / "index.html", ROOT / "web" / "artifact.html"}
    files = [p for p in ROOT.rglob("*") if p.is_file() and not (set(p.relative_to(ROOT).parts) & skip_dirs)
             and (p.suffix in suffixes or p.name in {"template.html", "LICENSE", ".gitignore"})
             and p not in generated and "fixtures" not in p.parts]
    return sorted(files)


_C_ESCAPES = {"\\": "\\", "'": "'", '"': '"', "n": "\n", "t": "\t", " ": " ", "s": " "}


def systemd_exec_words(value: str) -> list[str]:
    """Split an ExecStart= value as systemd does: %-specifiers on the whole line first, then words
    with quotes that may start mid-word and C escapes everywhere (inside single quotes too), then
    $VARIABLES per word. Covers what this project's writers produce, and refuses anything else.
    (systemd: src/core/load-fragment.c config_parse_exec, src/basic/extract-word.c.)"""
    assert "%" not in value.replace("%%", ""), f"a %-specifier would be expanded: {value}"
    line = value.replace("%%", "%")
    words, word, quote, i, started = [], [], None, 0, False
    while i < len(line):
        c = line[i]
        if c == "\\":
            nxt = line[i + 1] if i + 1 < len(line) else ""
            assert nxt in _C_ESCAPES, f"an escape systemd would read differently: \\{nxt}"
            word.append(_C_ESCAPES[nxt]); started = True; i += 2
            continue
        if quote:
            if c == quote:
                quote = None
            else:
                word.append(c)
        elif c in "'\"":
            quote, started = c, True
        elif c in " \t":
            if started:
                words.append("".join(word)); word, started = [], False
        else:
            word.append(c); started = True
        i += 1
    assert quote is None, f"unbalanced quotes: {value}"
    if started:
        words.append("".join(word))
    out = []
    for w in words:
        assert "$" not in w.replace("$$", ""), f"a variable would be expanded: {w}"
        out.append(w.replace("$$", "$"))
    return out
