"""478-point face mesh landmarks in pixel space.

Two backends give the same points (MediaPipe's face_landmarks_detector model):

* LiteRT (Pi): YuNet finds the face, then the face mesh model from inside
  face_landmarker.task runs on a rotated, square crop. Later frames crop from the
  previous landmarks, as MediaPipe does, and YuNet only runs again when the face
  is lost. Used on the Pi 4 because MediaPipe >= 1.0 wheels need the ARMv8 AES
  extension, which the Pi 4's Cortex-A72 lacks.
* MediaPipe Tasks (laptop): used when ai-edge-litert is not installed.
"""
from __future__ import annotations

import math
import zipfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

YUNET = "face_detection_yunet_2023mar.onnx"
MESH_SIZE = 256
ROI_SCALE = 1.5  # crop side = 1.5 x face size, as in MediaPipe's face landmark graph
PRESENCE_MIN = 0.5


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


def _face_from_points(pts: np.ndarray) -> Face:
    x0, y0 = pts.min(axis=0)
    x1, y1 = pts.max(axis=0)
    return Face(pts, (int(x0), int(y0), int(x1 - x0), int(y1 - y0)))


def roi_transform(center, size: float, angle: float) -> np.ndarray:
    """2x3 affine from crop pixels (0..MESH_SIZE) to image pixels.

    The crop is a square of side `size * ROI_SCALE` around `center`, rotated by
    `angle` (radians, image coordinates) so the eyes come out level.
    """
    s = size * ROI_SCALE / MESH_SIZE
    c, si = math.cos(angle) * s, math.sin(angle) * s
    half = MESH_SIZE / 2
    return np.array([
        [c, -si, center[0] - c * half + si * half],
        [si, c, center[1] - si * half - c * half],
    ], dtype=np.float64)


class _LiteRtMesh:
    def __init__(self, task_path: Path, yunet_path: Path, threads: int = 2):
        from ai_edge_litert.interpreter import Interpreter

        with zipfile.ZipFile(task_path) as z:
            mesh = z.read("face_landmarks_detector.tflite")
        self.it = Interpreter(model_content=mesh, num_threads=threads)
        self.it.allocate_tensors()
        self.inp = self.it.get_input_details()[0]["index"]
        outs = self.it.get_output_details()
        self.out_points = next(o["index"] for o in outs if int(np.prod(o["shape"])) == 478 * 3)
        self.out_presence = next(o["index"] for o in outs if o["shape"].tolist() == [1, 1, 1, 1])

        self.detector = cv2.FaceDetectorYN.create(str(yunet_path), "", (320, 320), 0.6, 0.3, 5)
        self.det_size = None
        self.prev: np.ndarray | None = None  # last landmarks, for tracking

    def _detect_roi(self, frame):
        h, w = frame.shape[:2]
        if self.det_size != (w, h):
            self.detector.setInputSize((w, h))
            self.det_size = (w, h)
        _, faces = self.detector.detect(frame)
        if faces is None or not len(faces):
            return None
        f = max(faces, key=lambda r: r[2] * r[3])
        x, y, fw, fh = f[:4]
        eye_a, eye_b = f[4:6], f[6:8]  # YuNet: subject's right eye (viewer's left), then left eye
        angle = math.atan2(eye_b[1] - eye_a[1], eye_b[0] - eye_a[0])
        return (x + fw / 2, y + fh / 2), max(fw, fh), angle

    @staticmethod
    def _roi_from_points(p):
        x0, y0 = p.min(axis=0)
        x1, y1 = p.max(axis=0)
        angle = math.atan2(p[263, 1] - p[33, 1], p[263, 0] - p[33, 0])
        return ((x0 + x1) / 2, (y0 + y1) / 2), max(x1 - x0, y1 - y0), angle

    def _mesh(self, rgb, roi):
        m = roi_transform(*roi)
        crop = cv2.warpAffine(rgb, m, (MESH_SIZE, MESH_SIZE),
                              flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_CONSTANT)
        self.it.set_tensor(self.inp, (crop.astype(np.float32) / 255.0)[None])
        self.it.invoke()
        presence = 1 / (1 + math.exp(-float(self.it.get_tensor(self.out_presence).ravel()[0])))
        if presence < PRESENCE_MIN:
            return None
        local = self.it.get_tensor(self.out_points).reshape(478, 3)[:, :2].astype(np.float64)
        return (local @ m[:, :2].T + m[:, 2]).astype(np.float32)

    def detect(self, frame_bgr, ts_ms):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pts = self._mesh(rgb, self._roi_from_points(self.prev)) if self.prev is not None else None
        if pts is None:
            roi = self._detect_roi(frame_bgr)
            pts = self._mesh(rgb, roi) if roi else None
        self.prev = pts
        return [_face_from_points(pts)] if pts is not None else []

    def close(self):
        pass


class _MediaPipeMesh:
    def __init__(self, task_path: Path, max_faces: int):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        self._mp = mp
        self._landmarker = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(task_path)),
                running_mode=vision.RunningMode.VIDEO,
                num_faces=max_faces,
                min_face_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        )
        self._last_ts = 0

    def detect(self, frame_bgr, ts_ms):
        ts_ms = max(ts_ms, self._last_ts + 1)  # VIDEO mode needs increasing timestamps
        self._last_ts = ts_ms
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(image, ts_ms)
        h, w = frame_bgr.shape[:2]
        return [_face_from_points(np.array([(lm.x * w, lm.y * h) for lm in lms], dtype=np.float32))
                for lms in result.face_landmarks]

    def close(self):
        self._landmarker.close()


class FaceLandmarks:
    def __init__(self, model_path: str, max_faces: int = 1, backend: str = "auto"):
        model_path = Path(model_path)
        yunet = model_path.parent / YUNET
        if backend == "auto":
            try:
                import ai_edge_litert  # noqa: F401
                backend = "litert" if yunet.exists() else "mediapipe"
            except ImportError:
                backend = "mediapipe"
        self.backend = backend
        self._impl = _LiteRtMesh(model_path, yunet) if backend == "litert" else _MediaPipeMesh(model_path, max_faces)

    def detect(self, frame_bgr: np.ndarray, ts_ms: int) -> list[Face]:
        faces = self._impl.detect(frame_bgr, ts_ms)
        # Largest face first: that is the driver closest to the camera.
        faces.sort(key=lambda f: f.bbox[2] * f.bbox[3], reverse=True)
        return faces

    def close(self):
        self._impl.close()
