"""Driver identity check with SFace embeddings (128-d, cosine similarity).

The embedding is computed on the Pi from an aligned 112x112 face and compared
against the enrolled drivers pushed by the backend on dms/{id}/drivers.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import onnxruntime as ort

MODEL_NAME = "sface-2021dec-128"


@dataclass
class Match:
    driver_id: str | None
    name: str | None
    authorized: bool
    score: float


class FaceEmbedder:
    def __init__(self, model_path: str):
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        opts.log_severity_level = 3  # hide initializer warnings from the zoo models
        self.session = ort.InferenceSession(str(model_path), opts, providers=["CPUExecutionProvider"])
        self.input = self.session.get_inputs()[0].name

    def embed(self, aligned_bgr: np.ndarray) -> np.ndarray:
        # SFace expects RGB, 0-255, NCHW, no normalisation.
        rgb = aligned_bgr[:, :, ::-1].astype(np.float32)
        blob = np.ascontiguousarray(rgb.transpose(2, 0, 1)[None])
        vec = self.session.run(None, {self.input: blob})[0].reshape(-1)
        return vec / (np.linalg.norm(vec) + 1e-9)


def best_match(vec: np.ndarray, drivers: list[dict], threshold: float) -> Match:
    """drivers: payload of dms/{id}/drivers. Returns the closest enrolled driver above threshold."""
    best = Match(None, None, False, -1.0)
    for d in drivers:
        for e in d.get("embeddings", []):
            ref = np.asarray(e["vector"], dtype=np.float32)
            if ref.shape != vec.shape:
                continue
            score = float(np.dot(vec, ref / (np.linalg.norm(ref) + 1e-9)))
            if score > best.score:
                best = Match(d["id"], d.get("displayName"), bool(d.get("isAuthorized", True)), score)
    if best.score < threshold:
        return Match(None, None, False, best.score)
    return best
