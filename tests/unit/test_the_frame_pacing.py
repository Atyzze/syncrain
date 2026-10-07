"""Frames on whole refreshes, each drawn for the refresh it is shown on (syncrain/pacing.py).

Build 4 asked for a frame every 33 ms from a timer, which drifts past the screen's refresh. The
pacer's promise: frames N refreshes apart, N the fewest that keep the rate under the cap, whatever a
frame takes to draw within its slack; a frame that is late takes the soonest refresh it can make.
"""
from __future__ import annotations

import math
import random

from syncrain.pacing import Pacer, spacing, steady

R60 = 1e6 / 60
V0 = 5_000_000.0           # a refresh GTK knows about (monotonic microseconds)


def on_grid(t, refresh=R60, v0=V0):
    k = (t - v0) / refresh
    return abs(k - round(k)) < 1e-6


def test_the_cap_becomes_a_whole_number_of_refreshes():
    p = Pacer(30)
    assert p.step(1e6 / 60) == 2
    assert p.step(1e6 / 59.94) == 2, "a 59.94 Hz screen still draws every 2nd refresh"
    assert p.step(1e6 / 120) == 4
    assert p.step(1e6 / 144) == 5, "28.8 fps: never above the cap"
    assert p.step(1e6 / 165) == 6
    assert p.step(1e6 / 75) == 3
    assert [Pacer(f).step(R60) for f in (60, 20, 15, 10)] == [1, 3, 4, 6]
    assert Pacer(240).step(R60) == 1, "a cap above the refresh rate draws every refresh"


def run(pacer, frames, refresh=R60, late=(0, 4000), seed=5, grid_jitter=True):
    """Drive the pacer as the app does: ask at the due time (a timer fires late by up to late[1] us
    and drawing takes some of that), then plan the next frame. Returns the targets."""
    rnd = random.Random(seed)
    now = V0 + 3000
    delay, target = pacer.plan(now, refresh, V0)
    targets = [target]
    for _ in range(frames):
        now += delay + rnd.uniform(*late)
        vblank = V0 + refresh * (int((now - V0) / refresh) + (1 if grid_jitter else 0))   # GTK: next refresh
        delay, target = pacer.plan(now, refresh, vblank)
        targets.append(target)
    return targets


def test_frames_land_every_nth_refresh_whatever_a_frame_takes_within_its_slack():
    targets = run(Pacer(30), 500)
    assert all(on_grid(t) for t in targets)
    assert set(spacing(targets, R60)) == {2}
    for fps, n, hz in ((20, 3, 60), (30, 5, 144), (15, 8, 120)):
        r = 1e6 / hz
        assert set(spacing(run(Pacer(fps), 300, refresh=r), r)) == {n}, (fps, hz)


def test_the_first_frame_on_a_known_grid_takes_the_soonest_refresh_it_can_make():
    p = Pacer(30)
    now = V0 + 1000
    delay, target = p.plan(now, R60, V0)
    assert on_grid(target) and target - p.lead(R60) >= now
    assert target - R60 - p.lead(R60) < now, "not a refresh later than it has to be"
    assert delay == target - p.lead(R60) - now


def test_a_late_frame_moves_to_the_soonest_refresh_and_the_steps_go_on_from_there():
    p = Pacer(30)
    _, t1 = p.plan(V0 + 1000, R60, V0)
    late = t1 + 50_000                              # this frame was drawn 50 ms after its refresh
    _, t2 = p.plan(late, R60, V0)
    assert on_grid(t2) and t2 - p.lead(R60) >= late and t2 - R60 - p.lead(R60) < late
    _, t3 = p.plan(t2 - p.lead(R60) + 2000, R60, V0)
    assert abs(t3 - t2 - 2 * R60) < 1e-3


def test_a_rounded_refresh_interval_does_not_drift_off_the_screen_s_grid():
    true = 1e6 / 59.951                           # what the screen does
    told = 16680.0                                 # what GTK's rounded interval says
    p = Pacer(30)
    now = V0 + 1000
    delay, target = p.plan(now, told, V0)
    for _ in range(2000):                          # a minute at 30 fps
        now += delay + 1500
        k = int((now - V0) / true) + 1
        delay, target = p.plan(now, told, V0 + k * true)
    k = (target - V0) / true
    assert abs(k - round(k)) * true < 1500, "the targets stay within a fraction of a refresh of the real ones"


def test_without_a_known_refresh_it_falls_back_to_the_timer_period():
    p = Pacer(30)
    assert p.plan(V0, 0, 0) == (1e6 / 30, None) and p.target is None
    p.plan(V0, R60, V0)
    assert p.target is not None
    p.restart()
    assert p.target is None


