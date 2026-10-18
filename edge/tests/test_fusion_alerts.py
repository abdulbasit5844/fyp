"""Alert trigger logic (SRS 5.1 / TC-01, TC-02) with a simulated clock."""
import numpy as np
import pytest

from dms_edge.alerts import AlertManager
from dms_edge.fusion import Fusion, Signals
from dms_edge.recorder import ClipRecorder
from dms_edge.settings import MonitorConfig
from dms_edge.temporal import Sustained

FPS = 15
DT = 1 / FPS


def run(fusion, sig, seconds, start=0.0):
    raised, t = [], start
    for _ in range(int(round(seconds * FPS))):
        r = fusion.update(sig, t)
        raised += r.raised
        t += DT
    return raised, r, t


def test_sustained_ignores_short_dropouts():
    s = Sustained(grace_sec=0.3)
    assert s.update(True, 0.0) == 0
    s.update(False, 0.2)  # brief dropout
    assert s.update(True, 1.0) == pytest.approx(1.0)
    s.update(False, 1.1)
    s.update(False, 1.5)  # longer than grace → reset
    assert s.update(True, 2.0) == 0


def test_single_frame_never_alerts():
    f = Fusion(MonitorConfig())
    r = f.update(Signals(True, ear=0.1, yaw=0, pitch=0), 0.0)
    assert r.raised == [] and r.state == "safe"


def test_tc01_drowsiness_alert_after_two_seconds():
    f = Fusion(MonitorConfig())
    closed = Signals(True, ear=0.18, yaw=0, pitch=0)
    raised, r, _ = run(f, closed, 1.9)
    assert raised == [] and r.state == "warning"  # building up
    raised, r, _ = run(f, closed, 0.6, start=1.9)
    assert [(t.type, t.severity) for t in raised] == [("drowsiness", "critical")]
    assert r.state == "critical"


def test_ear_threshold_is_configurable():
    f = Fusion(MonitorConfig(earThreshold=0.20))
    raised, _, _ = run(f, Signals(True, ear=0.22, yaw=0, pitch=0), 3)
    assert raised == []


def test_sensitivity_shortens_required_duration():
    f = Fusion(MonitorConfig(alertSensitivity=5))  # x0.6 → 1.2 s
    raised, _, _ = run(f, Signals(True, ear=0.18, yaw=0, pitch=0), 1.4)
    assert raised and raised[0].type == "drowsiness"


def test_inattention_warning_then_critical_and_clear():
    f = Fusion(MonitorConfig())
    away = Signals(True, ear=0.3, yaw=45, pitch=0)
    # A level 45° turn is where the side mirrors are: the first second is a
    # mirror check, so the 2 s hold starts after it.
    raised, _, t = run(f, away, 2.9)
    assert raised == []
    raised, _, t = run(f, away, 0.3, start=t)
    assert [(x.type, x.severity) for x in raised] == [("inattention", "warning")]
    raised, _, t = run(f, away, 2.0, start=t)
    assert [(x.type, x.severity) for x in raised] == [("inattention", "critical")]
    _, r, _ = run(f, Signals(True, ear=0.3, yaw=0, pitch=0), 1.0, start=t)
    assert r.state == "safe"


def test_missing_face_counts_as_inattention():
    raised, _, _ = run(Fusion(MonitorConfig()), Signals(face=False), 2.5)
    assert raised[0].type == "inattention"


def test_emotional_distress_soft_alert():
    f = Fusion(MonitorConfig())
    raised, _, _ = run(f, Signals(True, ear=0.3, yaw=0, pitch=0, emotion="angry", emotion_conf=0.8), 3.2)
    assert [(x.type, x.severity) for x in raised] == [("emotional_distress", "warning")]


def test_two_warnings_fuse_into_critical():
    f = Fusion(MonitorConfig())
    sig = Signals(True, ear=0.3, yaw=40, pitch=0, emotion="fear", emotion_conf=0.9)
    _, r, _ = run(f, sig, 3.5)
    assert r.state == "critical"


