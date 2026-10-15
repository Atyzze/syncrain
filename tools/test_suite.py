#!/usr/bin/env python3
"""Run syncrain's test lanes.

    python3 tools/test_suite.py                       # every lane; missing environments skip
    python3 tools/test_suite.py --lane quick          # unit + contract: seconds, no display
    python3 tools/test_suite.py --lane all --require-all   # what the release runs

Lanes: unit (no display), contract (the project's rules), native (the C wallpaper's arithmetic
against Python's, and its build), render (the app on an X display, a
private Xvfb by default), wayland (the wallpaper layer in a headless Sway), kwin (the wallpaper on
a headless KWin 6, Plasma's compositor: covered screens and frame spacing), browser (the web page
in Chromium, and against the app), nix (the package and the services, evaluated and built),
lockscreen (syncrain's lock screen in Plasma's own locker: its frame, its box, a real KWin lock
unlocked through PAM).
`--require-all` turns every "this machine lacks X" skip into a failure, because a lane that skips
on the release machine never ran.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANES = {
    "unit": ["tests/unit"],
    "contract": ["tests/contract"],
    "render": ["tests/render"],
    "wayland": ["tests/wayland"],
    "native": ["tests/native"],
    "browser": ["tests/browser"],
    "kwin": ["tests/kwin"],
    "nix": ["tests/nix"],
    "lockscreen": ["tests/lockscreen"],
    "quick": ["tests/unit", "tests/contract"],
    "all": ["tests/unit", "tests/contract", "tests/native", "tests/render", "tests/wayland", "tests/kwin",
            "tests/browser", "tests/nix", "tests/lockscreen"],
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lane", choices=sorted(LANES), default="all")
    ap.add_argument("--require-all", action="store_true", help="a missing environment fails instead of skipping")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if args.require_all:
        env["SYNCRAIN_REQUIRE_ALL"] = "1"
    command = [sys.executable, "-m", "pytest", "-vv" if args.verbose else "-q", "-rs", *LANES[args.lane]]
    # The lane leads its own session, so a stopped run takes everything it started with it. Stopped,
    # pytest is interrupted first (SIGINT: its teardowns run and stop what each test started, Xvfb,
    # Sway and KWin in sessions of their own included), and only then, after a minute, the whole
    # session is ended.
    # A shell's `cmd &` (the release runs that way) starts it with SIGINT ignored, which pytest would
    # inherit and then never be interrupted: the lane gets the default back.
    lane = subprocess.Popen(command, cwd=ROOT, env=env, start_new_session=True,
                            preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL))

    def signal_lane(sig) -> bool:
        try:
            if sig == signal.SIGINT:
                lane.send_signal(sig)               # pytest alone: it tears down
            else:
                os.killpg(lane.pid, sig)
        except ProcessLookupError:
            return False
        return True

    def stop(signum, _frame):
        for sig, wait in ((signal.SIGINT, 60), (signal.SIGTERM, 10), (signal.SIGKILL, 5)):
            if not signal_lane(sig):
                break
            try:
                lane.wait(timeout=wait)
            except subprocess.TimeoutExpired:
                continue
            signal_lane(signal.SIGTERM)             # whatever the teardowns left behind
            break
        raise SystemExit(128 + signum)
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stop)
    # A test that hangs (a process that never says the line awaited) ends the lane, as a failure,
    # rather than the release waiting for good: "all" takes about 20 minutes here.
    limit = 3600 if args.lane == "all" else 1800
    try:
        return lane.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        print(f"test_suite: the {args.lane} lane ran past {limit // 60} minutes; stopped", file=sys.stderr, flush=True)
        try:
            stop(signal.SIGALRM, None)
        except SystemExit:
            pass
        return 124


if __name__ == "__main__":
    raise SystemExit(main())
