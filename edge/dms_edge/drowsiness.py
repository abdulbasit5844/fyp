"""Eye Aspect Ratio (Soukupová & Čech, 2016) on MediaPipe face-mesh landmarks,
plus fatigue measures over time (yawns, PERCLOS, blink trends, head nods).

EAR = (|p2-p6| + |p3-p5|) / (2 |p1-p4|)
Open eyes sit around 0.25-0.35; closed eyes fall below ~0.2.
"""
from __future__ import annotations

from collections import deque

import numpy as np

# p1..p6 for each eye in MediaPipe's 468-point mesh (outer corner, two upper,
# inner corner, two lower), matching the dlib 68-point ordering.
LEFT_EYE = (33, 160, 158, 133, 153, 144)
RIGHT_EYE = (362, 385, 387, 263, 373, 380)
# Inner-lip points for the mouth aspect ratio (upper, lower, left corner, right corner).
MOUTH = (13, 14, 78, 308)


def eye_aspect_ratio(eye: np.ndarray) -> float:
    """eye: (6, 2) array of p1..p6."""
    p1, p2, p3, p4, p5, p6 = eye
    horizontal = np.linalg.norm(p1 - p4)
    if horizontal < 1e-6:
        return 0.0
    return float((np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)) / (2.0 * horizontal))


def face_ear(points: np.ndarray) -> float:
    """Mean EAR of both eyes from a (N, 2) landmark array."""
    left = eye_aspect_ratio(points[list(LEFT_EYE)])
    right = eye_aspect_ratio(points[list(RIGHT_EYE)])
    return (left + right) / 2.0


def mouth_aspect_ratio(points: np.ndarray) -> float:
    """Inner-lip opening / mouth width. Fallback for when there is no jawOpen blendshape."""
    up, low, left, right = (points[i] for i in MOUTH)
    width = np.linalg.norm(left - right)
    return 0.0 if width < 1e-6 else float(np.linalg.norm(up - low) / width)


# --- Fatigue over time ---
#
# The 2-second closure rule only catches a driver who is already asleep. These
# measures pick up the build-up: frequent yawns, a rising share of time with the
# eyes closed (PERCLOS, the standard research measure), slow blinks, and the
# head dropping while the eyes are shut (a microsleep nod).

YAWN_OPEN, YAWN_CLOSE = 0.5, 0.35  # jawOpen or MAR; hysteresis so one yawn is not split in two
YAWN_MIN_SEC = 1.5  # talking and laughing open the mouth for less than this
YAWN_MAX_SEC = 6.0  # eyes often close during a yawn; past this it is not a yawn any more
YAWN_WINDOW_SEC = 300.0
YAWNS_FOR_FATIGUE = 3  # in five minutes

PERCLOS_WINDOW_SEC = 60.0
PERCLOS_MIN_COVERAGE = 30.0  # seconds of face data in the window before PERCLOS is judged
PERCLOS_WARN, PERCLOS_CLEAR = 0.15, 0.10
MAX_FRAME_GAP = 0.5  # longer gaps between frames (CPU stall) are not counted

BLINK_MIN_SEC, BLINK_MAX_SEC = 0.05, 0.5  # longer closures are not blinks
BLINK_TREND_N = 6  # blinks averaged for the trend
SLOW_BLINK_SEC = 0.4
SLOW_BLINK_RATIO = 1.5  # … and this much slower than the driver's first blinks of the session

NOD_DROP_DEG = 15.0  # head drops (pitch rises) this much …
NOD_WINDOW_SEC = 1.0  # … within this time, while the eyes are already shut. Looking down
# at a phone lowers the eyelids *as* the head drops, so it does not count.


