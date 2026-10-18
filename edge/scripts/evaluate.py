"""Evidence for the report: precision, recall and detection delay of the
drowsiness rules, and head-pose angle error against ground truth.

  python scripts/evaluate.py simulate [--sessions 40] [--fps 10]
      Simulated drives with known ground truth (microsleeps, nods, yawns, phone
      glances, long blinks, alert vs fatigued drivers) through the real
      calibration → smoothing → fusion chain. Compares the 2 s EAR rule alone
      with the refinements (nod detection, yawn handling, PERCLOS / blink trends).
  python scripts/evaluate.py headpose --aflw path/to/AFLW2000
      AFLW2000-3D (2000 faces with yaw / pitch / roll ground truth): MediaPipe
      landmarks → solvePnP with the canonical 468-point model vs the generic
      6-point model, and MediaPipe's own transformation matrix for reference.
  python scripts/evaluate.py eyes --dir path/with/open_and_closed_subfolders
      Frame-level eye state on full-face images (e.g. CEW). MRL Eye images are
      eye crops without a face, so the face mesh cannot run on them.
  python scripts/evaluate.py video --video clip.mp4 --labels labels.txt
      Labelled driving video (NTHU-DDD per-frame 0/1 label file, or a CSV of
      start,end seconds): event precision, recall and delay on real footage.

Add --out report.md to any mode to save the tables.
"""
from __future__ import annotations

import argparse
import glob
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dms_edge.calibration import DriverBaseline, Median3  # noqa: E402
from dms_edge.fusion import Fusion, Signals  # noqa: E402
from dms_edge.settings import MonitorConfig  # noqa: E402

MODELS = ROOT / "models"
MATCH_AFTER_SEC = 1.0  # a detection this long after an episode ends still counts


# --- scoring ---

@dataclass
class Episode:
    kind: str
    start: float
    end: float
    positive: bool  # ground truth: should raise a drowsiness alert


def score(episodes: list[Episode], detections: list[float]) -> dict:
    """Event-level matching: each positive episode is detected by the first alert
    inside [start, end + MATCH_AFTER_SEC]; every other alert is a false positive,
    attributed to the distractor it overlapped (if any)."""
    pos = [e for e in episodes if e.positive]
    delays, matched, fp_by = {}, set(), {}
    for t in sorted(detections):
        hit = next((i for i, e in enumerate(pos) if i not in matched and e.start <= t <= e.end + MATCH_AFTER_SEC), None)
        if hit is not None:
            matched.add(hit)
            delays.setdefault(pos[hit].kind, []).append(t - pos[hit].start)
            continue
        if any(e.start <= t <= e.end + MATCH_AFTER_SEC for i, e in enumerate(pos) if i in matched):
            continue  # a second alert for an episode already counted: not a new false alarm
        cause = next((e.kind for e in episodes if not e.positive and e.start <= t <= e.end + MATCH_AFTER_SEC), "other")
        fp_by[cause] = fp_by.get(cause, 0) + 1
    tp, fp = len(matched), sum(fp_by.values())
    return {"tp": tp, "fp": fp, "fn": len(pos) - tp, "delays": delays, "fp_by": fp_by,
            "missed_by": _count(pos[i].kind for i in range(len(pos)) if i not in matched)}


def _count(items) -> dict:
    out = {}
    for k in items:
        out[k] = out.get(k, 0) + 1
    return out


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f = 2 * p * r / (p + r) if p + r else float("nan")
    return p, r, f


# --- the pipeline's signal chain, without the camera ---

