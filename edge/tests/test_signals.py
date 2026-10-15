import cv2
import numpy as np
import pytest

from dms_edge import drowsiness, head_pose
from dms_edge.face_id import best_match
from dms_edge.gps import parse_nmea


# --- EAR (SRS 5.1: validated against known landmark coordinates) ---

def eye(width, height):
    """p1..p6 for an eye of the given width and opening."""
    return np.array([[0, 0], [width / 3, -height / 2], [2 * width / 3, -height / 2],
                     [width, 0], [2 * width / 3, height / 2], [width / 3, height / 2]], dtype=float)


def test_ear_known_values():
    assert drowsiness.eye_aspect_ratio(eye(30, 9)) == pytest.approx(0.30)
    assert drowsiness.eye_aspect_ratio(eye(30, 3)) == pytest.approx(0.10)
    assert drowsiness.eye_aspect_ratio(eye(30, 0)) == 0.0


def test_ear_degenerate_eye():
    assert drowsiness.eye_aspect_ratio(np.zeros((6, 2))) == 0.0


def test_face_ear_uses_both_eyes():
    pts = np.zeros((478, 2))
    pts[list(drowsiness.LEFT_EYE)] = eye(30, 9)
    pts[list(drowsiness.RIGHT_EYE)] = eye(30, 3) + 100
    assert drowsiness.face_ear(pts) == pytest.approx(0.20)


# --- head pose: project the 3D model with a known rotation, then recover it ---

@pytest.mark.parametrize("yaw,pitch", [(0, 0), (35, 0), (-35, 0), (0, 25), (0, -25), (20, 15)])
def test_head_pose_recovers_rotation(yaw, pitch):
    w, h = 640, 480
    # Rotation in the "face" frame, then the fixed flip between model (y up, z out) and camera axes.
    r_face = cv2.Rodrigues(np.array([np.radians(pitch), 0, 0]))[0] @ cv2.Rodrigues(np.array([0, np.radians(yaw), 0]))[0]
    r_cam = np.diag([1.0, -1.0, -1.0]) @ r_face
    rvec = cv2.Rodrigues(r_cam)[0]
    tvec = np.array([0.0, 0.0, 600.0])
    img, _ = cv2.projectPoints(head_pose.MODEL_POINTS, rvec, tvec, head_pose.camera_matrix(w, h), np.zeros(4))

    pts = np.zeros((478, 2))
    pts[list(head_pose.LANDMARK_IDS)] = img.reshape(-1, 2)
    est_yaw, est_pitch, _ = head_pose.estimate(pts, w, h)
    assert abs(est_yaw) == pytest.approx(abs(yaw), abs=2.0)
    assert abs(est_pitch) == pytest.approx(abs(pitch), abs=2.0)
    if yaw:
        assert np.sign(est_yaw) == np.sign(yaw)
    if pitch:
        assert np.sign(est_pitch) == np.sign(pitch)


# --- GPS (SRS 5.1: sample NMEA sentences) ---

def test_nmea_rmc():
    fix = parse_nmea("$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A")
    assert fix["lat"] == pytest.approx(48.1173, abs=1e-4)
    assert fix["lng"] == pytest.approx(11.5167, abs=1e-4)


def test_nmea_gga_south_west_with_accuracy():
    s = "GPGGA,092750.000,3340.8840,S,07302.8700,W,1,8,1.03,61.7,M,55.2,M,,"
    cs = 0
    for ch in s:
        cs ^= ord(ch)
    fix = parse_nmea(f"${s}*{cs:02X}")
    assert fix["lat"] == pytest.approx(-33.6814, abs=1e-4)
    assert fix["lng"] == pytest.approx(-73.0478, abs=1e-4)
    assert fix["accuracyM"] == pytest.approx(5.2, abs=0.1)


def test_nmea_rejects_no_fix_and_bad_checksum():
    assert parse_nmea("$GPRMC,123519,V,,,,,,,230394,,*00") is None
    assert parse_nmea("$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*00") is None
    assert parse_nmea("garbage") is None


# --- driver matching ---

def unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_best_match():
    rng = np.random.default_rng(0)
    a, b = unit(rng.normal(size=128)), unit(rng.normal(size=128))
    drivers = [
        {"id": "A", "displayName": "Ali", "isAuthorized": True, "embeddings": [{"vector": a.tolist()}]},
        {"id": "B", "displayName": "Bob", "isAuthorized": False, "embeddings": [{"vector": b.tolist()}]},
    ]
    probe = unit(a + 0.2 * rng.normal(size=128))
    m = best_match(probe, drivers, threshold=0.363)
    assert (m.driver_id, m.authorized) == ("A", True)

    assert best_match(unit(b + 0.1 * rng.normal(size=128)), drivers, 0.363).authorized is False
    assert best_match(unit(rng.normal(size=128)), drivers, 0.363).driver_id is None
