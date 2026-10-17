"""Per-driver calibration and signal smoothing.

People differ: some have narrow eyes, and the camera is rarely straight in front
of the driver. For the first few seconds of monitoring the pipeline records the
driver's normal open-eye level and normal head position, then judges eye closure
and looking-away *relative to that driver*, not against fixed numbers.
"""
from __future__ import annotations

from collections import deque

import numpy as np

CALIBRATION_SAMPLES = 40  # face frames (~4 s at 10 fps)
MAX_NEUTRAL_DEG = 25.0  # a "neutral" pose beyond this is a mounting problem, not normal
CLOSURE_MARGIN = 0.35  # eyeBlink score above the driver's open-eye level that means closed
EAR_CLOSED_RATIO = 0.72  # EAR below this fraction of the open-eye EAR means closed (fallback)


class Median3:
    """Median of the last three values: removes single-frame landmark glitches."""

    def __init__(self):
        self.buf: deque = deque(maxlen=3)

    def __call__(self, value):
        if value is None:
            self.buf.clear()
            return None
        self.buf.append(value)
        return float(np.median(self.buf))

    def reset(self):
        self.buf.clear()


class DriverBaseline:
    def __init__(self, samples: int = CALIBRATION_SAMPLES):
        self.samples = samples
        self.reset()

    def reset(self):
        self.ear: list[float] = []
        self.closure: list[float] = []
        self.yaw: list[float] = []
        self.pitch: list[float] = []
        self.ear_open = self.closure_open = None
        self.yaw0 = self.pitch0 = 0.0

    @property
    def ready(self) -> bool:
        return self.ear_open is not None

    def add(self, ear, closure, yaw, pitch):
        if self.ready or ear is None or yaw is None:
            return
        self.ear.append(ear)
        self.yaw.append(yaw)
        self.pitch.append(pitch)
        if closure is not None:
            self.closure.append(closure)
        if len(self.ear) >= self.samples:
            # Upper EAR / lower closure percentiles skip blinks during calibration.
            self.ear_open = float(np.percentile(self.ear, 75))
            self.closure_open = float(np.percentile(self.closure, 25)) if self.closure else None
            self.yaw0 = float(np.clip(np.median(self.yaw), -MAX_NEUTRAL_DEG, MAX_NEUTRAL_DEG))
            self.pitch0 = float(np.clip(np.median(self.pitch), -MAX_NEUTRAL_DEG, MAX_NEUTRAL_DEG))

    def eyes_closed(self, ear, closure, ear_threshold: float) -> bool | None:
        """ear_threshold is the user's EAR setting (default 0.25); higher = more
        sensitive, and it shifts the personal thresholds the same way."""
        sensitivity = ear_threshold / 0.25
        if closure is not None:
            base = self.closure_open if self.closure_open is not None else 0.1
            limit = float(np.clip(base + CLOSURE_MARGIN / sensitivity, 0.4, 0.8))
            return closure >= limit
        if ear is None:
            return None
        limit = self.ear_open * EAR_CLOSED_RATIO * sensitivity if self.ready else ear_threshold
        return ear < limit

    def relative_pose(self, yaw, pitch):
        if yaw is None:
            return None, None
        return yaw - self.yaw0, pitch - self.pitch0