class Chain:
    """Calibration and smoothing as in Pipeline._analyse, then fusion."""

    def __init__(self, cfg=None, refinements=True):
        self.cfg = cfg or MonitorConfig()
        self.fusion = Fusion(self.cfg)
        self.baseline = DriverBaseline()
        self.smooth = {k: Median3() for k in ("ear", "mouth", "pitch")}
        self.refinements = refinements
        if not refinements:  # no PERCLOS / blink / yawn fatigue state either
            self.fusion.fatigue.fatigue_reason = lambda: None

    def step(self, t, face, ear, mouth, pitch):
        if not face:
            for f in self.smooth.values():
                f.reset()
            return self.fusion.update(Signals(False), t)
        ear, mouth, pitch = self.smooth["ear"](ear), self.smooth["mouth"](mouth), self.smooth["pitch"](pitch)
        if not self.baseline.ready:
            self.baseline.add(ear, None, 0.0, pitch, 0.0)
        _, rel_pitch, _ = self.baseline.relative_pose(0.0, pitch, 0.0)
        closed = self.baseline.eyes_closed(ear, None, self.cfg.earThreshold)
        if not self.refinements:  # the 2 s EAR rule alone: no mouth or nod information
            mouth, rel_pitch = None, 0.0
        return self.fusion.update(Signals(True, ear, 0.0, rel_pitch, 0.0, eyes_closed=closed, mouth_open=mouth), t)


# --- simulated drives ---

def _place(rng, busy, length, total, margin=4.0):
    for _ in range(500):
        s = rng.uniform(12.0, total - length - 2.0)
        if all(s + length + margin < a or s > b + margin for a, b in busy):
            busy.append((s, s + length))
            return s
    return None


DROWSY_DRIVE = {"microsleep": 3, "head nod": 2, "yawn": 2, "phone glance": 3, "long blink": 4}
ALERT_DRIVE = {"microsleep": 0, "head nod": 0, "yawn": 1, "phone glance": 3, "long blink": 4}


def simulate_session(rng, fps=10.0, minutes=5.0, fatigued=False, mix=None):
    """One drive. Returns (frames, episodes); frames = list of (t, face, ear, mouth, pitch).
    mix: how many of each scripted episode (DROWSY_DRIVE by default)."""
    mix = mix or DROWSY_DRIVE
    total = minutes * 60
    t = np.cumsum(rng.normal(1 / fps, 0.1 / fps, int(total * fps)).clip(0.5 / fps))
    n = len(t)
    closed = np.zeros(n, bool)
    ear_factor = np.ones(n)
    mouth = 0.05 + np.abs(rng.normal(0, 0.03, n))
    pitch = rng.normal(0, 1.5, n)
    face = rng.random(n) > 0.003  # occasional missed detection
    busy, episodes = [], []

    def span(a, b):
        return (t >= a) & (t < b)

    def add(kind, length, positive):
        s = _place(rng, busy, length, total)
        if s is not None:
            episodes.append(Episode(kind, s, s + length, positive))
        return s

    for _ in range(mix["microsleep"]):  # microsleeps: eyes shut 2.5-6 s
        d = rng.uniform(2.5, 6.0)
        s = add("microsleep", d, True)
        if s is not None:
            closed[span(s, s + d)] = True
    for _ in range(mix["head nod"]):  # nods: a short closure, then the head drops
        d, drop = rng.uniform(1.0, 1.8), rng.uniform(18, 30)
        s = add("head nod", d, True)
        if s is not None:
            closed[span(s, s + d)] = True
            m = span(s + 0.2, s + d)
            pitch[m] += np.minimum(drop, drop * (t[m] - s - 0.2) / 0.4)
    for _ in range(mix["yawn"]):  # yawns: mouth wide, eyes squeezed shut in the middle
        d = rng.uniform(3.5, 6.0)
        s = add("yawn", d, False)
        if s is not None:
            mouth[span(s, s + d)] = rng.uniform(0.6, 0.9)
            sq = rng.uniform(1.5, 3.0)
            closed[span(s + (d - sq) / 2, s + (d + sq) / 2)] = True
    for _ in range(mix["phone glance"]):  # phone glances: head down, lids lowered
        d = rng.uniform(2.0, 5.0)
        s = add("phone glance", d, False)
        if s is not None:
            pitch[span(s, s + d)] += rng.uniform(25, 35)
            ear_factor[span(s, s + d)] = rng.uniform(0.75, 0.85)
    for _ in range(mix["long blink"]):
        d = rng.uniform(0.5, 1.2)
        s = add("long blink", d, False)
        if s is not None:
            closed[span(s, s + d)] = True

    # Ordinary blinks (and, for a fatigued driver, slower blinks and frequent long closures).
    rate, median = (20, 0.3) if fatigued else (15, 0.15)
    for start in np.cumsum(rng.exponential(60 / rate, int(total * rate / 60 * 1.5))):
        d = float(np.clip(rng.lognormal(math.log(median), 0.35), 0.06, 0.45))
        if 10 < start < total - 1 and not any(a - 1 < start < b + 1 for a, b in busy):
            closed[span(start, start + d)] = True
    if fatigued:
        for start in np.cumsum(rng.exponential(60 / 8, int(total * 8 / 60))):
            d = rng.uniform(0.6, 1.6)
            if 10 < start < total - 2 and not any(a - 1 < start < b + 1 for a, b in busy):
                closed[span(start, start + d)] = True

    open_ear = rng.uniform(0.24, 0.34)
    ear = np.where(closed, rng.normal(0.08, 0.02, n), open_ear * ear_factor) + rng.normal(0, 0.012, n)
    glitch = rng.random(n) < 0.01  # single-frame landmark glitches
    ear[glitch] = 0.1
    frames = list(zip(t, face, ear.clip(0.0), mouth, pitch))
    return frames, episodes


