"""The native wallpaper (syncrain/native/) against the Python host it stands in for, value for value.

The same moment draws the same frame on either host only if the processor-side arithmetic agrees to
the last bit: the viewport's geometry (renderer.geometry), the clock (engine.split_time) and the
frame schedule (pacing.py). The program prints its results for given inputs exactly
(`--selftest`, hexadecimal floats), and these tests compare them with Python's over many inputs,
edge cases included. The wayland and kwin lanes then run it as the wallpaper.

Needs a C compiler, pkg-config, wayland-scanner and the libwayland and libdbus headers
(docs/agent/ENVIRONMENT.md); no display.
"""
from __future__ import annotations

import os
import random
import struct
import subprocess
import sys

import pytest

from syncrain import engine, native, pacing
from syncrain.renderer import Renderer, geometry

#: Refresh intervals in microseconds, as GTK and the native wallpaper compute them from a screen's
#: mode (1e9 / millihertz): 60, 59.94, 75, 120, 141.33, 144, 165 and 240 Hz.
REFRESHES = [16666, 16683, 13333, 8333, 7075, 6944, 6060, 4166]


def selftest(binary, what, lines):
    done = subprocess.run([str(binary), "--selftest", what], input="\n".join(lines) + "\n", capture_output=True,
                          text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    return done.stdout.splitlines()


def f32(x):
    return struct.unpack("f", struct.pack("f", x))[0]


def test_it_is_started_by_syncrain_and_says_so_otherwise(native_wallpaper):
    done = subprocess.run([str(native_wallpaper)], capture_output=True, text=True, timeout=30)
    assert done.returncode == 2 and "started by syncrain" in done.stderr


def renderers():
    """The three ways the hidden words keep clear: of the logo, of a mask's bright part, of nothing."""
    logo = Renderer(theme="nixos")
    plain = Renderer(theme="matrix")
    masked = Renderer(theme="matrix", background="unused.png", mask="unused.png")
    masked.mask_bbox = (0.3125, 0.21, 0.6640625, 0.734375)
    return logo, plain, masked


def test_the_geometry_is_the_python_host_s_to_the_last_bit(native_wallpaper):
    rnd = random.Random(8)
    sizes = [(2560, 1440), (1920, 1080), (3840, 2160), (1366, 768), (1362, 768), (1080, 1920), (320, 180),
             (64, 36), (5120, 1440), (768, 1366), (1, 1), (767, 13), (2048, 1152), (4096, 2304)]
    sizes += [(rnd.randint(64, 7680), rnd.randint(36, 4320)) for _ in range(300)]
    cases, lines = [], []
    for r in renderers():
        for drift in (0.03, 0.0, 0.1):
            r.motion["uDrift"] = drift
            for bg in (None, (3840, 2160), (1000, 1500)):
                if bg and r.mask_bbox is None:
                    continue
                r.bg_size = bg
                keep = r.keep_mode()
                size = keep[1] if keep[0] == "logo" else 0.0
                box = keep[1] if keep[0] == "mask" else (0.0, 0.0, 0.0, 0.0)
                for w, h in sizes:
                    cases.append(geometry(w, h, r.cols, r))
                    lines.append(" ".join([str(w), str(h), str(r.cols), keep[0], float(size).hex(), float(drift).hex(),
                                           *(float(v).hex() for v in box), str(bg[0] if bg else 0),
                                           str(bg[1] if bg else 0)]))
    out = selftest(native_wallpaper, "geometry", lines)
    assert len(out) == len(cases)
    for g, line, given in zip(cases, out, lines):
        words = line.split()
        assert [int(v) for v in words[:4]] == [g.cols, g.rows, g.qw, g.qh], given
        floats = [float.fromhex(v) for v in words[4:]]
        want = [g.cell, g.col0, *g.keep, *g.scale, *g.offset, g.sigma, *g.step_h, *g.step_v]
        assert floats == [float(v) for v in want], given


def test_the_clock_is_split_as_the_python_host_splits_it(native_wallpaper):
    rnd = random.Random(3)
    epoch0 = engine.load_meta()["epoch0"]
    times = [1791331207.0, 1791331207.9995, 1791331207.0004999, 1704067200.0, 1704067199.999, 0.0, 4294967295.5,
             1791331207.1235, 2000000000.001]
    times += [rnd.uniform(1.7e9, 2.1e9) for _ in range(3000)]
    times += [round(rnd.uniform(1.7e9, 2.1e9), 3) for _ in range(1000)]          # on the millisecond grid
    out = selftest(native_wallpaper, "time", [f"{t.hex()} {epoch0}" for t in times])
    for t, line in zip(times, out):
        sec, frac = engine.split_time(t, epoch0)
        got_sec, got_frac = line.split()
        assert int(got_sec) == sec and float.fromhex(got_frac) == f32(frac), t


def test_the_pacer_plans_what_pacing_py_plans(native_wallpaper):
    """Random runs of plan, shown, lead, step and restart, on every common refresh rate, with frames
    shown on time, a refresh early, late, and far off (a locked screen)."""
    rnd = random.Random(11)
    lines, expected = [], []
    for run in range(60):
        fps = rnd.choice([30.0, 30.0, 20.0, 15.0, 60.0, 24.0, 144.0, 7.5])
        refresh = rnd.choice(REFRESHES)
        p = pacing.Pacer(fps)
        lines.append(f"new {fps.hex()}")
        expected.append(("ok",))
        now = rnd.randint(10**9, 10**11)
        vblank = now - rnd.randint(0, refresh)
        targets = []
        for step in range(120):
            what = rnd.random()
            if what < 0.55:
                grid = 0 if rnd.random() < 0.05 else vblank
                r = 0 if rnd.random() < 0.03 else refresh
                delay, target = p.plan(now, r, grid)
                lines.append(f"plan {now} {r} {grid}")
                expected.append(("plan", delay, target))
                if target is not None:
                    targets.append(target)
                now += max(1000, int(delay)) + rnd.randint(0, 4000)
                vblank += ((now - vblank) // refresh) * refresh
            elif what < 0.85 and targets:
                target = rnd.choice(targets[-6:])
                off = rnd.choice([0, 0, 0, 1, -1, 2, -2, 5])
                presented = target + off * refresh + rnd.randint(-300, 300)
                p.shown(target, presented, refresh)
                lines.append(f"shown {target} {presented} {refresh}")
                expected.append(("shown", p.shift, p.settled_after))
            elif what < 0.92:
                lines.append(f"lead {refresh}")
                expected.append(("lead", p.lead(refresh)))
            elif what < 0.97:
                lines.append(f"step {refresh}")
                expected.append(("step", p.step(refresh)))
            else:
                p.restart()
                lines.append("restart")
                expected.append(("ok",))
    out = selftest(native_wallpaper, "pacer", lines)
    assert len(out) == len(expected)

    def same(text, value):
        return value is None if text == "none" else float.fromhex(text) == float(value)

    for given, want, got in zip(lines, expected, out):
        words = got.split()
        if want[0] == "ok":
            assert got == "ok", given
        elif want[0] in ("plan", "shown"):
            assert same(words[0], want[1]) and same(words[1], want[2]), (given, want, got)
        elif want[0] == "lead":
            assert same(words[0], want[1]), (given, want, got)
        else:
            assert int(words[0]) == want[1], (given, want, got)


def test_the_timing_report_counts_as_the_python_host_counts(native_wallpaper):
    rnd = random.Random(5)
    lines, expected = [], []
    for _ in range(200):
        refresh = rnd.choice(REFRESHES)
        t = rnd.randint(10**9, 10**10)
        presented = []
        for _ in range(rnd.randint(0, 40)):
            t += refresh * rnd.choice([2, 2, 2, 1, 3]) + rnd.randint(-200, 200)
            presented.append(t)
        lines.append(" ".join(["spacing", str(refresh), *map(str, presented)]))
        expected.append(" ".join(map(str, pacing.spacing(presented, refresh))))
        delays = [rnd.choice([16000.0, 16100.0, 33000.0]) + rnd.uniform(-3000, 3000) for _ in range(rnd.randint(0, 30))]
        lines.append(" ".join(["steady", *(d.hex() for d in delays)]))
        expected.append(pacing.steady(delays))
    out = selftest(native_wallpaper, "pacer", lines)
    for given, want, got in zip(lines, expected, out):
        if isinstance(want, str):
            assert got.strip() == want, given
        else:
            assert float.fromhex(got) == want, given


def scene_fd(data: bytes) -> int:
    fd = os.memfd_create("test-scene", 0)
    os.write(fd, data)
    return fd


def run_with_scene(binary, data, env, *extra):
    fd = scene_fd(data)
    try:
        return subprocess.run([str(binary), "--scene", str(fd), *extra], pass_fds=(fd,), env=env,
                              capture_output=True, text=True, timeout=60)
    finally:
        os.close(fd)


def test_a_scene_from_another_build_or_cut_short_is_refused(native_wallpaper, tmp_path):
    args = native_args()
    whole = native.scene_bytes(args, None)
    env = dict(os.environ, XDG_RUNTIME_DIR=str(tmp_path), WAYLAND_DISPLAY="nowhere")
    other = whole.replace(native.SCENE_CONTRACT.encode(), b"syncrain-scene-0", 1)
    done = run_with_scene(native_wallpaper, other, env)
    assert done.returncode == 70 and "syncrain-scene-0" in done.stderr, done.stderr
    cut = whole[:whole.index(b"\nend\n")] + b"\nend\n"                     # every offset now points past the end
    done = run_with_scene(native_wallpaper, cut, env)
    assert done.returncode == 70 and "outside the scene" in done.stderr, done.stderr


def native_args(*extra):
    from syncrain.app import parse_args
    return parse_args(["--channel", "test", *extra])


def test_without_a_compositor_it_hands_over_to_the_gtk_host(native_wallpaper, tmp_path):
    """Whatever stops it before the first frame runs the GTK host's command, with LD_PRELOAD as the
    launcher found it (the launcher takes gtk4-layer-shell out for the native program)."""
    marker = tmp_path / "took-over"
    host = [sys.executable, "-c", "import os, sys; open(sys.argv[1], 'w').write(os.environ.get('LD_PRELOAD', ''))",
            str(marker)]
    data = native.scene_bytes(native_args(), host)
    env = dict(os.environ, XDG_RUNTIME_DIR=str(tmp_path), WAYLAND_DISPLAY="nowhere",
               SYNCRAIN_LD_PRELOAD="/usr/lib/libgtk4-layer-shell.so.0")
    env.pop("LD_PRELOAD", None)
    done = run_with_scene(native_wallpaper, data, env)
    assert done.returncode == 0, done.stderr
    assert "no Wayland display" in done.stderr and "the GTK host takes over" in done.stderr, done.stderr
    assert marker.read_text() == "/usr/lib/libgtk4-layer-shell.so.0"


def test_asked_for_by_name_it_says_why_it_cannot_draw(native_wallpaper, root, tmp_path):
    """`syncrain --host native` names no GTK host in the scene: the program says why it cannot draw
    and stops, where `--host auto` would hand over."""
    env = dict(os.environ, XDG_RUNTIME_DIR=str(tmp_path), WAYLAND_DISPLAY="nowhere", GDK_BACKEND="wayland",
               PYTHONPATH=str(root))
    env.pop("DISPLAY", None)
    done = subprocess.run([sys.executable, "-m", "syncrain", "--host", "native"], cwd=root, env=env,
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 1 and "no display" in done.stderr, done.stderr
    assert "GTK host" not in done.stderr, done.stderr


def test_a_native_program_that_cannot_start_leaves_no_scene_behind(monkeypatch):
    """When the exec fails, the GTK host draws instead, and the scene's memfd (the textures' pixels,
    19 MiB and more) must not stay open in it."""
    def refuse(*_):
        raise OSError(8, "Exec format error")
    monkeypatch.setattr(native.os, "execve", refuse)
    before = sorted(os.listdir("/proc/self/fd"))
    why = native.run(native_args(), [], "/nonexistent/syncrain-wallpaper")
    assert why == "the native wallpaper did not start ([Errno 8] Exec format error)"
    assert sorted(os.listdir("/proc/self/fd")) == before


def test_the_launcher_hands_it_everything_the_gtk_host_would_use():
    """The scene carries the GTK host's own sources: every shader, every texture at its size, and
    every uniform static_uniforms lists, each value exactly."""
    from syncrain.renderer import STATIC_TEXTURES, shader_bodies, static_uniforms, texture_sources
    args = native_args("--rainbow", "all", "--spin", "240", "--speed", "0.5", "--glow", "0", "--snow", "off",
                       "--hieroglyphs", "0.4", "--bg-gain", "0.7")
    data = native.scene_bytes(args, ["python3", "-m", "syncrain", "--host", "gtk"])
    head, _, body = data.partition(b"\nend\n")
    lines = head.decode().splitlines()
    assert lines[0] == native.SCENE_CONTRACT
    r = Renderer(theme=args.theme, channel=args.channel, rainbow="all", spin=240.0, speed=0.5, glow=0.0, snow="off",
                 hieroglyphs=0.4, bg_gain=0.7)
    sources, _, _ = texture_sources(r)
    for name, src in shader_bodies().items():
        line = next(x for x in lines if x.startswith(f"shader {name} "))
        off, n = map(int, line.split()[2:])
        assert body[off:off + n].decode() == src
    for name in STATIC_TEXTURES:
        line = next(x for x in lines if x.startswith(f"texture {name} "))
        _, _, w, h, kind, off, n = line.split()
        assert (int(w), int(h), kind) == sources[name][:3] and body[int(off):int(off) + int(n)] == sources[name][3]
    uniforms = [x.split(" ", 4)[1:] for x in lines if x.startswith("uniform ")]
    want = static_uniforms(r)
    assert len(uniforms) == len(want)
    for (program, name, kind, values), (p, n, k, v) in zip(want, uniforms):
        assert (program, name, kind) == (p, n, k)
        got = [int(x) if k in ("i", "ui") else float.fromhex(x) for x in v.split()]
        assert got == [int(x) if k in ("i", "ui") else float(x) for x in values], name
    fallback = next(x for x in lines if x.startswith("fallback "))
    off, n = map(int, fallback.split()[1:])
    assert body[off:off + n] == b"python3\0-m\0syncrain\0--host\0gtk\0"


@pytest.mark.parametrize("argv, expected", [
    (["python3", "-m", "syncrain", "--channel", "x"], ["python3", "-m", "syncrain"]),
    (["/nix/store/p/bin/python3.14", "/nix/store/s/bin/.syncrain-wrapped", "--channel", "x"],
     ["/nix/store/p/bin/python3.14", "/nix/store/s/bin/.syncrain-wrapped"]),
])
def test_the_gtk_host_is_started_the_way_this_process_was(monkeypatch, argv, expected):
    monkeypatch.setattr(sys, "orig_argv", argv, raising=False)
    monkeypatch.setattr(sys, "argv", ["whatever", "--channel", "x"])
    assert native.gtk_host_command(["--channel", "x"]) == expected + ["--channel", "x", "--host", "gtk"]


def test_gtk4_layer_shell_stays_out_of_the_native_process(monkeypatch):
    monkeypatch.setenv("LD_PRELOAD", "/usr/lib/libgtk4-layer-shell.so.0 /opt/other.so")
    env = native.environment()
    assert env["LD_PRELOAD"] == "/opt/other.so"
    assert env["SYNCRAIN_LD_PRELOAD"] == "/usr/lib/libgtk4-layer-shell.so.0 /opt/other.so"
    monkeypatch.setenv("LD_PRELOAD", "/nix/store/x-gtk4-layer-shell-1.3.0/lib/libgtk4-layer-shell.so")
    assert "LD_PRELOAD" not in native.environment()
