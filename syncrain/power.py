"""`syncrain --power-sweep`: what syncrain costs this machine's graphics card, setting by setting.

The operator's question after build 3: how far can the power come down without giving up the
smoothness. Only their card can answer it, so this measures it there. Build 4's sweep answered the
first half on their card (the watts follow the frames, not the pixels; GTK's OpenGL renderer costs
half of its Vulkan one; a covered wallpaper still drew at full rate under KWin). Build 5's sweep
measures what build 5 changed: the desktop with no syncrain; syncrain as installed (frames on the
screen's refresh); build 4's frame timer, for comparison; 20 and 15 frames a second; and behind a
maximized and a full-screen window, where it should stop drawing. Each phase runs a real wallpaper
for a while, lets the card settle, and averages its power draw from the driver: `nvidia-smi` on
NVIDIA, the amdgpu power sensor on AMD (or any command named by SYNCRAIN_POWER_COMMAND that prints
watts). The table goes to the terminal and a JSON file to the home folder, for sending.
"""
from __future__ import annotations

import contextlib
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import build

# ---------------------------------------------------------------- power sources


class NvidiaSmi:
    """`nvidia-smi` in its streaming mode: one line a second per card, no process per sample."""

    name = "nvidia-smi"
    FIELDS = ("power.draw", "pstate", "clocks.gr", "clocks.mem", "utilization.gpu")

    def __init__(self, exe: str):
        self.exe = exe
        self.latest: dict[str, dict] = {}
        self.proc = None
        self.lock = threading.Lock()

    def describe(self) -> str:
        try:
            out = subprocess.run([self.exe, "--query-gpu=name,driver_version", "--format=csv,noheader"],
                                 capture_output=True, text=True, timeout=10).stdout.strip()
            return out.replace("\n", "; ") or "NVIDIA"
        except (OSError, subprocess.SubprocessError):
            return "NVIDIA"

    def start(self) -> None:
        self.proc = subprocess.Popen(
            [self.exe, "--query-gpu=index," + ",".join(self.FIELDS), "--format=csv,noheader,nounits", "-lms", "1000"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        for line in self.proc.stdout:
            parsed = parse_nvidia_line(line)
            if parsed:
                with self.lock:
                    self.latest[parsed["index"]] = parsed

    def sample(self):
        with self.lock:
            cards = list(self.latest.values())
        if not cards:
            return None
        return sum(c["watts"] for c in cards), {"pstate": "/".join(c["pstate"] for c in cards),
                                                "clocks": "/".join(f"{c['gr']}+{c['mem']} MHz" for c in cards),
                                                "busy": "/".join(f"{c['util']}%" for c in cards)}

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def parse_nvidia_line(line: str):
    """'0, 38.21, P2, 1590, 7001, 3' -> a dict, or None for anything else (headers, '[N/A]')."""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != 6:
        return None
    try:
        return {"index": parts[0], "watts": float(parts[1]), "pstate": parts[2], "gr": parts[3], "mem": parts[4],
                "util": parts[5]}
    except ValueError:
        return None


class Hwmon:
    """The amdgpu power sensor in sysfs (microwatts), and how busy the card says it is."""

    name = "amdgpu hwmon"

    def __init__(self, files: list[str]):
        self.files = files

    def describe(self) -> str:
        return ", ".join(sorted({f.split("/device/")[0].split("/")[-1] for f in self.files})) + " (amdgpu)"

    def start(self) -> None:
        pass

    def sample(self):
        total, busy = 0.0, []
        for f in self.files:
            try:
                total += int(Path(f).read_text().strip()) / 1e6
            except (OSError, ValueError):
                return None
            busy_file = Path(f.split("/hwmon/")[0]) / "gpu_busy_percent"
            if busy_file.is_file():
                busy.append(busy_file.read_text().strip() + "%")
        return total, {"busy": "/".join(busy)} if busy else {}

    def stop(self) -> None:
        pass


class Command:
    """Any command that prints the card's power in watts (SYNCRAIN_POWER_COMMAND)."""

    name = "command"

    def __init__(self, command: str):
        self.command = command

    def describe(self) -> str:
        return f"SYNCRAIN_POWER_COMMAND={self.command}"

    def start(self) -> None:
        pass

    def sample(self):
        try:
            out = subprocess.run(self.command, shell=True, capture_output=True, text=True, timeout=5).stdout
            return float(out.strip().split()[0]), {}
        except (OSError, subprocess.SubprocessError, ValueError, IndexError):
            return None

    def stop(self) -> None:
        pass


def detect_power_source(sysfs: str = "/sys/class/drm"):
    command = os.environ.get("SYNCRAIN_POWER_COMMAND")
    if command:
        return Command(command)
    exe = shutil.which("nvidia-smi")
    if exe:
        probe = subprocess.run([exe, "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=10)
        if probe.returncode == 0 and re.match(r"^\s*[0-9.]+", probe.stdout):
            return NvidiaSmi(exe)
    files = []
    for hw in sorted(glob.glob(os.path.join(sysfs, "card[0-9]*/device/hwmon/hwmon*"))):
        for name in ("power1_average", "power1_input"):
            if os.path.isfile(os.path.join(hw, name)):
                files.append(os.path.join(hw, name))
                break
    return Hwmon(files) if files else None


# ---------------------------------------------------------------- other wallpapers


SWEEP_FLAGS = ("--power-sweep", "--benchmark", "--diagnose", "--build", "--version", "--list-themes", "--screenshot",
               "--record", "--help", "--probe")


def running_wallpapers(proc_dir: str = "/proc", exclude: set[int] | None = None) -> list[tuple[int, str]]:
    """Other syncrain processes that draw a wallpaper or a window (not tools like this one)."""
    exclude = exclude or set()
    found = []
    for path in glob.glob(os.path.join(proc_dir, "[0-9]*", "cmdline")):
        pid = int(path.split("/")[-2])
        if pid in exclude:
            continue
        try:
            argv = Path(path).read_bytes().split(b"\0")
        except OSError:
            continue
        args = [a.decode(errors="replace") for a in argv if a]
        if is_syncrain_command(args) and not any(flag in args for flag in SWEEP_FLAGS):
            found.append((pid, " ".join(args)))
    return found


def is_syncrain_command(args: list[str]) -> bool:
    """python -m syncrain (the installer's launcher execs this), the Nix package's wrapped script, or
    the native wallpaper that either replaces itself with (syncrain/native.py)."""
    if not args:
        return False
    if any(a == "syncrain" and i > 0 and args[i - 1] == "-m" for i, a in enumerate(args)):
        return True
    names = [os.path.basename(a) for a in args[:2]]
    return names[0] in (".syncrain-wrapped", "syncrain-wallpaper") or (
        names[0].startswith("python") and len(names) > 1 and names[1] in ("syncrain", ".syncrain-wrapped"))


# ---------------------------------------------------------------- the sweep


def phases(seconds: int) -> list[dict]:
    """What the sweep measures, in order. `args` are added to the wallpaper's own options; `cover`
    puts syncrain.cover's windows over every screen (full-screen, or maximized)."""
    return [
        {"name": "nothing (your desktop alone)", "child": False},
        {"name": "as installed (30 fps)", "args": []},
        {"name": "the Python and GTK host", "args": ["--host", "gtk"]},
        {"name": "build 4's frame timer", "args": ["--pacing", "timer"]},
        {"name": "--fps 20", "args": ["--fps", "20"]},
        {"name": "--fps 15", "args": ["--fps", "15"]},
        {"name": "behind a maximized window", "args": [], "cover": "maximized"},
        {"name": "behind a full-screen window", "args": [], "cover": "fullscreen"},
    ]


def cover_warning(plan: list[dict], seconds: int) -> str | None:
    """Said before the sweep starts: in the phases with a covering window, every screen goes black."""
    covering = [n for n, phase in enumerate(plan, 1) if phase.get("cover")]
    if not covering:
        return None
    if covering == list(range(len(plan) - len(covering) + 1, len(plan) + 1)):
        which = "the last phase" if len(covering) == 1 else \
            f"the last {({2: 'two', 3: 'three'}).get(len(covering), len(covering))} phases"
    else:
        which = "phases " + ", ".join(str(n) for n in covering)
    names = ", ".join(plan[n - 1]["name"] for n in covering)
    return (f"Warning: in {which} ({names}) a black window covers every screen, so all your screens go black for "
            f"about {len(covering) * (seconds + 3)} s. That is the test, not a fault: they come back by themselves "
            "when the sweep ends. To get them back sooner, close the black windows (Alt+F4) or press Ctrl+C here.")


@contextlib.contextmanager
def interrupted_by_hangup():
    """While the sweep runs, a closed terminal (SIGHUP) or `kill` (SIGTERM) stops it as Ctrl+C does:
    its wallpaper and its black covering windows are stopped too, rather than left on the screens."""
    def interrupt(signum, frame):
        raise KeyboardInterrupt

    before = {sig: signal.signal(sig, interrupt) for sig in (signal.SIGHUP, signal.SIGTERM)}
    try:
        yield
    finally:
        for sig, handler in before.items():
            signal.signal(sig, handler)


#: The wallpaper options a sweep passes on to every phase (the rest are the phase's own).
PASS_ON = ("theme", "channel", "logo", "background", "mask", "bg_gamma", "bg_gain", "rainbow", "spin", "drift",
           "layer", "scale", "fps", "pause_under", "host")


def base_args(args) -> list[str]:
    out = []
    for key in PASS_ON:
        value = getattr(args, key, None)
        default = {"theme": "nixos", "channel": "public", "scale": 1.0, "fps": 30.0, "pause_under": "maximized",
                   "host": "auto"}.get(key)
        if value is not None and value != default:
            out += ["--" + key.replace("_", "-"), str(value)]
    return out


class Child:
    """A wallpaper (or the cover) in its own process, with its output read as it comes."""

    def __init__(self, argv, env):
        self.lines: list[str] = []
        self.started = threading.Event()
        self.proc = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                     start_new_session=True)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            self.lines.append(line.rstrip("\n"))
            if line.startswith("syncrain build") or line.startswith("syncrain cover:"):
                self.started.set()

    REPORT = re.compile(r"syncrain: ([0-9.]+) fps at (\d+x\d+) \(area (\d+)\)"
                        r"(?:, spacing (\d+) refresh(?:es)? (\d+)%, steady (\d+)%(?:, lead ([0-9.]+) ms)?)?")

    def fps_since(self, index: int) -> float | None:
        """Frames a second over all screens, from the wallpaper's own reports after line `index`."""
        reports: dict[str, list[float]] = {}
        for line in self.lines[index:]:
            m = self.REPORT.match(line)
            if m:
                reports.setdefault(m.group(3), []).append(float(m.group(1)))
        if not reports:
            return 0.0 if self.started.is_set() else None
        return sum(sum(v) / len(v) for v in reports.values())

    def timing_since(self, index: int) -> dict:
        """The frame timing the wallpaper reported after line `index`, averaged over its reports and
        screens: {"spacing": "2", "even": 99.0, "steady": 98.0, "lead_ms": 14.3}, or {} when it
        reported none ("lead_ms" only when the reports carry it)."""
        steps, even, calm, lead = set(), [], [], []
        for line in self.lines[index:]:
            m = self.REPORT.match(line)
            if m and m.group(4):
                steps.add(m.group(4))
                even.append(int(m.group(5)))
                calm.append(int(m.group(6)))
                if m.group(7):
                    lead.append(float(m.group(7)))
        if not even:
            return {}
        out = {"spacing": "/".join(sorted(steps)), "even": round(sum(even) / len(even), 1),
               "steady": round(sum(calm) / len(calm), 1)}
        if lead:
            out["lead_ms"] = round(sum(lead) / len(lead), 1)
        return out

    def cpu_seconds(self) -> float | None:
        """Processor time the wallpaper has used, all its threads, user and system (/proc/<pid>/stat)."""
        try:
            fields = Path(f"/proc/{self.proc.pid}/stat").read_text().rsplit(")", 1)[1].split()
            return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")
        except (OSError, IndexError, ValueError):
            return None

    def resident_mib(self) -> float | None:
        """The wallpaper's resident memory now (VmRSS), in MiB."""
        try:
            for line in Path(f"/proc/{self.proc.pid}/status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
        except (OSError, IndexError, ValueError):
            pass
        return None

    def stop(self):
        if self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait(timeout=5)


def child_env(extra: dict | None = None) -> dict:
    env = dict(os.environ, SYNCRAIN_DEBUG_FPS="2", PYTHONUNBUFFERED="1")
    env.pop("SYNCRAIN_REEXEC", None)
    env.update(extra or {})
    return env


def run_sweep(args) -> int:
    seconds = max(4, int(args.sweep_seconds))
    settle = min(8, seconds // 3)
    print(f"{build.describe()} --power-sweep")
    others = running_wallpapers(exclude={os.getpid(), os.getppid()})
    if others:
        print("another syncrain is running, so the sweep would measure two at once:")
        for pid, cmd in others:
            print(f"  pid {pid}: {cmd}")
        print("Stop it first (`systemctl --user stop syncrain` for the autostart service, or Ctrl+C where it "
              "runs), then run the sweep again.")
        return 1
    source = detect_power_source()
    if source is None:
        print("This machine does not tell programs the graphics card's power: no working nvidia-smi and no "
              "amdgpu power sensor. `syncrain --benchmark` still shows what each pass costs the card.")
        return 1
    plan = phases(seconds)
    print(f"power from {source.name}: {source.describe()}")
    print(f"{len(plan)} phases of {seconds} s (the first {settle} s of each let the card settle), about "
          f"{len(plan) * (seconds + 3) // 60 + 1} minutes. For a fair 'nothing', give Plasma a still picture as "
          "its wallpaper first. Ctrl+C stops early and still prints what was measured.")
    warning = cover_warning(plan, seconds)
    if warning:
        print(warning)
    source.start()
    results = []
    child = cover = None
    interrupted = False
    with interrupted_by_hangup():
        try:
            for n, phase in enumerate(plan, 1):
                label = phase["name"]
                black = f" (every screen goes black now, for about {seconds} s)" if phase.get("cover") else ""
                print(f"[{n}/{len(plan)}] {label} ...{black}", flush=True)
                mark = 0
                if phase.get("child", True):
                    argv = [sys.executable, "-m", "syncrain", *base_args(args), *phase["args"]]
                    child = Child(argv, child_env(phase.get("env")))
                    if not child.started.wait(timeout=90):
                        child.stop()
                        print("   the wallpaper did not start; its output:\n   " + "\n   ".join(child.lines[-8:]))
                        results.append({"phase": label, "error": "did not start"})
                        child = None
                        continue
                    if phase.get("cover"):
                        how = ["--maximized"] if phase["cover"] == "maximized" else []
                        cover = Child([sys.executable, "-m", "syncrain.cover", *how], child_env())
                        cover.started.wait(timeout=60)
                samples, details = [], []
                start = time.monotonic()
                cpu0 = None
                while time.monotonic() - start < seconds:
                    time.sleep(1.0)
                    if child and time.monotonic() - start >= settle and mark == 0:
                        mark = len(child.lines)
                        cpu0, cpu_t0 = child.cpu_seconds(), time.monotonic()
                    reading = source.sample()
                    if reading and time.monotonic() - start >= settle:
                        samples.append(reading[0])
                        details.append(reading[1])
                row = {"phase": label, "watts": sum(samples) / len(samples) if samples else None,
                       "samples": samples, "detail": details[-1] if details else {}}
                if child:
                    cpu1 = child.cpu_seconds()
                    if cpu0 is not None and cpu1 is not None and time.monotonic() > cpu_t0:
                        row["cpu_percent"] = round(100.0 * (cpu1 - cpu0) / (time.monotonic() - cpu_t0), 2)
                    rss = child.resident_mib()
                    if rss is not None:
                        row["resident_mib"] = round(rss, 1)
                    row["fps"] = child.fps_since(mark)
                    row["timing"] = child.timing_since(mark)
                    row["startup"] = next((line for line in child.lines if line.startswith("syncrain build")), "")
                    row["pause"] = next((line for line in child.lines if "drawing pauses" in line
                                         or "drawing goes on under" in line), "")
                results.append(row)
                for c in (cover, child):
                    if c:
                        c.stop()
                child = cover = None
        except KeyboardInterrupt:
            interrupted = True
        finally:
            for c in (cover, child):
                if c:
                    c.stop()
            source.stop()
    report(results, source, interrupted)
    return 0 if not interrupted else 130


def drawn_by(startup: str) -> str:
    """What drew a phase, from its startup line: "native", or GTK's renderer ("gl", "vulkan")."""
    if ", native wallpaper," in startup:
        return "native"
    found = re.search(r"GTK renderer (\S+?),", startup)
    return found.group(1) if found else ""


def report(results, source, interrupted) -> None:
    idle = next((r["watts"] for r in results if r["phase"].startswith("nothing") and r.get("watts")), None)
    print()
    print(f"{'phase':30s} {'card W':>7s} {'above':>7s} {'frames/s':>9s} {'even':>5s} {'steady':>6s} "
          f"{'cpu %':>6s} {'MiB':>6s} {'drawn by':>9s}  card state")
    for r in results:
        w = r.get("watts")
        above = f"{w - idle:+.1f}" if (w is not None and idle is not None and not r["phase"].startswith("nothing")) else ""
        fps = r.get("fps")
        fps_text = "" if fps is None else f"{fps:.1f}"
        timing = r.get("timing") or {}
        even = f"{timing['even']:.0f}%" if timing else ""
        calm = f"{timing['steady']:.0f}%" if timing else ""
        drawn = drawn_by(r.get("startup", ""))
        state = " ".join(f"{k} {v}" for k, v in r.get("detail", {}).items())
        watts = "?" if w is None else f"{w:.1f}"
        cpu = f"{r['cpu_percent']:.1f}" if r.get("cpu_percent") is not None else ""
        mib = f"{r['resident_mib']:.0f}" if r.get("resident_mib") is not None else ""
        print(f"{r['phase']:30s} {watts:>7s} {above:>7s} {fps_text:>9s} {even:>5s} {calm:>6s} "
              f"{cpu:>6s} {mib:>6s} {drawn:>9s}  {r.get('error', state)}")
    print("'above' is the card's power above 'nothing'; frames/s counts every screen together. 'even': frames\n"
          "shown the same number of refreshes apart; 'steady': frames shown the usual delay after the moment\n"
          "they were drawn for. The motion is smooth when both are near 100%. 'cpu %': the wallpaper's processor\n"
          "time as a share of one core (100 is one core kept busy); 'MiB': its resident memory at the end of the\n"
          "phase; 'drawn by': the native wallpaper, or the GTK host with GTK's renderer.")
    pause = next((r["pause"] for r in results if r.get("pause")), "")
    if pause:
        print(pause)
    record = {"contract": "syncrain-power-sweep-1", "build": build.BUILD_NUMBER, "stream": build.stream_id(),
              "source": source.describe(), "when_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "interrupted": interrupted, "phases": results}
    out = Path.home() / f"syncrain-power-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    try:
        out.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
        print(f"\nsaved {out} (send this file)")
    except OSError as e:
        print(f"\ncould not save the results: {e}")