def run_session(frames, refinements=True, cfg=None):
    chain = Chain(cfg, refinements)
    alerts, fatigue_at = [], None
    for t, face, ear, mouth, pitch in frames:
        r = chain.step(float(t), bool(face), float(ear), float(mouth), float(pitch))
        for trig in r.raised:
            if trig.type == "drowsiness" and trig.severity == "critical":
                alerts.append(float(t))
            elif trig.type == "fatigue" and fatigue_at is None:
                fatigue_at = float(t)
    return alerts, fatigue_at


def simulate(sessions=40, fps=10.0, seed=7, minutes=5.0):
    rng = np.random.default_rng(seed)
    data = [simulate_session(rng, fps, minutes) for _ in range(sessions)]
    results = {}
    for name, refine in (("2 s EAR rule only", False), ("with refinements", True)):
        tot = {"tp": 0, "fp": 0, "fn": 0, "delays": {}, "fp_by": {}, "missed_by": {}}
        for frames, episodes in data:
            alerts, _ = run_session(frames, refine)
            s = score(episodes, alerts)
            for k in ("tp", "fp", "fn"):
                tot[k] += s[k]
            for k, v in s["delays"].items():
                tot["delays"].setdefault(k, []).extend(v)
            for key in ("fp_by", "missed_by"):
                for k, v in s[key].items():
                    tot[key][k] = tot[key].get(k, 0) + v
        results[name] = tot

    # Fatigue: half alert, half fatigued drivers; a session counts as flagged if a fatigue warning is raised.
    fat = {"alert": [], "fatigued": []}
    for i in range(sessions):
        kind = "fatigued" if i % 2 else "alert"
        frames, _ = simulate_session(rng, fps, minutes, fatigued=kind == "fatigued", mix=ALERT_DRIVE)
        fat[kind].append(run_session(frames, True)[1])
    return {"drowsiness": results, "fatigue": fat, "sessions": sessions, "fps": fps, "minutes": minutes}


