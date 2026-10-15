"""Train the MobileNetV2 emotion classifier on FER-2013 and export it as INT8 ONNX.

Dataset layout (Kaggle "msambare/fer2013"):
    fer2013/train/{angry,disgust,fear,happy,neutral,sad,surprise}/*.jpg
    fer2013/test/{...}/*.jpg

Run on a laptop GPU or Google Colab:
    pip install -r training/requirements.txt
    python training/train_emotion.py --data fer2013 --epochs 30

Outputs (copy both to edge/models/ on the Pi):
    emotion_mobilenetv2_int8.onnx   static INT8 (QDQ, per-channel) model
    emotion_mobilenetv2_int8.json   preprocessing metadata read by dms_edge/emotion.py
    report.json                     accuracy / precision / recall / F1 / confusion matrix (SRS 4.2)
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, models, transforms

LABELS = ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"]
SIZE = 112
MEAN, STD = [0.5] * 3, [0.5] * 3


def loaders(root: Path, batch: int):
    train_tf = transforms.Compose([
        transforms.Grayscale(3),  # FER is grayscale; the Pi feeds RGB crops converted the same way
        transforms.Resize(SIZE),
        transforms.RandomResizedCrop(SIZE, scale=(0.8, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ColorJitter(0.3, 0.3),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD),
    ])
    test_tf = transforms.Compose([
        transforms.Grayscale(3), transforms.Resize((SIZE, SIZE)), transforms.ToTensor(), transforms.Normalize(MEAN, STD),
    ])
    train = datasets.ImageFolder(root / "train", train_tf)
    test = datasets.ImageFolder(root / "test", test_tf)
    assert train.classes == LABELS, f"unexpected class folders: {train.classes}"

    # Class weights offset FER-2013's imbalance (very few "disgust" images).
    counts = np.bincount(train.targets, minlength=len(LABELS))
    weights = torch.tensor(counts.sum() / (len(LABELS) * counts), dtype=torch.float32)
    kw = dict(batch_size=batch, num_workers=4, pin_memory=torch.cuda.is_available())
    return DataLoader(train, shuffle=True, **kw), DataLoader(test, **kw), test, weights


def build_model():
    m = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
    m.classifier = nn.Sequential(nn.Dropout(0.3), nn.Linear(m.last_channel, len(LABELS)))
    return m


def evaluate(predict, loader):
    y_true, y_pred = [], []
    for x, y in loader:
        y_pred += predict(x).tolist()
        y_true += y.tolist()
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    cm = np.zeros((len(LABELS), len(LABELS)), int)
    for t, p in zip(y_true, y_pred):
        cm[t, p] += 1
    per_class = {}
    for i, name in enumerate(LABELS):
        tp, fp, fn = cm[i, i], cm[:, i].sum() - cm[i, i], cm[i, :].sum() - cm[i, i]
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per_class[name] = {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4)}
    return {
        "accuracy": round(float((y_true == y_pred).mean()), 4),
        "macro_f1": round(float(np.mean([c["f1"] for c in per_class.values()])), 4),
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
    }


def train(args):
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_dl, test_dl, test_ds, weights = loaders(Path(args.data), args.batch)
    model = build_model().to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, args.lr, epochs=args.epochs, steps_per_epoch=len(train_dl))
    loss_fn = nn.CrossEntropyLoss(weight=weights.to(dev), label_smoothing=0.1)

    best, best_state = 0.0, None
    for epoch in range(args.epochs):
        model.train()
        t0, total = time.time(), 0.0
        for x, y in train_dl:
            x, y = x.to(dev), y.to(dev)
            opt.zero_grad()
            loss = loss_fn(model(x), y)
            loss.backward()
            opt.step()
            sched.step()
            total += loss.item()
        model.eval()
        with torch.no_grad():
            acc = evaluate(lambda x: model(x.to(dev)).argmax(1).cpu(), test_dl)["accuracy"]
        print(f"epoch {epoch + 1:02d}/{args.epochs} loss {total / len(train_dl):.4f} test acc {acc:.4f} "
              f"({time.time() - t0:.0f}s)")
        if acc > best:
            best, best_state = acc, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    return model.cpu().eval(), test_dl, test_ds


def export(model, test_ds, test_dl, out: Path):
    import onnxruntime as ort
    from onnxruntime.quantization import (CalibrationDataReader, QuantFormat, QuantType, quantize_static)
    from onnxruntime.quantization.shape_inference import quant_pre_process

    out.mkdir(parents=True, exist_ok=True)
    fp32, prep, int8 = out / "emotion_mobilenetv2_fp32.onnx", out / "emotion_prep.onnx", out / "emotion_mobilenetv2_int8.onnx"
    torch.onnx.export(model, torch.randn(1, 3, SIZE, SIZE), fp32, input_names=["input"], output_names=["logits"],
                      opset_version=17, dynamic_axes={"input": {0: "n"}, "logits": {0: "n"}},
                      dynamo=False)  # classic exporter: one self-contained file, quantizes cleanly
    quant_pre_process(str(fp32), str(prep))

    class Calib(CalibrationDataReader):
        def __init__(self):
            idx = np.random.default_rng(0).choice(len(test_ds), size=min(500, len(test_ds)), replace=False)
            self.it = iter(DataLoader(Subset(test_ds, idx.tolist()), batch_size=1))

        def get_next(self):
            batch = next(self.it, None)
            return None if batch is None else {"input": batch[0].numpy()}

    quantize_static(str(prep), str(int8), Calib(), quant_format=QuantFormat.QDQ, per_channel=True,
                    activation_type=QuantType.QUInt8, weight_type=QuantType.QInt8)
    prep.unlink(missing_ok=True)

    report = {}
    for name, path in (("fp32", fp32), ("int8", int8)):
        sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        report[name] = evaluate(lambda x: torch.from_numpy(sess.run(None, {"input": x.numpy()})[0].argmax(1)), test_dl)
        x = np.random.rand(1, 3, SIZE, SIZE).astype(np.float32)
        t0 = time.perf_counter()
        for _ in range(50):
            sess.run(None, {"input": x})
        report[name]["latency_ms_this_machine"] = round((time.perf_counter() - t0) * 20, 2)
        report[name]["size_mb"] = round(path.stat().st_size / 1e6, 2)
        print(f"{name}: acc {report[name]['accuracy']:.4f}, macro F1 {report[name]['macro_f1']:.4f}, "
              f"{report[name]['size_mb']} MB, {report[name]['latency_ms_this_machine']} ms")

    meta = {"input": "crop", "size": SIZE, "color": "rgb", "mean": MEAN, "std": STD, "labels": LABELS}
    int8.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    (out / "report.json").write_text(json.dumps(report, indent=2))
    print("wrote", int8, "and", out / "report.json")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # the ONNX exporter prints emoji; Windows consoles choke on them
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="FER-2013 folder with train/ and test/")
    ap.add_argument("--out", default="training/output")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--lr", type=float, default=3e-3)
    a = ap.parse_args()
    m, dl, ds = train(a)
    torch.save(m.state_dict(), Path(a.out).mkdir(parents=True, exist_ok=True) or Path(a.out) / "emotion_mobilenetv2.pt")
    export(m, ds, dl, Path(a.out))
