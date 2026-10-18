"""Multi-signal fusion: per-frame signals → driver state and safety events.

Rules (durations are scaled by the alert-sensitivity factor):
  drowsiness          EAR < threshold for earSustainSec                → critical
                      … for half that time                              → warning state only
                      head nod (pitch drops ≥15° in 1 s) with eyes closed → critical at once
  yawning             mouth open ≥1.5 s (jawOpen / MAR)                 → warning (advisory)
  fatigue             PERCLOS ≥15 % over 60 s, ≥3 yawns in 5 min,
                      or slow blinks                                    → warning
  inattention         |yaw| > headPoseThresholdDeg, looking up more than
                      headPitchThresholdDeg, |roll| > 30°, or face missing,
                      for headPoseSustainSec                            → warning
                      … for twice that time                             → critical
  looking_down        pitch down > headPitchThresholdDeg (phone, lap)
                      for headPoseSustainSec                            → warning
                      … for 1.5x that time (more dangerous than a turn) → critical
  emotional_distress  angry/fear dominant for emotionSustainSec          → warning (soft alert)
  combined            two or more warning-level conditions at once      → critical
                      (yawning is advisory and does not count; fatigue counts, so it
                      lowers the bar for the acute alerts, but stays a warning itself)

Glances into the mirror zones (level to either side, or up and to the side)
start counting as inattention only after MIRROR_GLANCE_SEC, so normal mirror
checks never build up to an alert.

Each condition raises one event per episode (rising edge) and reports when
it clears, so warnings can be resolved automatically.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .drowsiness import FatigueMonitor
from .settings import MonitorConfig
from .temporal import Sustained

DISTRESS = {"angry", "fear"}
SEVERITY_RANK = {"safe": 0, "warning": 1, "critical": 2}
ADVISORY = {"yawning"}  # shown and logged, but not enough to escalate a second warning
BACKGROUND = ADVISORY | {"fatigue"}  # states over minutes: never upgraded to critical themselves

ROLL_LIMIT_DEG = 30.0  # head tilted towards a shoulder
LOOK_DOWN_CRITICAL = 1.5  # x headPoseSustainSec
MIRROR_GLANCE_SEC = 1.0
# (min |yaw|, max |yaw|, min pitch, max pitch) relative to the driver's neutral pose;
# positive pitch = looking down. Symmetric, so it works for left- and right-hand drive.
MIRROR_ZONES = (
    (20.0, 75.0, -15.0, 10.0),  # side mirrors: a level glance to either side
    (10.0, 45.0, -30.0, -5.0),  # rear-view mirror: up and to the side
)


def in_mirror_zone(yaw: float, pitch: float) -> bool:
    return any(y0 <= abs(yaw) <= y1 and p0 <= pitch <= p1 for y0, y1, p0, p1 in MIRROR_ZONES)


@dataclass
class Signals:
    face: bool
    ear: float | None = None
    yaw: float | None = None
    pitch: float | None = None
    roll: float | None = None
    emotion: str | None = None
    emotion_conf: float | None = None
    # Per-driver decision from calibration (blendshapes / personal EAR); when
    # None, the fixed EAR threshold from the settings is used instead.
    eyes_closed: bool | None = None
    mouth_open: float | None = None  # jawOpen blendshape (or mouth aspect ratio)


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
        self.timers = {k: Sustained() for k in
                       ("drowsiness", "inattention", "looking_down", "emotional_distress", "fatigue")}
        self.fatigue = FatigueMonitor()
        self.active: dict[str, str] = {}  # condition → severity already raised
        self.hold_off: set[str] = set()  # acknowledged; must end before it can alert again
        self.reasons: dict[str, str] = {}
        self.mirror_since: float | None = None
        self.nod_episode = False

    @property
    def metrics(self) -> dict:
        """PERCLOS, blink rate / duration and yawn count, for events and the log."""
        return self.fatigue.metrics()

    def _levels(self, s: Signals, now: float) -> dict[str, tuple[str, float]]:
        c, k = self.cfg, self.cfg.sensitivity_factor
        out, self.reasons = {}, {}

        # --- eyes, mouth and fatigue (Module 3) ---
        if s.eyes_closed is not None:
            closed = s.face and s.eyes_closed
        else:
            closed = s.face and s.ear is not None and s.ear < c.earThreshold
        fat = self.fatigue
        closed = fat.update(now, s.face, closed, s.mouth_open, s.pitch)
        timer = self.timers["drowsiness"]
        held = timer.update(closed, now)
        if fat.nod:
            self.nod_episode = True
        elif timer.since is None:
            self.nod_episode = False  # eyes open again
        need = c.earSustainSec * k
        if held >= need or self.nod_episode:
            out["drowsiness"] = ("critical", held)
            if held < need:
                self.reasons["drowsiness"] = "Head nodding with eyes closed"
        elif held >= need / 2:
            out["drowsiness"] = ("warning", held)

        if fat.yawning:
            out["yawning"] = ("warning", now - fat.mouth_since)
        reason = fat.fatigue_reason()
        held = self.timers["fatigue"].update(reason is not None, now)
        if reason:
            out["fatigue"] = ("warning", held)
            self.reasons["fatigue"] = reason

        # --- head pose and attention (Module 5) ---
        turned = down = False
        if s.face and s.yaw is not None:
            pitch = s.pitch or 0.0
            down = pitch > c.headPitchThresholdDeg
            if abs(s.yaw) > c.headPoseThresholdDeg:
                turned, why = True, f"Head turned away (yaw {s.yaw:.0f}°)"
            elif -pitch > c.headPitchThresholdDeg:
                turned, why = True, f"Looking up (pitch {-pitch:.0f}°)"
            elif s.roll is not None and abs(s.roll) > ROLL_LIMIT_DEG:
                turned, why = True, f"Head tilted (roll {s.roll:.0f}°)"
            if turned and not down and in_mirror_zone(s.yaw, pitch):
                if self.mirror_since is None:
                    self.mirror_since = now
                turned = now - self.mirror_since >= MIRROR_GLANCE_SEC  # a mirror check is not inattention
            else:
                self.mirror_since = None
            if turned:
                self.reasons["inattention"] = why
        else:
            self.mirror_since = None

        away = (not s.face) or (turned and not down)
        held = self.timers["inattention"].update(away, now)
        need = c.headPoseSustainSec * k
        if held >= 2 * need:
            out["inattention"] = ("critical", held)
        elif held >= need:
            out["inattention"] = ("warning", held)

        held = self.timers["looking_down"].update(down, now)
        if held >= LOOK_DOWN_CRITICAL * need:
            out["looking_down"] = ("critical", held)
        elif held >= need:
            out["looking_down"] = ("warning", held)

        # --- emotion ---
        distressed = s.face and s.emotion in DISTRESS and (s.emotion_conf or 0) >= 0.5
        held = self.timers["emotional_distress"].update(distressed, now)
        if held >= c.emotionSustainSec * k:
            out["emotional_distress"] = ("warning", held)
        return out

    def update(self, s: Signals, now: float) -> FusionResult:
        levels = self._levels(s, now)

        # Combined warnings escalate to critical.
        if sum(1 for cond, (sev, _) in levels.items() if sev == "warning" and cond not in ADVISORY) >= 2:
            levels = {cond: (sev if cond in BACKGROUND else "critical", h) for cond, (sev, h) in levels.items()}

        state = max((sev for sev, _ in levels.values()), key=SEVERITY_RANK.get, default="safe")
        result = FusionResult(state=state, levels=levels)

        self.hold_off &= set(levels)
        for cond, (sev, held) in levels.items():
            # Drowsiness at warning level only colours the state; it alerts at critical.
            if (cond == "drowsiness" and sev == "warning") or cond in self.hold_off:
                continue
            prev = self.active.get(cond)
            if prev is None or SEVERITY_RANK[sev] > SEVERITY_RANK[prev]:
                self.active[cond] = sev
                result.raised.append(Trigger(cond, sev, int(held * 1000), self._describe(cond, s)))

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
        if cond == "fatigue":
            self.fatigue.snooze()
        elif cond == "yawning":
            self.hold_off.add(cond)  # this yawn is acknowledged; the next one alerts again

    def reset(self):
        for t in self.timers.values():
            t.reset()
        self.fatigue.reset()
        self.active.clear()
        self.hold_off.clear()
        self.mirror_since, self.nod_episode = None, False

    def _describe(self, cond: str, s: Signals) -> str:
        if cond in self.reasons:
            return self.reasons[cond]
        if cond == "drowsiness":
            return f"Eyes closed (EAR {s.ear:.2f})" if s.ear is not None else "Eyes closed"
        if cond == "yawning":
            return f"Yawning ({len(self.fatigue.yawns)} in the last 5 min)"
        if cond == "inattention":
            return "Driver's face not visible" if not s.face else "Not watching the road"
        if cond == "looking_down":
            return f"Looking down (pitch {s.pitch:.0f}°): phone or lap" if s.pitch is not None else "Looking down"
        return f"Driver appears {s.emotion or 'distressed'}"