def simulate_report(res) -> str:
    hours = res["sessions"] * res["minutes"] / 60
    out = [f"### Drowsiness alerts on simulated drives ({res['sessions']} drives x {res['minutes']:.0f} min, "
           f"{res['fps']:.0f} fps)\n",
           "Each drive has 3 microsleeps (eyes shut 2.5-6 s) and 2 head nods (eyes shut 1-1.8 s, head drops "
           "18-30°) that should alert, plus 2 yawns with eyes squeezed shut for 1.5-3 s, 3 phone glances "
           "(head down 25-35°, eyelids lowered) and 4 long blinks (0.5-1.2 s) that should not, among normal "
           "blinks (15/min), EAR noise, single-frame landmark glitches and missed detections. A long blink can "
           "still alert when the driver is already in a fatigue warning (fatigue + 1 s closure = critical); "
           "those count as false alarms here.\n",
           "| Rules | TP | FP | FN | Precision | Recall | F1 | False alarms / h | Delay microsleep (median / p95) "
           "| Delay nod (median) |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for name, r in res["drowsiness"].items():
        p, rc, f = prf(r["tp"], r["fp"], r["fn"])
        ms = r["delays"].get("microsleep", [])
        nod = r["delays"].get("head nod", [])
        out.append(f"| {name} | {r['tp']} | {r['fp']} | {r['fn']} | {p:.3f} | {rc:.3f} | {f:.3f} | "
                   f"{r['fp'] / hours:.1f} | "
                   + (f"{np.median(ms):.2f} s / {np.percentile(ms, 95):.2f} s" if ms else "-") + " | "
                   + (f"{np.median(nod):.2f} s" if nod else "missed") + " |")
    out.append("")
    for name, r in res["drowsiness"].items():
        out.append(f"* {name}: false alarms by cause {r['fp_by'] or '{}'}; missed {r['missed_by'] or '{}'}")
    f = res["fatigue"]
    flagged = [x for x in f["fatigued"] if x is not None]
    false = [x for x in f["alert"] if x is not None]
    out += ["", "### Fatigue warning (PERCLOS / slow blinks / yawns) per drive\n",
            "Separate drives without microsleeps: 1 yawn, 3 phone glances and 4 long blinks each.\n",
            "| Drivers | Drives | Flagged | Rate | Time to first warning (median) |", "|---|---|---|---|---|",
            "| fatigued: 20 blinks/min (median 300 ms), 8 closures/min of 0.6-1.6 s "
            f"| {len(f['fatigued'])} | {len(flagged)} | {len(flagged) / max(1, len(f['fatigued'])):.2f} | "
            + (f"{np.median(flagged):.0f} s" if flagged else "-") + " |",
            f"| alert: 15 blinks/min (median 150 ms) | {len(f['alert'])} | {len(false)} | "
            f"{len(false) / max(1, len(f['alert'])):.2f} | - |", ""]
    return "\n".join(out)


# --- head pose on AFLW2000-3D ---

def _mp_landmarker(transform=True):
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    return mp, vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODELS / "face_landmarker.task")),
        running_mode=vision.RunningMode.IMAGE, num_faces=1,
        output_face_blendshapes=True, output_facial_transformation_matrixes=transform))


def headpose(aflw_dir: str, limit: int | None = None) -> dict:
    import cv2
    import scipy.io as sio

    from dms_edge import head_pose

    if not head_pose.use_canonical(MODELS / "face_landmarker.task"):
        raise SystemExit("face_landmarker.task not found")
    canonical = head_pose._canonical
    mp, lm = _mp_landmarker()
    files = sorted(glob.glob(str(Path(aflw_dir) / "*.jpg")))[:limit]
    rows, missed = [], 0
    t0 = time.perf_counter()
    for f in files:
        gt = np.degrees(sio.loadmat(f[:-4] + ".mat")["Pose_Para"][0, :3])  # pitch, yaw, roll
        img = cv2.imread(f)
        h, w = img.shape[:2]
        res = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
        if not res.face_landmarks:
            missed += 1
            continue
        pts = np.array([(p.x * w, p.y * h) for p in res.face_landmarks[0]], np.float32)
        est = {}
        head_pose._canonical = canonical
        est["canonical (33 pts)"] = head_pose.estimate(pts, w, h)
        head_pose._canonical = None
        est["generic 6-point"] = head_pose.estimate(pts, w, h)
        head_pose._canonical = canonical
        m = np.array(res.facial_transformation_matrixes[0])[:3, :3]
        rvec, _ = cv2.Rodrigues(np.diag([1.0, -1.0, -1.0]) @ m)  # OpenGL camera → OpenCV camera
        est["MediaPipe matrix"] = head_pose.rotation_to_euler(rvec)
        rows.append((gt[[1, 0, 2]], {k: np.array(v) if v else None for k, v in est.items()}))  # → yaw, pitch, roll
    return {"rows": rows, "missed": missed, "n": len(files), "sec": time.perf_counter() - t0}


