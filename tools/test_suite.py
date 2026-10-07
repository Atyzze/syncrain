#!/usr/bin/env python3
"""Run syncrain's test lanes.

    python3 tools/test_suite.py                       # every lane; missing environments skip
    python3 tools/test_suite.py --lane quick          # unit + contract: seconds, no display
    python3 tools/test_suite.py --lane all --require-all   # what the release runs

Lanes: unit (no display), contract (the project's rules), render (the app on an X display, a
private Xvfb by default), wayland (the wallpaper layer in a headless Sway), kwin (the wallpaper on
a headless KWin 6, Plasma's compositor: covered screens and frame spacing), browser (the web page
in Chromium, and against the app), nix (the package and the services, evaluated and built).
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
    "browser": ["tests/browser"],
    "kwin": ["tests/kwin"],
    "nix": ["tests/nix"],
    "quick": ["tests/unit", "tests/contract"],
    "all": ["tests/unit", "tests/contract", "tests/render", "tests/wayland", "tests/kwin", "tests/browser",
            "tests/nix"],
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
    # The lane leads its own session, so a stopped run takes everything it started with it.
    lane = subprocess.Popen(command, cwd=ROOT, env=env, start_new_session=True)

    def stop(signum, _frame):
        try:
            os.killpg(lane.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        raise SystemExit(128 + signum)
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stop)
    return lane.wait()


if __name__ == "__main__":
    raise SystemExit(main())
