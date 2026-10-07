"""When each screen's next frame is drawn, and for which moment.

Build 4 asked for a frame every 33 ms from a GLib timer. A timer is not the screen's refresh: the
two drift past each other, so now and then a frame was shown one refresh earlier or later than the
others while its picture was drawn for the moment the timer fired, and the motion stumbled. Here a
frame is drawn on whole refreshes (every Nth one, N the smallest whole number that keeps the rate
at or under --fps) and for the refresh it is shown on, so the rain and the snow move by the same
step every frame. GTK knows the refresh grid from the compositor's presentation feedback
(GdkFrameClock.get_refresh_info). Where it does not (X11 without a compositor, the first frame on a
screen), the next frame is simply asked for one period later, as before.

How long before its refresh a frame must be asked for depends on the machine: the frame has to be
committed after the compositor's deadline for the refresh before (or it is shown a refresh early)
and before its deadline for the refresh meant (or it is shown a refresh late). That window is one
refresh wide, 16.7 ms at 60 Hz but only 6.9 ms at 144 Hz, and where it lies depends on how long the
drawing takes and on the compositor. So the lead starts in the middle for a fast machine and moves
by NUDGE_US whenever GTK reports a frame shown a refresh early or late (`Pacer.shown`).
"""
from __future__ import annotations

import math

#: Microseconds before its refresh that a frame is asked for, beyond half a refresh. GTK's paint (the
#: six passes, GTK's own frame, the commit) and the compositor's deadline before the refresh both have
#: to fit, with room either side, so that a frame that takes a little longer, or a compositor that
#: starts a little earlier, never moves a frame to the next refresh.
LEAD_US = 6000

#: A frame rate within this share of a refresh's multiple still counts as that multiple: a 60 Hz
#: screen at the default 30 fps cap draws every 2nd refresh, not every 3rd.
GRACE = 0.05

#: A frame shown more than this many refreshes from its target says nothing about the lead: the screen
#: was locked or off, and GTK learns when the frame was shown only when it comes back.
MAX_MISS = 2

#: How far the lead moves after a frame is shown a refresh early or late, and its bounds: never less
#: than MIN_LEAD_US, never more than two refreshes plus LEAD_US (room for a slow drawer on a fast
#: screen; a machine too slow even then shows every frame a refresh late, which keeps the steps even,
#: and a frame shown early always pulls the lead back).
NUDGE_US = 500
MIN_LEAD_US = 2000


class Pacer:
    """One screen's frame schedule. Times are GLib monotonic microseconds, as GTK's frame clock gives them."""

    def __init__(self, fps: float):
        self.period = 1e6 / max(1.0, fps)
        self.target = None          # the refresh the frame being asked for is drawn for, when known
        self.shift = 0.0            # microseconds added to the lead by what GTK reported
        self.settled_after = None   # frames drawn for refreshes up to this one were planned before the last nudge

    def step(self, refresh: float) -> int:
        """Refreshes from one frame to the next: the fewest that keep the rate at or under the cap."""
        return max(1, math.ceil(self.period / refresh - GRACE))

    def lead(self, refresh: float) -> float:
        """How long before its refresh a frame is asked for: half a refresh and LEAD_US, moved by what
        GTK reported about earlier frames, within MIN_LEAD_US and two refreshes plus LEAD_US."""
        return min(max(refresh / 2 + LEAD_US + self.shift, MIN_LEAD_US), 2 * refresh + LEAD_US)

    def shown(self, target: float, presented: float, refresh: float) -> None:
        """A frame drawn for the refresh `target` was shown at `presented` (GTK's frame timings).

        Shown a refresh late, the next frames are asked for a little earlier; a refresh early, a
        little later. Frames planned before the last move say nothing about the new lead and are not
        counted, so one slow moment moves the lead once, not once for every frame already asked for.
        """
        if refresh <= 0 or (self.settled_after is not None and target <= self.settled_after):
            return
        off = round((presented - target) / refresh)
        if off == 0 or abs(off) > MAX_MISS:
            return
        base = refresh / 2 + LEAD_US
        moved = self.shift + (NUDGE_US if off > 0 else -NUDGE_US)
        self.shift = min(max(moved, MIN_LEAD_US - base), 1.5 * refresh)
        self.settled_after = self.target

    def plan(self, now: float, refresh: float, vblank: float):
        """After a frame: (microseconds until the next is asked for, the refresh it is drawn for or None).

        refresh is the interval between refreshes and vblank any refresh on the grid (both 0 when GTK
        does not know them). The next target is the last one plus whole steps, put back onto the grid;
        a frame that came too late for it (a slow frame, a screen that was covered) takes the soonest
        refresh it can still make, and the steps go on from there.
        """
        if refresh <= 0 or vblank <= 0:
            self.target = None
            return self.period, None
        lead = self.lead(refresh)
        earliest = vblank + math.ceil((now + lead - vblank) / refresh) * refresh
        target = None
        if self.target is not None:
            target = self.target + self.step(refresh) * refresh
            target = vblank + round((target - vblank) / refresh) * refresh
        if target is None or target < earliest:
            target = earliest
        self.target = target
        return target - lead - now, target

    def restart(self):
        """Forget the cadence (the screen was hidden, or its refresh changed): the next frame is drawn now."""
        self.target = None


def spacing(presented, refresh: float):
    """Refreshes between consecutive presentation times (microseconds), rounded to whole refreshes."""
    return [round((b - a) / refresh) for a, b in zip(presented, presented[1:]) if refresh > 0]


#: How far from the usual delay a frame may be shown and still count as steady (microseconds).
STEADY_US = 2000


def steady(delays) -> float:
    """The share of frames shown within STEADY_US of the usual delay between the moment a frame was
    drawn for and the moment it was shown. Near 1, the motion advances by the same step every frame;
    a frame drawn for the moment a timer fired is shown anywhere up to a refresh later, so its share
    is low however evenly the frames are spaced."""
    if not delays:
        return 0.0
    usual = sorted(delays)[len(delays) // 2]
    return sum(1 for d in delays if abs(d - usual) <= STEADY_US) / len(delays)