def headpose_report(res) -> str:
    rows = res["rows"]
    methods = list(rows[0][1]) if rows else []
    gt = np.array([g for g, _ in rows])
    # AFLW2000's angle signs differ from ours; one sign per axis is fixed from the
    # canonical model's correlation with the ground truth and applied to every method.
    ref = np.array([e[methods[0]] for _, e in rows])
    signs = np.sign([np.corrcoef(ref[:, i], gt[:, i])[0, 1] for i in range(3)])
    out = [f"### Head pose error on AFLW2000-3D ({len(rows)} of {res['n']} faces; "
           f"{res['missed']} not detected by MediaPipe)\n",
           f"Mean absolute error in degrees (axis signs aligned to the dataset: yaw {signs[0]:+.0f}, "
           f"pitch {signs[1]:+.0f}, roll {signs[2]:+.0f}).\n"]
    subsets = [
        ("all angles within ±99° (standard protocol)", np.all(np.abs(gt) <= 99, axis=1)),
        ("driver range: |yaw| and |pitch| ≤ 45°", (np.abs(gt[:, 0]) <= 45) & (np.abs(gt[:, 1]) <= 45)),
        ("near frontal: |yaw| and |pitch| ≤ 20°", (np.abs(gt[:, 0]) <= 20) & (np.abs(gt[:, 1]) <= 20)),
    ]
    for title, keep in subsets:
        out += [f"**{title}**, {int(keep.sum())} faces\n",
                "| Method | Yaw MAE | Pitch MAE | Roll MAE | Mean | Yaw error ≤ 10° |", "|---|---|---|---|---|---|"]
        for m in methods:
            ok = np.array([e[m] is not None for _, e in rows]) & keep
            est = np.array([e[m] * signs for _, e in rows if e[m] is not None])
            err = np.abs(est - gt[[e[m] is not None for _, e in rows]])
            err = err[keep[[e[m] is not None for _, e in rows]]]
            mae = err.mean(axis=0)
            out.append(f"| {m} | {mae[0]:.2f} | {mae[1]:.2f} | {mae[2]:.2f} | {mae.mean():.2f} | "
                       f"{100 * np.mean(err[:, 0] <= 10):.0f} % |" + ("" if ok.sum() == keep.sum() else " (some failed)"))
        out.append("")
    return "\n".join(out)


# --- eye state on still images ---

def eyes(directory: str) -> str:
    import cv2

    from dms_edge import drowsiness
    from dms_edge.landmarks import _face_from_points

    mp, lm = _mp_landmarker(transform=False)  # IMAGE mode: no tracking between unrelated photos
    counts = {m: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for m in ("blendshape", "EAR < 0.20")}
    missed = 0
    for label in ("open", "closed"):
        for f in sorted(glob.glob(str(Path(directory) / label / "*"))):
            img = cv2.imread(f)
            if img is None:
                continue
            if max(img.shape[:2]) < 200:  # small crops (CEW is 100x100): upscale so the face is found
                img = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            h, w = img.shape[:2]
            res = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
            if not res.face_landmarks:
                missed += 1
                continue
            pts = np.array([(p.x * w, p.y * h) for p in res.face_landmarks[0]], np.float32)
            face = _face_from_points(pts, np.array([c.score for c in res.face_blendshapes[0]], np.float32))
            decisions = {"blendshape": DriverBaseline().eyes_closed(None, face.eye_closure, 0.25),
                         "EAR < 0.20": drowsiness.face_ear(face.points) < 0.20}
            for m, closed in decisions.items():
                truth = label == "closed"
                counts[m]["tp" if closed and truth else "fp" if closed else "fn" if truth else "tn"] += 1
    out = [f"### Eye state on still images ({directory}; {missed} without a detected face)\n",
           "| Method | Precision (closed) | Recall (closed) | F1 | Accuracy |", "|---|---|---|---|---|"]
    for m, c in counts.items():
        p, r, f1 = prf(c["tp"], c["fp"], c["fn"])
        acc = (c["tp"] + c["tn"]) / max(1, sum(c.values()))
        out.append(f"| {m} | {p:.3f} | {r:.3f} | {f1:.3f} | {acc:.3f} |")
    return "\n".join(out) + "\n"


