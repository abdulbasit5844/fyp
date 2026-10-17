"""Accuracy measures: per-driver calibration, smoothing, low-light enhancement and
identity quality gating."""
from pathlib import Path

import cv2
import numpy as np
import pytest

from dms_edge.calibration import DriverBaseline, Median3
from dms_edge.fusion import Fusion, Signals
from dms_edge.landmarks import enhance_if_dark
from dms_edge.settings import MonitorConfig

MODELS = Path(__file__).resolve().parent.parent / "models"


def calibrated(ear_open=0.30, closure_open=None, yaw0=0.0, pitch0=0.0, n=40):
    b = DriverBaseline(samples=n)
    rng = np.random.default_rng(1)
    for i in range(n):
        blink = i % 13 == 0  # a few blinks while calibrating
        ear = 0.08 if blink else ear_open + rng.normal(0, 0.01)
        closure = None if closure_open is None else (0.9 if blink else closure_open + rng.normal(0, 0.02))
        b.add(ear, closure, yaw0 + rng.normal(0, 2), pitch0 + rng.normal(0, 2))
    assert b.ready
    return b


def test_median3_removes_single_frame_glitch():
    m = Median3()
    out = [m(v) for v in (0.30, 0.31, 0.05, 0.30, 0.29)]
    assert min(out) > 0.25  # the one-frame 0.05 never gets through


def test_narrow_eyes_are_not_mistaken_for_closed_eyes():
    b = calibrated(ear_open=0.21)  # below the fixed 0.25 threshold even when wide open
    assert b.ear_open == pytest.approx(0.21, abs=0.01)
    assert b.eyes_closed(0.21, None, 0.25) is False  # fixed threshold would say closed
    assert b.eyes_closed(0.12, None, 0.25) is True


def test_blendshape_closure_is_judged_against_the_drivers_open_level():
    b = calibrated(closure_open=0.30)  # squinty driver: high blink score even when awake
    assert b.eyes_closed(0.30, 0.45, 0.25) is False  # 0.45 > the usual 0.4-0.5 cut-off
    assert b.eyes_closed(0.10, 0.80, 0.25) is True
    # A more sensitive setting (higher EAR threshold) closes the gap.
    assert b.eyes_closed(0.30, 0.61, 0.30) is True and b.eyes_closed(0.30, 0.61, 0.25) is False


def test_before_calibration_blendshapes_still_work():
    b = DriverBaseline()
    assert b.eyes_closed(0.3, 0.05, 0.25) is False
    assert b.eyes_closed(0.1, 0.85, 0.25) is True


def test_off_centre_camera_does_not_cause_inattention_alerts():
    b = calibrated(yaw0=22.0, pitch0=-10.0)  # camera mounted to the side and above
    cfg = MonitorConfig()
    fusion = Fusion(cfg)
    raised = []
    for i in range(60):  # 6 s of normal driving, seen from the side
        yaw, pitch = b.relative_pose(22.0 + (i % 5), -10.0)
        raised += fusion.update(Signals(True, 0.3, yaw, pitch, 0, eyes_closed=False), i * 0.1).raised
    assert raised == []
    for i in range(60, 120):  # now really looking away: 45° from their normal position
        yaw, pitch = b.relative_pose(67.0, -10.0)
        raised += fusion.update(Signals(True, 0.3, yaw, pitch, 0, eyes_closed=False), i * 0.1).raised
    assert [t.type for t in raised][:1] == ["inattention"]


def test_neutral_pose_is_capped():
    b = calibrated(yaw0=60.0)  # driver looked away the whole calibration: do not learn that
    assert b.yaw0 == 25.0


def test_fusion_uses_calibrated_eye_decision_over_fixed_ear():
    fusion = Fusion(MonitorConfig(earThreshold=0.25))
    raised = []
    for i in range(40):  # EAR 0.20 (< 0.25) but calibration says eyes are open
        raised += fusion.update(Signals(True, 0.20, 0, 0, 0, eyes_closed=False), i * 0.1).raised
    assert raised == []


