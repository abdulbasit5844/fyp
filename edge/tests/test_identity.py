"""Driver identity before monitoring: only a recognised, authorized driver is
monitored; anyone else raises one unverified_driver event with a photo."""
from types import SimpleNamespace

import numpy as np

from dms_edge import pipeline as pl
from dms_edge.alerts import AlertManager
from dms_edge.landmarks import Face
from dms_edge.settings import MonitorConfig

FRAME = np.zeros((480, 640, 3), np.uint8)
FACE = Face(np.zeros((478, 2), np.float32), (250, 150, 140, 160))
RNG = np.random.default_rng(5)


def unit(v):
    v = np.asarray(v, np.float32)
    return v / np.linalg.norm(v)


REGISTERED = unit(RNG.normal(size=128))


def with_score(score):
    """A probe whose cosine similarity to REGISTERED is `score`."""
    other = RNG.normal(size=128)
    other = unit(other - other @ REGISTERED * REGISTERED)
    return unit(score * REGISTERED + np.sqrt(1 - score ** 2) * other)


class FakeMqtt:
    def __init__(self):
        self.sent = []

    def publish(self, kind, payload, retain=False):
        self.sent.append((kind, payload))


def make_pipeline(authorized=True, enrolled=True):
    p = object.__new__(pl.Pipeline)  # skip camera / models
    p.verify_enabled, p.detecting, p.state, p.last_status = True, True, "safe", 0.0
    p.drivers = [{"id": "d1", "displayName": "Basit", "isAuthorized": authorized,
                  "embeddings": [{"vector": REGISTERED.tolist()}] if enrolled else []}]
    p.s = SimpleNamespace(verify_threshold=0.363)
    p.cfg = MonitorConfig()
    p.mqtt = FakeMqtt()
    p.alerts = AlertManager(p.cfg, lambda e: None, lambda e: None, clock=lambda: 0.0, hardware=False)
    p.recorder = SimpleNamespace(trigger=lambda eid: None)
    p.gps = SimpleNamespace(position=None)
    p.camera = SimpleNamespace(live=False, live_quality=None, fps=10.0, connected=True)
    p.unknown_event = None
    p._reset_identity()
    return p


def look(p, probe, times, start=0.0, every=0.3):
    """`times` identity checks, `every` seconds apart; returns the time after the last."""
    t = start
    for _ in range(times):
        p._embedding = lambda frame, face: probe
        p._verify(FRAME, FACE, t)
        t += every
    return t


def events(p, kind="event"):
    return [m for k, m in p.mqtt.sent if k == kind]


def test_registered_driver_is_monitored_after_three_matches():
    p = make_pipeline()
    look(p, with_score(0.9), 2)
    assert not p.verified and p.identity == "verifying"
    look(p, with_score(0.9), 1, start=0.6)
    assert p.verified and p.identity == "verified" and p.driver == {"id": "d1", "name": "Basit"}
    assert events(p) == []


def test_stranger_raises_one_event_with_photo_and_is_not_monitored():
    p = make_pipeline()
    look(p, with_score(0.05), pl.UNKNOWN_AFTER - 1)
    assert events(p) == []
    t = look(p, with_score(0.05), 1, start=(pl.UNKNOWN_AFTER - 1) * 0.3)
    [e] = events(p)
    assert e["type"] == "unverified_driver" and e["severity"] == "critical"
    assert "Unknown person" in e["description"] and e["photo"]
    assert p.alerts.open == {}  # silent in the car: the backend alerts the owner
    assert not p.verified and p.identity == "unknown"
    status = events(p, "status")[-1]
    assert status["identity"] == "unknown" and status["monitoring"] is False
    look(p, with_score(0.05), 20, start=t)
    assert len(events(p)) == 1  # one alert per person, not one per look


def test_registered_driver_recognised_later_closes_the_alert():
    p = make_pipeline()
    t = look(p, with_score(0.05), pl.UNKNOWN_AFTER)
    [e] = events(p)
    look(p, with_score(0.9), 3, start=t)
    assert p.verified and p.identity == "verified"
    assert events(p, "event/resolve")[-1]["eventId"] == e["eventId"]


def test_borderline_scores_are_not_treated_as_a_stranger():
    # A registered driver at a bad angle scores just under the threshold.
    p = make_pipeline()
    look(p, with_score(0.33), 30, every=0.3)  # 9 s of looks
    assert events(p) == []


def test_face_never_clear_enough_is_unknown_after_timeout():
    p = make_pipeline()
    look(p, None, int(pl.VERIFY_TIMEOUT / 0.3) + 2)
    [e] = events(p)
    assert "could not be identified" in e["description"]


def test_registered_but_unauthorized_driver():
    p = make_pipeline(authorized=False)
    look(p, with_score(0.9), pl.UNKNOWN_AFTER)
    [e] = events(p)
    assert "not authorized" in e["description"] and not p.verified


def test_count_restarts_when_the_face_leaves():
    p = make_pipeline()
    t = look(p, with_score(0.05), pl.UNKNOWN_AFTER - 2)
    look(p, with_score(0.05), pl.UNKNOWN_AFTER - 2, start=t + pl.VERIFY_GAP + 1)
    assert events(p) == []


def test_nobody_enrolled_monitors_at_once():
    p = make_pipeline(enrolled=False)
    look(p, with_score(0.05), 1)
    assert p.verified and p.identity == "none" and events(p) == []


def test_stopping_detection_closes_the_unknown_person_alert():
    p = make_pipeline()
    look(p, with_score(0.05), pl.UNKNOWN_AFTER)
    [e] = events(p)
    p.lock = __import__("threading").Lock()
    p.open_events, p.fusion = {}, SimpleNamespace(reset=lambda: None)
    p._reset_driver_model = lambda: None
    p._on_detection({"enabled": False})
    assert events(p, "event/resolve")[-1]["eventId"] == e["eventId"]
    assert p.identity == "verifying" and p.unknown_event is None
