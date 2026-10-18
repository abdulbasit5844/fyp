"""Module 3 refinements (yawns, PERCLOS, blink trends, head nods) and Module 5
refinements (separate yaw / pitch limits, roll, mirror checks, looking down),
with a simulated clock."""
import numpy as np
import pytest

from dms_edge import drowsiness
from dms_edge.calibration import DriverBaseline
from dms_edge.fusion import Fusion, Signals, in_mirror_zone
from dms_edge.settings import MonitorConfig

FPS = 15
DT = 1 / FPS


def drive(fusion, signal_at, seconds, start=0.0):
    """signal_at(t) → Signals, for every frame in [start, start + seconds)."""
    raised, cleared, t, r = [], [], start, None
    for _ in range(int(round(seconds * FPS))):
        r = fusion.update(signal_at(t), t)
        raised += r.raised
        cleared += r.cleared
        t += DT
    return raised, cleared, r, t


def sig(closed=False, mouth=0.05, yaw=0.0, pitch=0.0, roll=0.0, emotion=None, conf=None):
    return Signals(True, 0.15 if closed else 0.3, yaw, pitch, roll, emotion, conf,
                   eyes_closed=closed, mouth_open=mouth)


def types(raised):
    return [(x.type, x.severity) for x in raised]


# --- yawning ---

def test_mouth_aspect_ratio():
    pts = np.zeros((478, 2))
    pts[[78, 308]] = [[0, 0], [50, 0]]
    pts[[13, 14]] = [[25, -10], [25, 20]]
    assert drowsiness.mouth_aspect_ratio(pts) == pytest.approx(0.6)


def test_yawn_raises_advisory_warning_and_clears():
    f = Fusion(MonitorConfig())
    raised, _, _, t = drive(f, lambda t: sig(mouth=0.05), 1.0)
    raised, _, r, t = drive(f, lambda t: sig(mouth=0.75), 2.0, t)
    assert types(raised) == [("yawning", "warning")]
    assert r.state == "warning"
    _, cleared, r, _ = drive(f, lambda t: sig(mouth=0.05), 0.5, t)
    assert cleared == ["yawning"] and r.state == "safe"


def test_talking_is_not_yawning():
    f = Fusion(MonitorConfig())
    # Mouth opening and closing every 0.4 s, for 20 s.
    raised, _, _, _ = drive(f, lambda t: sig(mouth=0.6 if int(t / 0.4) % 2 else 0.1), 20)
    assert raised == []


def test_eyes_squeezed_shut_during_a_yawn_are_not_drowsiness():
    f = Fusion(MonitorConfig())
    raised, _, _, _ = drive(f, lambda t: sig(closed=True, mouth=0.8), 4.0)
    assert ("drowsiness", "critical") not in types(raised)


def test_eyes_closed_with_mouth_hanging_open_is_still_drowsiness():
    # Asleep with the jaw dropped: past YAWN_MAX_SEC the open mouth is no excuse.
    f = Fusion(MonitorConfig())
    raised, _, _, _ = drive(f, lambda t: sig(closed=True, mouth=0.8), drowsiness.YAWN_MAX_SEC + 2.5)
    assert ("drowsiness", "critical") in types(raised)


def test_three_yawns_in_five_minutes_mean_fatigue():
    f = Fusion(MonitorConfig())
    raised = []

    def yawning_every_minute(t):
        return sig(mouth=0.8 if t % 60 < 3 else 0.05)

    r, _, _, _ = drive(f, yawning_every_minute, 150)
    raised += r
    fatigue = [x for x in raised if x.type == "fatigue"]
    assert len(fatigue) == 1 and "yawning" in fatigue[0].description
    assert sum(1 for x in raised if x.type == "yawning") == 3


def test_acknowledged_yawn_does_not_realert_until_the_next_yawn():
    f = Fusion(MonitorConfig())
    raised, _, _, t = drive(f, lambda t: sig(mouth=0.8), 2.0)
    assert types(raised) == [("yawning", "warning")]
    f.forget("yawning")
    raised, _, _, t = drive(f, lambda t: sig(mouth=0.8), 2.0, t)
    assert raised == []
    raised, _, _, t = drive(f, lambda t: sig(mouth=0.05), 1.0, t)
    raised, _, _, t = drive(f, lambda t: sig(mouth=0.8), 2.0, t)
    assert types(raised) == [("yawning", "warning")]


# --- PERCLOS and blinks ---

def bursts(closed_sec, period, **kw):
    """Eyes closed for closed_sec at the start of every period."""
    return lambda t: sig(closed=(t % period) < closed_sec, **kw)


