"""Head pose (yaw, pitch, roll in degrees) via cv2.solvePnP.

Six landmarks are matched to a generic 3D face model; the camera matrix is
approximated from the image size, which is accurate enough for detecting a
30° look-away.
"""
from __future__ import annotations

import cv2
import numpy as np

# Generic face model in millimetres (nose tip at origin, +y up, +z towards camera).
MODEL_POINTS = np.array(
    [
        (0.0, 0.0, 0.0),  # nose tip
        (0.0, -63.6, -12.5),  # chin
        (-43.3, 32.7, -26.0),  # left eye outer corner (image left)
        (43.3, 32.7, -26.0),  # right eye outer corner
        (-28.9, -28.9, -24.1),  # left mouth corner
        (28.9, -28.9, -24.1),  # right mouth corner
    ],
    dtype=np.float64,
)
LANDMARK_IDS = (1, 152, 33, 263, 61, 291)


def camera_matrix(width: int, height: int) -> np.ndarray:
    f = float(width)
    return np.array([[f, 0, width / 2], [0, f, height / 2], [0, 0, 1]], dtype=np.float64)


def rotation_to_euler(rvec: np.ndarray) -> tuple[float, float, float]:
    """Return (yaw, pitch, roll) in degrees for a head facing the camera = (0, 0, 0)."""
    r, _ = cv2.Rodrigues(rvec)
    # Image y points down while the model's y points up; flip so pitch/yaw signs are intuitive.
    r = np.diag([1.0, -1.0, -1.0]) @ r
    sy = np.hypot(r[0, 0], r[1, 0])
    if sy > 1e-6:
        pitch = np.degrees(np.arctan2(r[2, 1], r[2, 2]))
        yaw = np.degrees(np.arctan2(-r[2, 0], sy))
        roll = np.degrees(np.arctan2(r[1, 0], r[0, 0]))
    else:
        pitch = np.degrees(np.arctan2(-r[1, 2], r[1, 1]))
        yaw = np.degrees(np.arctan2(-r[2, 0], sy))
        roll = 0.0
    return float(yaw), float(pitch), float(roll)


def estimate(points: np.ndarray, width: int, height: int) -> tuple[float, float, float] | None:
    image_points = points[list(LANDMARK_IDS)].astype(np.float64)
    ok, rvec, _ = cv2.solvePnP(
        MODEL_POINTS, image_points, camera_matrix(width, height), np.zeros(4), flags=cv2.SOLVEPNP_ITERATIVE
    )
    return rotation_to_euler(rvec) if ok else None