def test_spacing_counts_whole_refreshes():
    assert spacing([0, 33_333, 66_667, 116_667, 133_333], R60) == [2, 2, 3, 1]
    assert spacing([0, 33_333], 0) == []


def test_steady_counts_frames_shown_the_usual_delay_after_the_moment_they_were_drawn_for():
    assert steady([16_700] * 30) == 1.0, "a constant delay (a card a refresh behind) is steady"
    assert steady([100, 300, -200, 900, 16_800]) == 0.8, "one frame a refresh late"
    timer = [i * 16_667 / 20 for i in range(20)]   # drawn whenever a timer fired: anywhere in a refresh
    assert steady(timer) < 0.3
    assert steady([]) == 0.0


def compositor(target, lead, paint, margin, refresh, v0=V0):
    """When a compositor shows a frame asked for `lead` before `target`: at the first refresh whose
    deadline (`margin` before it) the commit, `paint` after the request, still makes."""
    commit = target - lead + paint
    k = math.ceil((commit + margin - v0) / refresh)
    return v0 + k * refresh


def on_time_share(fps, hz, paint, margin, jitter, frames=1500, nudge=True, seed=3):
    """Run the pacer against that compositor; the share of the last 500 frames shown on their refresh."""
    rnd = random.Random(seed)
    refresh = 1e6 / hz
    p = Pacer(fps)
    now = V0 + 1000
    pending, hits = [], []
    delay, target = p.plan(now, refresh, V0)
    for _ in range(frames):
        now += delay                                          # the frame is asked for, and drawn
        t, lead = target, p.lead(refresh)
        shown = compositor(t, lead, paint + rnd.uniform(-jitter, jitter), margin, refresh)
        pending.append((t, shown))
        if len(pending) > 2:                                  # GTK learns it two frames later
            t_old, shown_old = pending.pop(0)
            if nudge:
                p.shown(t_old, shown_old, refresh)
            hits.append(abs(shown_old - t_old) < refresh / 2)
        now += paint
        k = math.ceil((now - V0) / refresh)
        delay, target = p.plan(now, refresh, V0 + k * refresh)
    return sum(hits[-500:]) / 500


def test_the_lead_finds_the_window_a_fast_screen_leaves():
    """At 144 Hz a frame has 6.9 ms in which to arrive. A slow drawer (6 ms, the sandbox) arrives late
    with the first lead and a fast one (1 ms, a desktop card) close to early; both settle on time."""
    for hz in (144, 240):
        for paint, margin in ((6000, 4000), (1000, 3000), (1000, 1000), (9000, 2000), (3000, 5000)):
            assert on_time_share(30, hz, paint, margin, jitter=800) >= 0.95, (hz, paint, margin)
    assert on_time_share(30, 144, 6000, 4000, jitter=800, nudge=False) < 0.6, "the fixed lead missed here"
    assert on_time_share(30, 60, 1000, 3000, jitter=800) == 1.0


def test_a_nudge_moves_the_lead_by_half_a_millisecond_once_per_lesson():
    p = Pacer(30)
    _, t1 = p.plan(V0 + 1000, R60, V0)
    base = p.lead(R60)
    _, t2 = p.plan(t1 - base + 2000, R60, V0)        # GTK reports a frame after the next is planned
    p.shown(t1, t1 + R60, R60)                       # shown a refresh late: ask earlier
    assert p.lead(R60) == base + 500
    p.shown(t2, t2 + R60, R60)                       # planned before the move: says nothing new
    assert p.lead(R60) == base + 500
    _, t3 = p.plan(t2 - p.lead(R60) + 2000, R60, V0)
    p.shown(t3, t3 - R60, R60)                       # shown a refresh early: ask later
    assert p.lead(R60) == base
    p.shown(t3 + 10 * R60, t3 + 10 * R60, R60)       # on time: nothing moves
    assert p.lead(R60) == base
    p.shown(t3 + 20 * R60, t3 + 20 * R60 + 600e6, R60)   # shown ten minutes on: the screen was locked
    assert p.lead(R60) == base, "a frame held back by a locked screen is not a late frame"


def test_the_lead_stays_within_two_refreshes_and_never_below_two_milliseconds():
    late, early = Pacer(30), Pacer(30)
    for k in range(200):
        for p, off in ((late, R60), (early, -R60)):
            p.plan(V0 + k * 100_000, R60, V0)
            p.shown(p.target, p.target + off, R60)
    assert late.lead(R60) == 2 * R60 + 6000
    assert early.lead(R60) == 2000