def test_perclos_rises_with_frequent_short_closures():
    f = Fusion(MonitorConfig())
    # 0.8 s closed every 3.3 s = 24 % of the time, but never long enough for the drowsiness rule.
    raised, _, _, _ = drive(f, bursts(0.8, 3.3), 60)
    assert types(raised) == [("fatigue", "warning")]
    assert "PERCLOS" in raised[0].description
    assert f.metrics["perclos"] == pytest.approx(0.24, abs=0.03)


def test_fatigued_driver_closing_eyes_for_one_second_is_critical():
    # Fatigue + the drowsiness warning level (half the 2 s hold) fuse into critical.
    f = Fusion(MonitorConfig())
    raised, _, _, t = drive(f, bursts(0.8, 3.3), 60)
    assert types(raised) == [("fatigue", "warning")]
    raised, _, r, _ = drive(f, lambda t: sig(closed=True), 1.2, t)
    assert ("drowsiness", "critical") in types(raised) and r.state == "critical"


def test_normal_blinking_is_not_fatigue():
    f = Fusion(MonitorConfig())
    raised, _, _, _ = drive(f, bursts(0.2, 4.0), 90)  # 15 blinks/min, 200 ms each
    assert raised == []
    m = f.metrics
    assert m["perclos"] == pytest.approx(0.05, abs=0.02)
    assert m["blinkRate"] == pytest.approx(15, abs=2)
    assert m["blinkMs"] == pytest.approx(200, abs=40)


def test_slow_blinks_warn_before_perclos_does():
    f = Fusion(MonitorConfig())
    _, _, _, t = drive(f, bursts(0.2, 4.0), 30)  # the driver's normal blinks set the baseline
    raised, _, _, _ = drive(f, bursts(0.45, 6.0), 40, t)  # slower blinks: PERCLOS only 7.5 %
    fatigue = [x for x in raised if x.type == "fatigue"]
    assert fatigue and "Slow blinks" in fatigue[0].description


def test_metrics_after_the_face_leaves_the_camera():
    # Regression: the Pi pipeline crashed in the perf log once the face was lost after 30 s.
    f = Fusion(MonitorConfig())
    _, _, _, t = drive(f, bursts(0.2, 4.0), 40)
    _, _, _, _ = drive(f, lambda t: Signals(False), 2.0, t)
    assert f.metrics["blinkRate"] == pytest.approx(15, abs=3)


def test_fatigue_needs_enough_data():
    f = Fusion(MonitorConfig())
    raised, _, _, _ = drive(f, bursts(1.2, 3.0), 20)  # 40 % closed, but only 20 s observed
    assert "fatigue" not in [x.type for x in raised]
    assert f.metrics["perclos"] is None


def test_acknowledged_fatigue_is_measured_afresh():
    f = Fusion(MonitorConfig())
    raised, _, _, t = drive(f, bursts(1.2, 5.0), 60)
    assert "fatigue" in [x.type for x in raised]
    f.forget("fatigue")
    raised, _, _, t = drive(f, bursts(1.2, 5.0), 20, t)
    assert "fatigue" not in [x.type for x in raised]
    raised, _, _, _ = drive(f, bursts(1.2, 5.0), 30, t)
    assert "fatigue" in [x.type for x in raised]


# --- head nod ---

def test_head_nod_with_closed_eyes_alerts_at_once():
    f = Fusion(MonitorConfig())
    _, _, _, t = drive(f, lambda t: sig(), 1.0)
    t0 = t
    # Eyes close and the head drops 25° in half a second.
    raised, _, _, _ = drive(f, lambda t: sig(closed=True, pitch=min(25.0, 50 * (t - t0))), 1.0, t)
    assert types(raised)[:1] == [("drowsiness", "critical")]
    assert "nod" in raised[0].description
    assert raised[0].sustained_ms < 1000  # well before the 2 s rule


def test_nod_with_open_eyes_is_not_drowsiness():
    f = Fusion(MonitorConfig())
    _, _, _, t = drive(f, lambda t: sig(), 1.0)
    t0 = t
    raised, _, _, _ = drive(f, lambda t: sig(pitch=min(25.0, 50 * (t - t0))), 1.0, t)
    assert "drowsiness" not in [x.type for x in raised]


def test_looking_down_with_lowered_lids_is_not_a_nod():
    # The eyelids drop at the same moment as the head (gaze down at a phone):
    # the head was already down by the time the eyes counted as closed.
    f = Fusion(MonitorConfig())
    _, _, _, t = drive(f, lambda t: sig(), 1.0)
    t0 = t
    raised, _, _, _ = drive(f, lambda t: sig(closed=t - t0 > 0.4, pitch=min(25.0, 60 * (t - t0))), 1.5, t)
    assert "drowsiness" not in [x.type for x in raised]


