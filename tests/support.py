"""Helpers the lanes share (imported as `tests.support`; fixtures live in conftest.py)."""
from __future__ import annotations

import contextlib
import getpass
import os
import signal
import subprocess
import sys
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


def stub(folder: Path, name: str, body: str) -> Path:
    """`folder/name`, a shell script standing in for a command of the system's."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(0o755)
    return path


#: Where login_install puts the system's side of the login screen, under its base folder.
LOGIN_PATHS = {"SYNCRAIN_LOGIN_LIB": "lib", "SYNCRAIN_LOGIN_STATE": "state",
               "SYNCRAIN_GREETD_CONFIG": "etc/greetd/config.toml", "SYNCRAIN_GREETD_PAM": "etc/pam.d/greetd",
               "SYNCRAIN_DM_LINK": "display-manager.service"}


def login_install(base: Path, *args: str, src: Path = ROOT, prefix: tuple = (), user: str | None = None,
                  timeout: float = 180) -> subprocess.CompletedProcess:
    """install.sh --no-deps run for real from `src`, with home, config and cache under `base` and the
    system's side of the login screen there too (LOGIN_PATHS; the record of what started at boot
    lands beside greetd's config). sudo, KWin, greetd's text login and systemctl are stubs: sudo
    writes each command it runs to base/sudo.calls; systemctl says there is no user session, writes
    every other call to base/systemctl.calls and moves the display-manager link as systemd does (a
    unit named gone*.service is not installed; a file base/systemctl.refuse fails the next call).
    `prefix` runs it as `user` (setpriv)."""
    bins = base / "bin"
    link = base / LOGIN_PATHS["SYNCRAIN_DM_LINK"]
    stub(bins, "sudo", f'echo "$@" >> {base}/sudo.calls; exec "$@"')
    stub(bins, "kwin_wayland", "exit 0")
    stub(bins, "agreety", "exit 0")
    stub(bins, "systemctl", f'''[ "$1" = --user ] && exit 1
case "$1 $2" in "cat gone"*) exit 1 ;; "cat "*) exit 0 ;; esac
echo "$@" >> {base}/systemctl.calls
if [ -f {base}/systemctl.refuse ]; then rm -f {base}/systemctl.refuse; echo "Access denied" >&2; exit 1; fi
case "$1 $2 $3" in
  *" gone"*) echo "Failed to enable unit: Unit file $3 does not exist." >&2; exit 1 ;;
  "enable --force "*) ln -sfn "/usr/lib/systemd/system/$3" {link} ;;
  "disable "*) if [ "$(basename "$(readlink {link})")" = "$2" ]; then rm -f {link}; fi ;;
esac
exit 0''')
    env = {"HOME": str(base / "home"), "XDG_CONFIG_HOME": str(base / "config"), "LANG": "C.UTF-8",
           "XDG_CACHE_HOME": str(base / "cache"), "TMPDIR": str(base), "PYTHONDONTWRITEBYTECODE": "1",
           "PATH": f"{bins}:{os.path.dirname(sys.executable)}:/usr/bin:/bin", "CC": "no-compiler-here",
           "SYNCRAIN_LOGIN_OWNER": user or getpass.getuser(),
           **{key: str(base / path) for key, path in LOGIN_PATHS.items()}}
    for key in ("GI_TYPELIB_PATH", "LD_LIBRARY_PATH"):
        if key in os.environ:
            env[key] = os.environ[key]
    return subprocess.run([*prefix, "bash", str(src / "install.sh"), "--no-deps", *args], cwd=src, env=env,
                          capture_output=True, text=True, timeout=timeout)


#: The user root runs install.sh as here (setpriv), as no user of the operator's is root.
NOBODY = 65534


class AnotherUser:
    """install.sh run by a user who is not root, as on the operator's desktop, so that everything it
    does as root goes through the sudo stub and is written down (login_install). The lanes in the
    cloud run as root, which becomes `nobody` here, in a folder of its own with a copy of the release
    folder; anyone else runs as themselves, in tmp_path, from this tree. A folder named root-only
    stays root's."""

    def __init__(self, tmp_path: Path):
        import pwd
        import shutil
        import tempfile
        self.root = os.getuid() == 0
        if not self.root:
            self.name, self.base, self.src, self.prefix = None, tmp_path, ROOT, ()
            return
        entry = pwd.getpwuid(NOBODY)
        self.name, self.gid = entry.pw_name, entry.pw_gid
        self.base = Path(tempfile.mkdtemp(prefix="syncrain-user-"))
        self.src = self.base / "src"
        self.src.mkdir()
        for name in ("install.sh", "BUILD_NUMBER"):
            shutil.copy2(ROOT / name, self.src / name)
        shutil.copytree(ROOT / "syncrain", self.src / "syncrain", ignore=shutil.ignore_patterns("__pycache__"))
        self.prefix = ("setpriv", f"--reuid={NOBODY}", f"--regid={self.gid}", "--clear-groups")

    def unreadable(self, text: str) -> Path:
        """A file this user can see but not read: root's, or one of mode 000."""
        folder = self.base / "root-only"
        folder.mkdir(exist_ok=True)
        folder.chmod(0o711)
        path = folder / "secret"
        path.write_text(text)
        path.chmod(0o600 if self.root else 0)
        return path

    def install(self, *args: str, src: Path | None = None) -> subprocess.CompletedProcess:
        """install.sh from the release folder `src` (by default this tree's, or its copy)."""
        if self.root:                       # what the test made there is the user's, as at home
            os.lchown(self.base, NOBODY, self.gid)
            for top, dirs, files in os.walk(self.base):
                dirs[:] = [d for d in dirs if d != "root-only"]
                for name in dirs + files:
                    os.lchown(os.path.join(top, name), NOBODY, self.gid)
        return login_install(self.base, *args, src=src or self.src, prefix=self.prefix, user=self.name)

    def calls(self, what: str) -> list[str]:
        """What went through the sudo or systemctl stub ("sudo", "systemctl"), in order."""
        path = self.base / f"{what}.calls"
        return path.read_text().splitlines() if path.exists() else []

    def close(self) -> None:
        if self.root:
            import shutil
            shutil.rmtree(self.base, ignore_errors=True)


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
