"""Seven-class emotion classifier running on ONNX Runtime.

Model: the pretrained OpenCV-Zoo MobileFaceNet facial-expression model,
quantized to INT8 (downloaded by scripts/download_models.py).

Optional: a custom MobileNetV2 trained with training/train_emotion.py
(emotion_mobilenetv2_int8.onnx + .json) takes precedence if placed in the
models folder.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from .align import align_112

LABELS = ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"]

CANDIDATES = [
    ("emotion_mobilenetv2_int8.onnx", None),  # metadata from the matching .json
    (
        "facial_expression_recognition_mobilefacenet_2022july_int8.onnx",
        {"input": "aligned112", "size": 112, "color": "rgb", "mean": [0.5] * 3, "std": [0.5] * 3, "labels": LABELS},
    ),
]


class EmotionClassifier:
    def __init__(self, models_dir: Path):
        for name, meta in CANDIDATES:
            path = Path(models_dir) / name
            if path.exists():
                break
        else:
            raise FileNotFoundError(f"no emotion model in {models_dir}; run scripts/download_models.py")

        self.meta = meta or json.loads(path.with_suffix(".json").read_text())
        self.name = path.name
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        opts.log_severity_level = 3  # hide initializer warnings from the zoo models
        self.session = ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])
        self.input = self.session.get_inputs()[0].name
        self.labels = self.meta["labels"]

    def _preprocess(self, frame_bgr, face) -> np.ndarray | None:
        size = self.meta["size"]
        if self.meta["input"] == "aligned112":
            img = align_112(frame_bgr, face.five_points())
            if img is None:
                return None
        else:  # "crop": square crop around the face bbox with a margin
            x, y, w, h = face.bbox
            s = int(max(w, h) * 1.2)
            cx, cy = x + w // 2, y + h // 2
            x0, y0 = max(cx - s // 2, 0), max(cy - s // 2, 0)
            img = frame_bgr[y0:y0 + s, x0:x0 + s]
            if img.size == 0:
                return None
            img = cv2.resize(img, (size, size))

        if self.meta["color"] == "gray":
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)[:, :, None]
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        x = img.astype(np.float32) / 255.0
        x = (x - np.array(self.meta["mean"], np.float32)) / np.array(self.meta["std"], np.float32)
        return np.ascontiguousarray(x.transpose(2, 0, 1)[None])

    def predict(self, frame_bgr, face) -> tuple[str, float, dict] | None:
        blob = self._preprocess(frame_bgr, face)
        if blob is None:
            return None
        logits = self.session.run(None, {self.input: blob})[0].reshape(-1).astype(np.float64)
        probs = np.exp(logits - logits.max())
        probs /= probs.sum()
        i = int(probs.argmax())
        return self.labels[i], float(probs[i]), dict(zip(self.labels, probs.round(3).tolist()))
