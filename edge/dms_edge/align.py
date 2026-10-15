"""Five-point face alignment to the standard 112x112 ArcFace template."""
from __future__ import annotations

import cv2
import numpy as np

# Viewer's left eye, right eye, nose tip, left mouth corner, right mouth corner.
ARCFACE_112 = np.array(
    [[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366], [41.5493, 92.3655], [70.7299, 92.2041]],
    dtype=np.float32,
)


def align_112(frame_bgr: np.ndarray, five_points: np.ndarray) -> np.ndarray | None:
    m, _ = cv2.estimateAffinePartial2D(five_points, ARCFACE_112, method=cv2.LMEDS)
    if m is None:
        return None
    return cv2.warpAffine(frame_bgr, m, (112, 112), borderValue=0)
