"""The native wallpaper: syncrain on Wayland with neither Python nor GTK in memory (syncrain/native/).

`syncrain` reads its options here, in Python. For the wallpaper on a Wayland session it then
prepares the scene, everything a frame needs that never changes (the shader sources, the textures'
pixels and the uniforms set once, made by the same code the GTK host uses: syncrain/renderer.py),
writes it to a memfd and replaces its own process with the native program (`os.execve`, same pid),
which draws every screen with one OpenGL context and keeps nothing else: no interpreter, no
toolkit. Python's memory goes with the exec.

Where the program is: SYNCRAIN_WALLPAPER (the Nix package sets it, the test lanes too), else
`syncrain/native/syncrain-wallpaper` beside this file, where install.sh builds it. Without it, on
X11, in a window, for --screenshot and --record, or with --host gtk, the GTK host draws as before.
The scene names the command that starts the GTK host; the native program runs it when it cannot
draw (no layer-shell, no EGL, a driver that refuses the shaders), so the wallpaper still draws
wherever the GTK host would.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from . import build, hidden
from .renderer import STATIC_TEXTURES, from_args, rgba_pil, shader_bodies, static_uniforms, texture_sources

NAME = "syncrain-wallpaper"
SCENE_CONTRACT = "syncrain-scene-1"
HOSTS = ("auto", "native", "gtk")


def binary() -> str | None:
    """The native program, if it is there and can be run."""
    named = os.environ.get("SYNCRAIN_WALLPAPER")
    path = Path(named) if named else Path(__file__).resolve().parent / "native" / NAME
    return str(path) if path.is_file() and os.access(path, os.X_OK) else None


def wayland_session() -> bool:
    """GTK would open Wayland here: WAYLAND_DISPLAY is set and GDK_BACKEND does not put X11 first."""
    if not os.environ.get("WAYLAND_DISPLAY"):
        return False
    first = os.environ.get("GDK_BACKEND", "").split(",")[0].strip()
    return first in ("", "*", "wayland")


def applies(args) -> bool:
    """The wallpaper itself, on Wayland: what the native program draws. Build 4's frame timer
    (--pacing timer, the power sweep's point of comparison) is the GTK host's, as it was."""
    return not (args.window or args.record or args.screenshot) and args.pacing == "refresh" and wayland_session()


def _number(kind, value) -> str:
    """A uniform's value as the scene carries it: integers as such, floats exactly (hexadecimal)."""
    return str(int(value)) if kind in ("i", "ui") else float(value).hex()


def scene_bytes(args, fallback: list[str] | None) -> bytes:
    """The scene, as syncrain/native/scene.c reads it."""
    r = from_args(args)
    sources, r.bg_size, r.mask_bbox = texture_sources(r, rgba_pil)
    header = [SCENE_CONTRACT, f"describe {build.describe()}", f"epoch0 {int(r.epoch0)}", f"cols {int(r.cols)}"]
    keep = r.keep_mode()
    if keep[0] == "logo":
        header.append(f"keep logo {float(keep[1]).hex()} {float(keep[2]).hex()}")
    elif keep[0] == "mask":
        header.append("keep mask " + " ".join(float(v).hex() for v in keep[1]) + f" {float(keep[2]).hex()}")
    else:
        header.append("keep none")
    if r.bg_size:
        header.append(f"bg {r.bg_size[0]} {r.bg_size[1]}")
    blobs: list[bytes] = []
    size = 0

    def put(data: bytes) -> str:
        nonlocal size
        blobs.append(data)
        size += len(data)
        return f"{size - len(data)} {len(data)}"

    for name, body in shader_bodies(r.data_dir).items():
        header.append(f"shader {name} {put(body.encode())}")
    for name in STATIC_TEXTURES:
        w, h, kind, data = sources.pop(name)
        header.append(f"texture {name} {w} {h} {kind} {put(data)}")
        del data
    for program, name, kind, values in static_uniforms(r):
        header.append(f"uniform {program} {name} {kind} " + " ".join(_number(kind, v) for v in values))
    script = hidden.script_template(maximized=args.pause_under == "maximized")
    header.append(f"kwin-script {put(script.encode())}")
    if fallback:
        header.append(f"fallback {put(b''.join(a.encode() + b'\0' for a in fallback))}")
    header.append("end")
    return ("\n".join(header) + "\n").encode() + b"".join(blobs)


def gtk_host_command(user_args) -> list[str]:
    """The command that started this process, with the same options and --host gtk: what the native
    program runs when it cannot draw. sys.orig_argv keeps the interpreter's own part (`python3 -m
    syncrain`, or the Nix package's wrapped script) in front of the options."""
    orig = list(getattr(sys, "orig_argv", None) or [])
    tail = sys.argv[1:]
    if tail and orig[len(orig) - len(tail):] == tail:
        program = orig[:len(orig) - len(tail)]
    elif not tail and orig:
        program = orig
    else:
        program = [sys.executable, "-m", "syncrain"]
    return program + list(user_args) + ["--host", "gtk"]


def environment() -> dict:
    """The native program's environment: gtk4-layer-shell out of LD_PRELOAD (it would load GTK into
    the process for nothing), kept in SYNCRAIN_LD_PRELOAD for the GTK host, should it take over."""
    env = dict(os.environ)
    preload = env.get("LD_PRELOAD", "")
    kept = [p for p in re.split(r"[\s:]+", preload) if p and "gtk4-layer-shell" not in os.path.basename(p)]
    if preload:
        env["SYNCRAIN_LD_PRELOAD"] = preload
    if kept:
        env["LD_PRELOAD"] = " ".join(kept)
    else:
        env.pop("LD_PRELOAD", None)
    return env


def command(path: str, args, scene_fd: int) -> list[str]:
    layer = args.layer or ("bottom" if "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "") else "background")
    cmd = [path, "--scene", str(scene_fd), "--fps", repr(float(args.fps)), "--pause-under", args.pause_under,
           "--scale", repr(float(args.scale)), "--layer", layer, "--offset", repr(float(args.offset))]
    if args.time is not None:
        cmd += ["--time", repr(float(args.time))]
    return cmd


def scene_fd(data: bytes) -> int:
    """A memfd holding the scene, inherited by the program exec'd next."""
    fd = os.memfd_create("syncrain-scene", os.MFD_CLOEXEC)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.set_inheritable(fd, True)
    except OSError:
        os.close(fd)
        raise
    return fd


def run(args, user_args, path: str) -> str:
    """Replace this process with the native wallpaper. Returns only when that cannot happen, with why.

    The scene names the GTK host's command, which the native program runs when it cannot draw;
    with --host native it names none, so the program says why and stops instead."""
    fd = None
    try:
        fallback = None if args.host == "native" else gtk_host_command(user_args)
        fd = scene_fd(scene_bytes(args, fallback))
        argv = command(path, args, fd)
        sys.stdout.flush()
        sys.stderr.flush()
        os.execve(path, argv, environment())
    except OSError as e:
        return f"the native wallpaper did not start ({e})"
    finally:
        if fd is not None:                      # still here: the scene must not stay with the GTK host
            os.close(fd)
    return "the native wallpaper did not start"


def probe(args, path: str, timeout: float = 60) -> tuple[int, list[str]]:
    """What the native program finds here, without drawing: (exit status, its lines)."""
    import subprocess
    fd = scene_fd(scene_bytes(args, None))
    try:
        done = subprocess.run([path, "--probe", "--scene", str(fd)], pass_fds=(fd,), env=environment(),
                              capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        return 1, [f"the native wallpaper did not run: {e}"]
    finally:
        os.close(fd)
    lines = [line for line in done.stdout.splitlines() if line.strip()]
    lines += [line for line in done.stderr.splitlines() if line.startswith("syncrain")]
    return done.returncode, lines
