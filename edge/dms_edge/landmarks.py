"""MediaPipe FaceLandmarker wrapper returning pixel-space landmarks."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Face:
    points: np.ndarray  # (478, 2) pixel coordinates
    bbox: tuple[int, int, int, int]  # x, y, w, h

    # Five alignment points (viewer's left eye, right eye, nose, left mouth, right mouth)
    # in the order of the ArcFace 112x112 template used by SFace and the FER model.
    def five_points(self) -> np.ndarray:
        p = self.points
        left_eye = p[468] if len(p) > 468 else p[[33, 133]].mean(axis=0)
        right_eye = p[473] if len(p) > 473 else p[[362, 263]].mean(axis=0)
        return np.array([left_eye, right_eye, p[1], p[61], p[291]], dtype=np.float32)


class FaceLandmarks:
    def __init__(self, model_path: str, max_faces: int = 1):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        self._mp = mp
        self._landmarker = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(model_path)),
                running_mode=vision.RunningMode.VIDEO,
                num_faces=max_faces,
                min_face_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        )
        self._last_ts = 0

    def detect(self, frame_bgr: np.ndarray, ts_ms: int) -> list[Face]:
        ts_ms = max(ts_ms, self._last_ts + 1)  # VIDEO mode needs increasing timestamps
        self._last_ts = ts_ms
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(image, ts_ms)

        h, w = frame_bgr.shape[:2]
        faces = []
        for lms in result.face_landmarks:
            pts = np.array([(lm.x * w, lm.y * h) for lm in lms], dtype=np.float32)
            x0, y0 = pts.min(axis=0)
            x1, y1 = pts.max(axis=0)
            faces.append(Face(pts, (int(x0), int(y0), int(x1 - x0), int(y1 - y0))))
        # Largest face first: that is the driver closest to the camera.
        faces.sort(key=lambda f: f.bbox[2] * f.bbox[3], reverse=True)
        return faces

    def close(self):
        self._landmarker.close()
