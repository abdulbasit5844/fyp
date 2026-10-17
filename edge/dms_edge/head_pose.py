"""Head pose (yaw, pitch, roll in degrees) via cv2.solvePnP.

Six landmarks are matched to a generic 3D face model; the camera matrix is
approximated from the image size, which is accurate enough for detecting a
30° look-away.
"""
from __future__ import annotations

import zipfile

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


_canonical: tuple[np.ndarray, list[int]] | None = None


def _protobuf_fields(b: bytes):
    """Minimal protobuf reader (varint / fixed32 / length-delimited) for the
    geometry metadata, so no protobuf schema or library is needed."""
    def varint(i):
        r = s = 0
        while True:
            c = b[i]
            i += 1
            r |= (c & 0x7F) << s
            s += 7
            if c < 0x80:
                return r, i
    i = 0
    while i < len(b):
        key, i = varint(i)
        field, wire = key >> 3, key & 7
        if wire == 0:
            v, i = varint(i)
        elif wire == 5:
            v, i = b[i:i + 4], i + 4
        elif wire == 2:
            n, i = varint(i)
            v, i = b[i:i + n], i + n
        else:
            raise ValueError(f"unsupported wire type {wire}")
        yield field, v


def use_canonical(task_path) -> bool:
    """Use MediaPipe's own 3D face model (468 points, from face_landmarker.task)
    and the 33 stable landmarks it uses for pose. Much closer to MediaPipe's pose
    than the 6-point generic model (≈4° vs ≈14° yaw error on test faces)."""
    global _canonical
    try:
        with zipfile.ZipFile(task_path) as z:
            meta = z.read("geometry_pipeline_metadata_landmarks.binarypb")
        top = list(_protobuf_fields(meta))
        mesh = next(v for f, v in top if f == 1)
        verts = np.array([np.frombuffer(v, "<f4")[0] for f, v in _protobuf_fields(mesh) if f == 3])
        model = verts.reshape(-1, 5)[:, :3].astype(np.float64)  # x, y, z (cm); u, v dropped
        ids = [dict(_protobuf_fields(v)).get(1, 0) for f, v in top if f == 2]
        if model.shape != (468, 3) or len(ids) < 6:
            return False
        _canonical = (model[ids], ids)
        return True
    except (OSError, KeyError, StopIteration, ValueError):
        return False


def estimate(points: np.ndarray, width: int, height: int) -> tuple[float, float, float] | None:
    if _canonical is not None:
        model, ids = _canonical
        image_points = points[ids].astype(np.float64)
        eye_px = max(np.linalg.norm(points[33] - points[263]), 1.0)
        eye_cm = np.linalg.norm(model[ids.index(33)] - model[ids.index(263)]) if 33 in ids and 263 in ids else 8.9
        ok, rvec, _ = cv2.solvePnP(
            model, image_points, camera_matrix(width, height), np.zeros(4),
            np.array([[np.pi], [0.0], [0.0]]), np.array([[0.0], [0.0], [width * eye_cm / eye_px]]),
            True, cv2.SOLVEPNP_ITERATIVE,
        )
        return rotation_to_euler(rvec) if ok else None

    image_points = points[list(LANDMARK_IDS)].astype(np.float64)
    # Start from "facing the camera" at a plausible distance; without a guess the
    # iterative solver can settle on a mirrored pose (roll near ±180°).
    eye_px = max(np.linalg.norm(image_points[2] - image_points[3]), 1.0)
    rvec0 = np.array([[np.pi], [0.0], [0.0]])
    tvec0 = np.array([[0.0], [0.0], [width * (MODEL_POINTS[3, 0] - MODEL_POINTS[2, 0]) / eye_px]])
    ok, rvec, _ = cv2.solvePnP(
        MODEL_POINTS, image_points, camera_matrix(width, height), np.zeros(4),
        rvec0, tvec0, True, cv2.SOLVEPNP_ITERATIVE,
    )
    return rotation_to_euler(rvec) if ok else None
