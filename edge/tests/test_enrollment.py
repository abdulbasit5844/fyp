"""Face enrollment on the edge: live view → capture → result, driven by cmd/enroll."""
import numpy as np

from dms_edge import pipeline as pl
from dms_edge.landmarks import Face


class FakeMqtt:
    def __init__(self):
        self.sent = []

    def publish(self, kind, payload, retain=False):
        self.sent.append((kind, payload))


def make_pipeline():
    p = object.__new__(pl.Pipeline)  # skip camera / models
    p.mqtt, p.enroll, p.verified = FakeMqtt(), None, True
    p._embedding = lambda frame, face: np.ones(128)
    return p


FRAME = np.zeros((480, 640, 3), np.uint8)
FACE = Face(np.zeros((478, 2), np.float32), (250, 150, 140, 160))


def last(p):
    return p.mqtt.sent[-1][1]


def test_preview_streams_view_and_warns_when_nobody_is_there(monkeypatch):
    p = make_pipeline()
    p._on_enroll({"driverId": "d1", "action": "preview"})
    p._handle_enrollment(FRAME, None)
    msg = last(p)
    assert msg["status"] == "progress" and msg["mode"] == "preview"
    assert msg["faceVisible"] is False and msg["preview"]
    assert msg["samples"] == 0  # preview never stores samples


def test_capture_collects_samples_and_sends_photo(monkeypatch):
    p = make_pipeline()
    clock = [100.0]
    monkeypatch.setattr(pl.time, "monotonic", lambda: clock[0])
    p._on_enroll({"driverId": "d1", "action": "capture"})
    p._handle_enrollment(FRAME, FACE)
    p._handle_enrollment(FRAME, FACE)  # too soon after the first: not a new sample
    assert len(p.enroll["vectors"]) == 1
    for _ in range(pl.ENROLL_SAMPLES - 1):
        clock[0] += pl.ENROLL_SPACING
        p._handle_enrollment(FRAME, FACE)
    msg = last(p)
    assert msg["status"] == "done" and msg["ok"] is True
    assert len(msg["vector"]) == 128 and msg["photo"]
    assert p.enroll is None and p.verified is False


def test_capture_without_a_person_fails_with_warning(monkeypatch):
    p = make_pipeline()
    p._on_enroll({"driverId": "d1", "action": "capture"})
    clock = [1000.0]
    monkeypatch.setattr(pl.time, "monotonic", lambda: clock[0])
    p.enroll["deadline"] = 1000.5
    p._handle_enrollment(FRAME, None)
    clock[0] = 1001.0
    p._handle_enrollment(FRAME, None)
    msg = last(p)
    assert msg["status"] == "failed" and msg["error"] == pl.NO_PERSON


def test_cancel_stops_only_that_driver():
    p = make_pipeline()
    p._on_enroll({"driverId": "d1", "action": "preview"})
    p._on_enroll({"driverId": "other", "action": "cancel"})
    assert p.enroll is not None
    p._on_enroll({"driverId": "d1", "action": "cancel"})
    assert p.enroll is None
