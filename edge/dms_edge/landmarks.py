"""478-point face mesh landmarks in pixel space, plus MediaPipe blendshapes.

Two backends give the same points (MediaPipe's face_landmarks_detector model):

* LiteRT (Pi): YuNet finds the face, then the face mesh model from inside
  face_landmarker.task runs on a rotated, square crop. Later frames crop from the
  previous landmarks, as MediaPipe does; YuNet runs again when the face is lost
  and once a second to make sure tracking has not drifted to another face. Used
  on the Pi 4 because MediaPipe >= 1.0 wheels need the ARMv8 AES extension,
  which the Pi 4's Cortex-A72 lacks.
* MediaPipe Tasks (laptop): used when ai-edge-litert is not installed.

Both also return the 52 blendshape scores (eyeBlinkLeft/Right, jawOpen, …) from
the face_blendshapes model in the same .task file; the LiteRT path matches
MediaPipe's output exactly.
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
REDETECT_EVERY = 10  # frames between detector checks while tracking (~1 s)
DARK_MEAN = 80  # frames darker than this (0-255) are contrast-enhanced first

# Output order of face_blendshapes.tflite (ARKit names, as MediaPipe reports them).
BLEND_NAMES = [
    "_neutral", "browDownLeft", "browDownRight", "browInnerUp", "browOuterUpLeft", "browOuterUpRight",
    "cheekPuff", "cheekSquintLeft", "cheekSquintRight", "eyeBlinkLeft", "eyeBlinkRight", "eyeLookDownLeft",
    "eyeLookDownRight", "eyeLookInLeft", "eyeLookInRight", "eyeLookOutLeft", "eyeLookOutRight", "eyeLookUpLeft",
    "eyeLookUpRight", "eyeSquintLeft", "eyeSquintRight", "eyeWideLeft", "eyeWideRight", "jawForward", "jawLeft",
    "jawOpen", "jawRight", "mouthClose", "mouthDimpleLeft", "mouthDimpleRight", "mouthFrownLeft", "mouthFrownRight",
    "mouthFunnel", "mouthLeft", "mouthLowerDownLeft", "mouthLowerDownRight", "mouthPressLeft", "mouthPressRight",
    "mouthPucker", "mouthRight", "mouthRollLower", "mouthRollUpper", "mouthShrugLower", "mouthShrugUpper",
    "mouthSmileLeft", "mouthSmileRight", "mouthStretchLeft", "mouthStretchRight", "mouthUpperUpLeft",
    "mouthUpperUpRight", "noseSneerLeft", "noseSneerRight",
]
BLINK_LEFT, BLINK_RIGHT = BLEND_NAMES.index("eyeBlinkLeft"), BLEND_NAMES.index("eyeBlinkRight")

# The 146 mesh points the blendshape model reads (MediaPipe face_blendshapes_graph).
BLEND_INPUT = [
    0, 1, 4, 5, 6, 7, 8, 10, 13, 14, 17, 21, 33, 37, 39, 40, 46, 52, 53, 54, 55, 58, 61, 63, 65, 66, 67, 70, 78, 80,
    81, 82, 84, 87, 88, 91, 93, 95, 103, 105, 107, 109, 127, 132, 133, 136, 144, 145, 146, 148, 149, 150, 152, 153,
    154, 155, 157, 158, 159, 160, 161, 162, 163, 168, 172, 173, 176, 178, 181, 185, 191, 195, 197, 234, 246, 249,
    251, 263, 267, 269, 270, 276, 282, 283, 284, 285, 288, 291, 293, 295, 296, 297, 300, 308, 310, 311, 312, 314,
    317, 318, 321, 323, 324, 332, 334, 336, 338, 356, 361, 362, 365, 373, 374, 375, 377, 378, 379, 380, 381, 382,
    384, 385, 386, 387, 388, 389, 390, 397, 398, 400, 402, 405, 409, 415, 454, 466, 468, 469, 470, 471, 472, 473,
    474, 475, 476, 477,
]


@dataclass
class Face:
    points: np.ndarray  # (478, 2) pixel coordinates
    bbox: tuple[int, int, int, int]  # x, y, w, h
    blend: np.ndarray | None = None  # 52 blendshape scores (BLEND_NAMES order)

    # Five alignment points (viewer's left eye, right eye, nose, left mouth, right mouth)
    # in the order of the ArcFace 112x112 template used by SFace and the FER model.
    def five_points(self) -> np.ndarray:
        p = self.points
        left_eye = p[468] if len(p) > 468 else p[[33, 133]].mean(axis=0)
        right_eye = p[473] if len(p) > 473 else p[[362, 263]].mean(axis=0)
        return np.array([left_eye, right_eye, p[1], p[61], p[291]], dtype=np.float32)

    @property
    def eye_closure(self) -> float | None:
        """0 = eyes wide open … 1 = closed (mean of both eyeBlink scores)."""
        if self.blend is None:
            return None
        return float((self.blend[BLINK_LEFT] + self.blend[BLINK_RIGHT]) / 2)


def _face_from_points(pts: np.ndarray, blend=None) -> Face:
    x0, y0 = pts.min(axis=0)
    x1, y1 = pts.max(axis=0)
    return Face(pts, (int(x0), int(y0), int(x1 - x0), int(y1 - y0)), blend)


def enhance_if_dark(frame_bgr: np.ndarray) -> np.ndarray:
    """Local contrast enhancement (CLAHE on luminance) for dim cabins, so faces
    are still found at night or against a bright window."""
    small = cv2.resize(frame_bgr, (80, 60), interpolation=cv2.INTER_AREA)
    if small.mean() >= DARK_MEAN:
        return frame_bgr
    lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
    lab[:, :, 0] = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


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
            blend = z.read("face_blendshapes.tflite")
        self.it = Interpreter(model_content=mesh, num_threads=threads)
        self.it.allocate_tensors()
        self.inp = self.it.get_input_details()[0]["index"]
        outs = self.it.get_output_details()
        self.out_points = next(o["index"] for o in outs if int(np.prod(o["shape"])) == 478 * 3)
        self.out_presence = next(o["index"] for o in outs if o["shape"].tolist() == [1, 1, 1, 1])

        self.blend = Interpreter(model_content=blend, num_threads=1)
        self.blend.allocate_tensors()
        self.blend_in = self.blend.get_input_details()[0]["index"]
        self.blend_out = self.blend.get_output_details()[0]["index"]

        self.detector = cv2.FaceDetectorYN.create(str(yunet_path), "", (320, 320), 0.6, 0.3, 5)
        self.det_size = None
        self.prev: np.ndarray | None = None  # last landmarks, for tracking
        self.frames_tracked = 0

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

    def _blendshapes(self, pts):
        self.blend.set_tensor(self.blend_in, pts[BLEND_INPUT][None].astype(np.float32))
        self.blend.invoke()
        return self.blend.get_tensor(self.blend_out).reshape(-1).copy()

    def _drifted(self, frame, pts) -> tuple | None:
        """Every REDETECT_EVERY frames: if the detector's largest face is somewhere
        else than the tracked one (driver changed, tracking slid onto a passenger),
        return that face's ROI to switch to it."""
        self.frames_tracked += 1
        if self.frames_tracked % REDETECT_EVERY:
            return None
        roi = self._detect_roi(frame)
        if roi is None:
            return None  # detector miss: trust the mesh's own presence score
        (cx, cy), size, _ = roi
        (tx, ty), tsize, _ = self._roi_from_points(pts)
        far = math.hypot(cx - tx, cy - ty) > 0.5 * max(size, tsize)
        return roi if far or size > 1.5 * tsize else None

    def detect(self, frame_bgr, ts_ms):
        frame_bgr = enhance_if_dark(frame_bgr)
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pts = self._mesh(rgb, self._roi_from_points(self.prev)) if self.prev is not None else None
        if pts is not None:
            switch = self._drifted(frame_bgr, pts)
            if switch is not None:
                pts = self._mesh(rgb, switch)
        if pts is None:
            self.frames_tracked = 0
            roi = self._detect_roi(frame_bgr)
            pts = self._mesh(rgb, roi) if roi else None
        self.prev = pts
        return [_face_from_points(pts, self._blendshapes(pts))] if pts is not None else []

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
                output_face_blendshapes=True,
            )
        )
        self._last_ts = 0

    def detect(self, frame_bgr, ts_ms):
        ts_ms = max(ts_ms, self._last_ts + 1)  # VIDEO mode needs increasing timestamps
        self._last_ts = ts_ms
        rgb = cv2.cvtColor(enhance_if_dark(frame_bgr), cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(image, ts_ms)
        h, w = frame_bgr.shape[:2]
        faces = []
        for i, lms in enumerate(result.face_landmarks):
            pts = np.array([(lm.x * w, lm.y * h) for lm in lms], dtype=np.float32)
            cats = result.face_blendshapes[i] if result.face_blendshapes else None
            blend = np.array([c.score for c in cats], np.float32) if cats else None
            faces.append(_face_from_points(pts, blend))
        return faces

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
