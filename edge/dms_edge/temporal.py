"""Temporal consistency filter: a condition only counts once it has held for
a minimum time, so no single frame can raise an alert (SRS 2.4, FR3.3)."""
from __future__ import annotations


class Sustained:
    def __init__(self, grace_sec: float = 0.3):
        # Brief dropouts (a blink of good frames, one missed detection) shorter
        # than grace_sec do not reset the timer.
        self.grace = grace_sec
        self.since: float | None = None
        self.last_true: float | None = None

    def update(self, active: bool, now: float) -> float:
        """Feed one observation; returns how long the condition has held (seconds)."""
        if active:
            if self.since is None:
                self.since = now
            self.last_true = now
        elif self.since is not None and now - (self.last_true or now) > self.grace:
            self.since = None
            self.last_true = None
        return 0.0 if self.since is None else now - self.since

    def reset(self):
        self.since = None
        self.last_true = None