def test_forget_requires_condition_to_build_up_again():
    f = Fusion(MonitorConfig())
    closed = Signals(True, ear=0.18, yaw=0, pitch=0)
    _, _, t = run(f, closed, 2.5)
    f.forget("drowsiness")
    raised, _, t = run(f, closed, 1.0, start=t)
    assert raised == []
    raised, _, _ = run(f, closed, 1.5, start=t)
    assert raised and raised[0].type == "drowsiness"


# --- alert manager ---

class Clock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t


def make_alerts(ack_window=10):
    clock, acks, escalations = Clock(), [], []
    am = AlertManager(MonitorConfig(ackWindowSec=ack_window), acks.append, escalations.append,
                      clock=clock, hardware=False)
    return am, clock, acks, escalations


def test_tc02_unacknowledged_critical_escalates_after_window():
    am, clock, _, esc = make_alerts(10)
    am.raise_alert("e1", "drowsiness", "critical")
    clock.t = 9.9
    am.tick()
    assert esc == [] and am.buzzer.state.startswith("blink")
    clock.t = 10.0
    am.tick()
    assert esc == ["e1"]
    assert am.buzzer.state == "off"


def test_button_ack_cancels_escalation():
    am, clock, acks, esc = make_alerts(10)
    am.raise_alert("e1", "drowsiness", "critical")
    clock.t = 5
    am.button_pressed()
    clock.t = 20
    am.tick()
    assert acks == ["e1"] and esc == []
    assert am.led.state == "off"


def test_app_ack_cancels_without_echo():
    am, clock, acks, esc = make_alerts(10)
    am.raise_alert("e1", "drowsiness", "critical")
    am.acknowledge("e1")
    clock.t = 20
    am.tick()
    assert acks == [] and esc == []


def test_warnings_never_escalate():
    am, clock, _, esc = make_alerts(5)
    am.raise_alert("w1", "inattention", "warning")
    clock.t = 60
    am.tick()
    assert esc == []
    am.resolve("w1")
    assert am.open == {}


# --- recorder ---

def test_recorder_writes_pre_and_post_frames(tmp_path):
    clock, clips = Clock(), []
    rec = ClipRecorder(tmp_path, clips.append, fps=FPS, pre_sec=2, post_sec=1, clock=clock)
    rec._ffmpeg = None  # use the OpenCV writer for a deterministic test
    frame = np.zeros((120, 160, 3), np.uint8)
    for _ in range(4 * FPS):  # 4 s of history, only 2 s kept
        rec.push(frame)
        clock.t += DT
    rec.trigger("evt1")
    for _ in range(int(1.2 * FPS)):
        rec.push(frame)
        clock.t += DT
    import time
    for _ in range(50):
        if clips:
            break
        time.sleep(0.05)
    assert clips and clips[0]["eventId"] == "evt1" and clips[0]["status"] == "available"
    assert 2.8 <= clips[0]["durationSec"] <= 3.2
    assert (tmp_path / "evt1.mp4").stat().st_size > 0


# --- back to normal: the open alert closes, even when critical ---

def test_recovered_driver_closes_critical_alert_and_cancels_escalation():
    from dms_edge import pipeline as pl
    from dms_edge.fusion import FusionResult, Signals, Trigger

    clock = [0.0]
    escalated, resolved = [], []
    p = object.__new__(pl.Pipeline)
    p.alerts = AlertManager(MonitorConfig(ackWindowSec=10), lambda e: None, escalated.append,
                            clock=lambda: clock[0], hardware=False)
    p.open_events, p.state = {}, "safe"
    p._raise_event = lambda type_, sev, *a, **k: (p.alerts.raise_alert("e1", type_, sev), "e1")[1]
    p._resolve_event = lambda eid: (p.alerts.resolve(eid), resolved.append(eid))
    results = iter([
        FusionResult("critical", raised=[Trigger("drowsiness", "critical", 2000, "eyes closed")]),
        FusionResult("safe", cleared=["drowsiness"]),
    ])
    p.fusion = type("F", (), {"update": lambda self, s, now: next(results)})()

    p._apply_fusion(Signals(True), 0)
    assert p.state == "critical" and p.alerts.is_open("e1")
    clock[0] = 3.0
    p._apply_fusion(Signals(True), 3.0)  # eyes open again
    assert p.state == "safe" and resolved == ["e1"]
    clock[0] = 20.0
    p.alerts.tick()
    assert escalated == []  # no escalation after recovery