# --- labelled video ---

def read_labels(path: str, fps: float) -> list[Episode]:
    text = Path(path).read_text().strip()
    if set(text) <= {"0", "1", "\n", "\r", " "}:  # NTHU-DDD: one digit per frame
        digits = "".join(ch for ch in text if ch in "01")
        episodes, start = [], None
        for i, ch in enumerate(digits + "0"):
            if ch == "1" and start is None:
                start = i
            elif ch == "0" and start is not None:
                if (i - start) / fps >= 1.0:
                    episodes.append(Episode("drowsy", start / fps, i / fps, True))
                start = None
        return episodes
    episodes = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2 and parts[0].replace(".", "").isdigit():
            kind = parts[2] if len(parts) > 2 else "drowsy"
            episodes.append(Episode(kind, float(parts[0]), float(parts[1]), kind in ("drowsy", "microsleep", "nod")))
    return episodes


def video(path: str, labels: str) -> str:
    import cv2

    from dms_edge import pipeline as pl
    from dms_edge.landmarks import FaceLandmarks

    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    episodes = read_labels(labels, fps)
    fl = FaceLandmarks(MODELS / "face_landmarker.task", backend="mediapipe")
    p = object.__new__(pl.Pipeline)
    p.cfg, p.emotion, p.last_emotion, p.emotion_avg = MonitorConfig(), None, (None, None), None
    p.baseline = DriverBaseline()
    p.smooth = {k: Median3() for k in ("ear", "closure", "mouth", "yaw", "pitch", "roll")}
    fusion = Fusion(p.cfg)
    alerts, i = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = i / fps
        sig = p._analyse(frame, fl.detect(frame, int(t * 1000)), t, i)
        for trig in fusion.update(sig, t).raised:
            if (trig.type == "drowsiness" and trig.severity == "critical") or trig.type == "fatigue":
                alerts.append(t)
        i += 1
    s = score(episodes, alerts)
    pr, rc, f1 = prf(s["tp"], s["fp"], s["fn"])
    delays = [d for v in s["delays"].values() for d in v]
    return (f"### {Path(path).name}: {i / fps:.0f} s, {len(episodes)} labelled drowsy episodes\n\n"
            "| TP | FP | FN | Precision | Recall | F1 | Median delay |\n|---|---|---|---|---|---|---|\n"
            f"| {s['tp']} | {s['fp']} | {s['fn']} | {pr:.3f} | {rc:.3f} | {f1:.3f} | "
            + (f"{np.median(delays):.2f} s" if delays else "-") + " |\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("simulate")
    s.add_argument("--sessions", type=int, default=40)
    s.add_argument("--fps", type=float, default=10.0)
    s.add_argument("--seed", type=int, default=7)
    h = sub.add_parser("headpose")
    h.add_argument("--aflw", required=True)
    h.add_argument("--limit", type=int)
    e = sub.add_parser("eyes")
    e.add_argument("--dir", required=True)
    v = sub.add_parser("video")
    v.add_argument("--video", required=True)
    v.add_argument("--labels", required=True)
    for p in (s, h, e, v):
        p.add_argument("--out")
    a = ap.parse_args()

    if a.mode == "simulate":
        text = simulate_report(simulate(a.sessions, a.fps, a.seed))
    elif a.mode == "headpose":
        text = headpose_report(headpose(a.aflw, a.limit))
    elif a.mode == "eyes":
        text = eyes(a.dir)
    else:
        text = video(a.video, a.labels)
    print(text)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