class FatigueMonitor:
    def __init__(self):
        self.reset()

    def reset(self):
        self.mouth_since: float | None = None
        self.yawn_counted = False
        self.yawns: deque = deque()  # times of counted yawns
        self.samples: deque = deque()  # (t, dt, closed) for PERCLOS
        self.closed_time = self.total_time = 0.0
        self.last_t: float | None = None
        self.closed_since: float | None = None
        self.blinks: deque = deque()  # (t, duration)
        self.first_blinks: list[float] = []
        self.blink_baseline = None
        self.pitches: deque = deque()  # (t, pitch) for nod detection
        self.perclos_high = False
        self.nod = False

    def snooze(self):
        """After an acknowledged fatigue alert: measure afresh, keep the driver's blink baseline."""
        baseline = self.blink_baseline
        self.reset()
        self.blink_baseline = baseline

    def update(self, now: float, face: bool, closed: bool, mouth: float | None, pitch: float | None) -> bool:
        """Feed one frame. Returns the eye-closed decision for the drowsiness
        timer, which ignores the eye squeeze of a yawn."""
        if not face:
            self.last_t = self.closed_since = self.mouth_since = None
            self.yawn_counted, self.nod = False, False
            self.pitches.clear()
            return False
        yawn_excuse = self._update_mouth(now, mouth)
        closed = closed and not yawn_excuse
        self._update_perclos(now, closed)
        self._update_blinks(now, closed)
        self.nod = self._update_nod(now, pitch, closed)
        return closed

    def _update_mouth(self, now, mouth) -> bool:
        """Returns True while a (possible) yawn is excusing closed eyes."""
        is_open = mouth is not None and mouth >= (YAWN_CLOSE if self.mouth_since is not None else YAWN_OPEN)
        if not is_open:
            self.mouth_since, self.yawn_counted = None, False
        else:
            if self.mouth_since is None:
                self.mouth_since = now
            if not self.yawn_counted and now - self.mouth_since >= YAWN_MIN_SEC:
                self.yawn_counted = True
                self.yawns.append(now)
        while self.yawns and now - self.yawns[0] > YAWN_WINDOW_SEC:
            self.yawns.popleft()
        return is_open and now - self.mouth_since <= YAWN_MAX_SEC

    def _update_perclos(self, now, closed):
        dt = 0.0 if self.last_t is None else min(now - self.last_t, MAX_FRAME_GAP)
        self.last_t = now
        self.samples.append((now, dt, closed))
        self.total_time += dt
        self.closed_time += dt if closed else 0.0
        while self.samples and now - self.samples[0][0] > PERCLOS_WINDOW_SEC:
            _, old_dt, old_closed = self.samples.popleft()
            self.total_time -= old_dt
            self.closed_time -= old_dt if old_closed else 0.0

    def _update_blinks(self, now, closed):
        if closed and self.closed_since is None:
            self.closed_since = now
        elif not closed and self.closed_since is not None:
            duration = now - self.closed_since
            self.closed_since = None
            if BLINK_MIN_SEC <= duration <= BLINK_MAX_SEC:
                self.blinks.append((now, duration))
                if self.blink_baseline is None:
                    self.first_blinks.append(duration)
                    if len(self.first_blinks) >= BLINK_TREND_N:
                        self.blink_baseline = float(np.median(self.first_blinks))
        while self.blinks and now - self.blinks[0][0] > 2 * PERCLOS_WINDOW_SEC:
            self.blinks.popleft()

    def _update_nod(self, now, pitch, closed) -> bool:
        """Pitch is only tracked while the eyes stay closed, so the drop is measured
        from where the head was when they closed."""
        if pitch is None or not closed:
            self.pitches.clear()
            return False
        self.pitches.append((now, pitch))
        while now - self.pitches[0][0] > NOD_WINDOW_SEC:
            self.pitches.popleft()
        # Positive pitch = looking down, so a nod is a quick rise in pitch.
        return pitch - min(p for _, p in self.pitches) >= NOD_DROP_DEG

    # --- measures ---

    @property
    def perclos(self) -> float | None:
        """Share of the last minute with the eyes closed (None until there is enough data)."""
        if self.total_time < PERCLOS_MIN_COVERAGE:
            return None
        return max(0.0, self.closed_time) / self.total_time

    @property
    def yawning(self) -> bool:
        return self.yawn_counted

    @property
    def blink_rate(self) -> float | None:
        """Blinks per minute over the PERCLOS window."""
        if self.total_time < PERCLOS_MIN_COVERAGE:
            return None
        latest = self.samples[-1][0]  # not last_t: that is cleared while the face is out of view
        n = sum(1 for t, _ in self.blinks if latest - t <= PERCLOS_WINDOW_SEC)
        return 60.0 * n / self.total_time

    @property
    def blink_duration(self) -> float | None:
        """Mean duration of the last few blinks (seconds)."""
        if len(self.blinks) < BLINK_TREND_N:
            return None
        return float(np.mean([d for _, d in list(self.blinks)[-BLINK_TREND_N:]]))

    def fatigue_reason(self) -> str | None:
        """Why the driver looks fatigued, or None. Call once per frame (PERCLOS hysteresis)."""
        p = self.perclos
        self.perclos_high = p is not None and p >= (PERCLOS_CLEAR if self.perclos_high else PERCLOS_WARN)
        if self.perclos_high:
            return f"Eyes closed {100 * p:.0f}% of the last minute (PERCLOS)"
        if len(self.yawns) >= YAWNS_FOR_FATIGUE:
            return f"Frequent yawning ({len(self.yawns)} in {YAWN_WINDOW_SEC / 60:.0f} min)"
        d = self.blink_duration
        slow = SLOW_BLINK_SEC if self.blink_baseline is None else max(SLOW_BLINK_SEC,
                                                                      SLOW_BLINK_RATIO * self.blink_baseline)
        if d is not None and d >= slow:
            return f"Slow blinks ({1000 * d:.0f} ms on average)"
        return None

    def metrics(self) -> dict:
        p, r, d = self.perclos, self.blink_rate, self.blink_duration
        return {
            "perclos": None if p is None else round(p, 3),
            "blinkRate": None if r is None else round(r, 1),
            "blinkMs": None if d is None else round(1000 * d),
            "yawns": len(self.yawns),
        }
