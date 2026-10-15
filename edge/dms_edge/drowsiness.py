"""Eye Aspect Ratio (Soukupová & Čech, 2016) on MediaPipe face-mesh landmarks.

EAR = (|p2-p6| + |p3-p5|) / (2 |p1-p4|)
Open eyes sit around 0.25-0.35; closed eyes fall below ~0.2.
"""
from __future__ import annotations

import numpy as np

# p1..p6 for each eye in MediaPipe's 468-point mesh (outer corner, two upper,
# inner corner, two lower), matching the dlib 68-point ordering.
LEFT_EYE = (33, 160, 158, 133, 153, 144)
RIGHT_EYE = (362, 385, 387, 263, 373, 380)


def eye_aspect_ratio(eye: np.ndarray) -> float:
    """eye: (6, 2) array of p1..p6."""
    p1, p2, p3, p4, p5, p6 = eye
    horizontal = np.linalg.norm(p1 - p4)
    if horizontal < 1e-6:
        return 0.0
    return float((np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)) / (2.0 * horizontal))


def face_ear(points: np.ndarray) -> float:
    """Mean EAR of both eyes from a (N, 2) landmark array."""
    left = eye_aspect_ratio(points[list(LEFT_EYE)])
    right = eye_aspect_ratio(points[list(RIGHT_EYE)])
    return (left + right) / 2.0