def test_dark_frames_are_enhanced_and_bright_frames_left_alone():
    rng = np.random.default_rng(0)
    dark = rng.integers(0, 50, (120, 160, 3), dtype=np.uint8)
    out = enhance_if_dark(dark)
    assert out.std() > dark.std()  # more contrast
    bright = rng.integers(100, 255, (120, 160, 3), dtype=np.uint8)
    assert enhance_if_dark(bright) is bright


@pytest.mark.skipif(not (MODELS / "face_recognition_sface_2021dec_int8.onnx").exists(), reason="models not downloaded")
def test_identity_ignores_blurred_or_tiny_faces():
    lena = Path(__file__).resolve().parent / "data" / "face.jpg"
    if not lena.exists():
        pytest.skip("no test face image")
    from dms_edge import pipeline as pl
    from dms_edge.face_id import FaceEmbedder
    from dms_edge.landmarks import FaceLandmarks

    img = cv2.imread(str(lena))
    face = FaceLandmarks(MODELS / "face_landmarker.task").detect(img, 0)[0]
    p = object.__new__(pl.Pipeline)
    p.embedder = FaceEmbedder(MODELS / "face_recognition_sface_2021dec_int8.onnx")
    assert p._embedding(img, face) is not None
    assert p._embedding(cv2.GaussianBlur(img, (0, 0), 4.5), face) is None
    tiny = type(face)(face.points, (0, 0, 40, 40), face.blend)
    assert p._embedding(img, tiny) is None


# --- head pose with MediaPipe's canonical 3D face model ---

@pytest.fixture
def canonical(monkeypatch):
    from dms_edge import head_pose

    monkeypatch.setattr(head_pose, "_canonical", None)
    if not head_pose.use_canonical(MODELS / "face_landmarker.task"):
        pytest.skip("face_landmarker.task not downloaded")
    return head_pose


@pytest.mark.parametrize("yaw,pitch", [(0, 0), (30, 0), (-30, 0), (0, 20), (25, -15)])
def test_canonical_pose_recovers_rotation(canonical, yaw, pitch):
    model, ids = canonical._canonical
    w, h = 640, 480
    r_face = cv2.Rodrigues(np.array([np.radians(pitch), 0, 0]))[0] @ cv2.Rodrigues(np.array([0, np.radians(yaw), 0]))[0]
    rvec, _ = cv2.Rodrigues(np.diag([1.0, -1.0, -1.0]) @ r_face)
    img, _ = cv2.projectPoints(model, rvec, np.array([0.0, 0.0, 60.0]), canonical.camera_matrix(w, h), np.zeros(4))
    pts = np.zeros((478, 2))
    pts[ids] = img.reshape(-1, 2)
    est_yaw, est_pitch, _ = canonical.estimate(pts, w, h)
    assert abs(est_yaw) == pytest.approx(abs(yaw), abs=2.0)
    assert abs(est_pitch) == pytest.approx(abs(pitch), abs=2.0)


def test_canonical_pose_matches_mediapipe_on_a_real_face(canonical):
    img_path = Path(__file__).resolve().parent / "data" / "face.jpg"
    if not img_path.exists():
        pytest.skip("no test face image")
    from dms_edge.landmarks import FaceLandmarks

    img = cv2.imread(str(img_path))
    face = FaceLandmarks(MODELS / "face_landmarker.task").detect(img, 0)[0]
    yaw, pitch, _ = canonical.estimate(face.points, img.shape[1], img.shape[0])
    # MediaPipe's own facial transformation matrix says yaw 20.1°, pitch 11.8° here
    # (the 6-point model said 34.7°).
    assert abs(yaw) == pytest.approx(20.1, abs=5)
    assert abs(pitch) == pytest.approx(11.8, abs=5)
