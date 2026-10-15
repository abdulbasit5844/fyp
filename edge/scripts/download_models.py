"""Download the pretrained models the edge pipeline needs into edge/models/.

  face_landmarker.task          MediaPipe face mesh (EAR + head pose landmarks)
  face_recognition_sface_*      SFace INT8, 128-d face embeddings (driver identity)
  facial_expression_*_int8      Fallback emotion model until the MobileNetV2 one is trained
"""
import sys
import urllib.request
from pathlib import Path

ZOO = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models"
MODELS = {
    "face_landmarker.task":
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
    "face_recognition_sface_2021dec_int8.onnx":
        f"{ZOO}/face_recognition_sface/face_recognition_sface_2021dec_int8.onnx",
    "facial_expression_recognition_mobilefacenet_2022july_int8.onnx":
        f"{ZOO}/facial_expression_recognition/facial_expression_recognition_mobilefacenet_2022july_int8.onnx",
}


def main(dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    for name, url in MODELS.items():
        target = dest / name
        if target.exists() and target.stat().st_size > 100_000:
            print(f"ok       {name}")
            continue
        print(f"download {name} ...", flush=True)
        tmp = target.with_suffix(".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(target)
    print("models ready in", dest)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "models")