def test_nod_alert_clears_when_eyes_open():
    f = Fusion(MonitorConfig())
    t0 = 0.0
    raised, _, _, t = drive(f, lambda t: sig(closed=True, pitch=min(25.0, 50 * (t - t0))), 0.8)
    assert ("drowsiness", "critical") in types(raised)
    _, cleared, r, _ = drive(f, lambda t: sig(), 1.0, t)
    assert "drowsiness" in cleared and r.state == "safe"


# --- head pose: separate limits, roll, mirror checks, looking down ---

def test_twenty_degrees_is_enough_down_but_not_sideways():
    f = Fusion(MonitorConfig())  # 30° left/right, 20° up/down
    raised, _, _, _ = drive(f, lambda t: sig(yaw=25), 5)
    assert raised == []
    raised, _, _, _ = drive(Fusion(MonitorConfig()), lambda t: sig(pitch=25), 2.2)
    assert types(raised) == [("looking_down", "warning")]


def test_looking_down_is_its_own_event_and_escalates_sooner():
    f = Fusion(MonitorConfig())
    raised, _, _, t = drive(f, lambda t: sig(pitch=35), 2.2)
    assert types(raised) == [("looking_down", "warning")]
    assert "phone" in raised[0].description
    raised, _, r, t = drive(f, lambda t: sig(pitch=35), 1.0, t)  # 1.5 x 2 s, not 2 x 2 s
    assert types(raised) == [("looking_down", "critical")]
    assert "inattention" not in r.levels


def test_looking_up_counts_as_inattention():
    raised, _, _, _ = drive(Fusion(MonitorConfig()), lambda t: sig(pitch=-28), 2.2)
    assert types(raised) == [("inattention", "warning")]
    assert "up" in raised[0].description


def test_head_tilt_roll_counts_as_inattention():
    raised, _, _, _ = drive(Fusion(MonitorConfig()), lambda t: sig(roll=40), 2.2)
    assert types(raised) == [("inattention", "warning")]
    assert "tilted" in raised[0].description
    raised, _, _, _ = drive(Fusion(MonitorConfig()), lambda t: sig(roll=15), 5)
    assert raised == []


def test_repeated_mirror_checks_never_alert():
    f = Fusion(MonitorConfig())
    # 0.8 s at the side mirror, 0.2 s on the road, for 12 s. The 0.3 s dropout
    # grace would otherwise merge these glances into one long look away.
    raised, _, _, _ = drive(f, lambda t: sig(yaw=50 if t % 1.0 < 0.8 else 0), 12)
    assert raised == []


def test_same_glances_outside_a_mirror_zone_do_alert():
    f = Fusion(MonitorConfig())
    # Down and to the side (glovebox): not a mirror, so the glances merge and alert.
    raised, _, _, _ = drive(f, lambda t: sig(yaw=50, pitch=15) if t % 1.0 < 0.8 else sig(), 12)
    assert "inattention" in [x.type for x in raised]


def test_staring_into_the_mirror_still_alerts():
    raised, _, _, _ = drive(Fusion(MonitorConfig()), lambda t: sig(yaw=50), 3.2)
    assert types(raised) == [("inattention", "warning")]


@pytest.mark.parametrize("yaw,pitch,expected", [
    (45, 0, True), (-45, 0, True),  # side mirrors, either side
    (25, -15, True),  # rear-view mirror: up and to the side
    (45, 20, False),  # down and to the side
    (0, -30, False),  # straight up
    (85, 0, False),  # over the shoulder
])
def test_mirror_zones(yaw, pitch, expected):
    assert in_mirror_zone(yaw, pitch) is expected


def test_yawning_does_not_escalate_another_warning():
    f = Fusion(MonitorConfig())
    raised, _, r, _ = drive(f, lambda t: sig(mouth=0.8, emotion="angry", conf=0.9), 3.5)
    assert ("yawning", "warning") in types(raised) and ("emotional_distress", "warning") in types(raised)
    assert r.state == "warning"


def test_calibration_learns_neutral_roll():
    b = DriverBaseline(samples=10)
    for _ in range(10):
        b.add(0.3, None, 0.0, 0.0, 12.0)  # camera mounted slightly rotated
    assert b.relative_pose(0.0, 0.0, 12.0) == (0.0, 0.0, 0.0)
    assert b.relative_pose(0.0, 0.0, 45.0)[2] == pytest.approx(33.0)
