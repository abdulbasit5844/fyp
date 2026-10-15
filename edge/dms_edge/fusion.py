"""Multi-signal fusion: per-frame signals → driver state and safety events.

Rules (durations are scaled by the alert-sensitivity factor):
  drowsiness          EAR < threshold for earSustainSec                → critical
                      … for half that time                              → warning state only
  inattention         |yaw| or |pitch| > threshold, or face missing,
                      for headPoseSustainSec                            → warning
                      … for twice that time                             → critical
  emotional_distress  angry/fear dominant for emotionSustainSec          → warning (soft alert)
  combined            two or more warning-level conditions at once      → critical

Each condition raises one event per episode (rising edge) and reports when
it clears, so warnings can be resolved automatically.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .settings import MonitorConfig
from .temporal import Sustained

DISTRESS = {"angry", "fear"}
SEVERITY_RANK = {"safe": 0, "warning": 1, "critical": 2}


@dataclass
class Signals:
    face: bool
    ear: float | None = None
    yaw: float | None = None
    pitch: float | None = None
    roll: float | None = None
    emotion: str | None = None
    emotion_conf: float | None = None


@dataclass
class Trigger:
    type: str
    severity: str
    sustained_ms: int
    description: str


@dataclass
class FusionResult:
    state: str
    raised: list[Trigger] = field(default_factory=list)
    cleared: list[str] = field(default_factory=list)  # condition types that ended
    levels: dict = field(default_factory=dict)


class Fusion:
    def __init__(self, cfg: MonitorConfig):
        self.cfg = cfg
        self.timers = {k: Sustained() for k in ("drowsiness", "inattention", "emotional_distress")}
        self.active: dict[str, str] = {}  # condition → severity already raised

    def _levels(self, s: Signals, now: float) -> dict[str, tuple[str, float]]:
        c, k = self.cfg, self.cfg.sensitivity_factor
        out = {}

        closed = s.face and s.ear is not None and s.ear < c.earThreshold
        held = self.timers["drowsiness"].update(closed, now)
        need = c.earSustainSec * k
        if held >= need:
            out["drowsiness"] = ("critical", held)
        elif held >= need / 2:
            out["drowsiness"] = ("warning", held)

        away = (not s.face) or (
            s.yaw is not None and (abs(s.yaw) > c.headPoseThresholdDeg or abs(s.pitch) > c.headPoseThresholdDeg)
        )
        held = self.timers["inattention"].update(away, now)
        need = c.headPoseSustainSec * k
        if held >= 2 * need:
            out["inattention"] = ("critical", held)
        elif held >= need:
            out["inattention"] = ("warning", held)

        distressed = s.face and s.emotion in DISTRESS and (s.emotion_conf or 0) >= 0.5
        held = self.timers["emotional_distress"].update(distressed, now)
        if held >= c.emotionSustainSec * k:
            out["emotional_distress"] = ("warning", held)
        return out

    def update(self, s: Signals, now: float) -> FusionResult:
        levels = self._levels(s, now)

        # Combined warnings escalate to critical.
        if sum(1 for sev, _ in levels.values() if sev == "warning") >= 2:
            levels = {k: ("critical", h) for k, (_, h) in levels.items()}

        state = max((sev for sev, _ in levels.values()), key=SEVERITY_RANK.get, default="safe")
        result = FusionResult(state=state, levels=levels)

        for cond, (sev, held) in levels.items():
            # Drowsiness at warning level only colours the state; it alerts at critical.
            if cond == "drowsiness" and sev == "warning":
                continue
            prev = self.active.get(cond)
            if prev is None or SEVERITY_RANK[sev] > SEVERITY_RANK[prev]:
                self.active[cond] = sev
                result.raised.append(Trigger(cond, sev, int(held * 1000), _describe(cond, sev, s)))

        for cond in list(self.active):
            if cond not in levels:
                del self.active[cond]
                result.cleared.append(cond)
        return result

    def forget(self, cond: str):
        """After an acknowledgment: if the condition persists, it must build up and alert again."""
        self.active.pop(cond, None)
        if cond in self.timers:
            self.timers[cond].reset()

    def reset(self):
        for t in self.timers.values():
            t.reset()
        self.active.clear()


def _describe(cond: str, sev: str, s: Signals) -> str:
    if cond == "drowsiness":
        return f"Eyes closed (EAR {s.ear:.2f})" if s.ear is not None else "Eyes closed"
    if cond == "inattention":
        if not s.face:
            return "Driver's face not visible"
        return f"Head turned away (yaw {s.yaw:.0f}°, pitch {s.pitch:.0f}°)"
    return f"Driver appears {s.emotion or 'distressed'}"