# --- Start / Stop detecting from the app ---

def test_stop_detecting_closes_open_alerts_and_resets():
    from dms_edge import pipeline as pl
    from dms_edge.fusion import Fusion

    escalated, resolved, statuses = [], [], []
    p = object.__new__(pl.Pipeline)
    p.lock = __import__("threading").Lock()
    p.verify_enabled, p.detecting, p.unknown_event = True, False, None
    p.alerts = AlertManager(MonitorConfig(ackWindowSec=10), lambda e: None, escalated.append,
                            clock=lambda: 0.0, hardware=False)
    p.fusion = Fusion(MonitorConfig())
    p._resolve_event = lambda eid: (p.alerts.resolve(eid), resolved.append(eid))
    p._publish_status = lambda now, force=False: statuses.append(p.detecting)
    p.baseline, p.smooth, p.emotion_avg, p.last_emotion = pl.DriverBaseline(), {}, None, (None, None)

    p._on_detection({"enabled": True})
    assert p.detecting and statuses == [True]
    p.verified, p.state = True, "critical"
    p.alerts.raise_alert("e1", "drowsiness", "critical")
    p.open_events = {"drowsiness": ("e1", "critical")}

    p._on_detection({"enabled": False})
    assert not p.detecting and p.state == "safe" and resolved == ["e1"]
    assert not p.alerts.is_open("e1") and p.open_events == {} and p.verified is False
    p._on_detection({"enabled": False})  # repeated (retained) message: no-op
    assert statuses == [True, False]


# --- live view: on request, kept alive by the app, stops on its own ---

def test_live_view_starts_on_request_and_stops_without_keepalive(monkeypatch):
    from types import SimpleNamespace

    from dms_edge import pipeline as pl

    clock = [100.0]
    monkeypatch.setattr(pl.time, "monotonic", lambda: clock[0])
    urls = []
    p = object.__new__(pl.Pipeline)
    p.s = SimpleNamespace(rtsp_port=8554, device_id="pi-test")
    p.camera = SimpleNamespace(live=False, live_quality=None,
                               set_live=lambda url, quality="480p": urls.append(url and (url, quality)))
    p.live_until = 0.0

    p._on_live({"enabled": True})
    assert urls == [("rtsp://127.0.0.1:8554/pi-test", "480p")]
    p._on_live({"enabled": True, "quality": "720p"})
    assert urls[-1] == ("rtsp://127.0.0.1:8554/pi-test", "720p")
    assert p.live_until == 100.0 + pl.LIVE_KEEPALIVE
    clock[0] += 30
    p._on_live({"enabled": True, "quality": "720p"})  # the app's keep-alive extends it
    assert p.live_until == 130.0 + pl.LIVE_KEEPALIVE

    p._on_live({"enabled": False})
    assert urls[-1] is None and p.live_until == 0.0


def test_live_qualities_stay_within_the_ov5647_limits():
    from dms_edge.camera import LIVE_QUALITIES

    sensor_max = {(640, 480): 62.5, (1280, 720): 46.3, (1920, 1080): 32.8}
    for name, q in LIVE_QUALITIES.items():
        assert q["fps"] <= sensor_max[q["size"]], name
        if q["ai"]:  # the AI copy keeps the stream's aspect ratio and stays small
            assert q["ai"][0] == 640 and abs(q["ai"][0] / q["ai"][1] - q["size"][0] / q["size"][1]) < 0.01
