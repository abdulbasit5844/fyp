# Evaluation results (Modules 3 and 5)

All numbers come from `edge/scripts/evaluate.py`; rerun any of them to regenerate the files here.

| File | What it measures | Command (from `edge/`) |
|---|---|---|
| `drowsiness_sim_10fps.md` | Drowsiness alert precision, recall, detection delay; fatigue warning per drive. 10 fps ≈ the Pi 4's processed rate | `python scripts/evaluate.py simulate --fps 10 --out reports/drowsiness_sim_10fps.md` |
| `drowsiness_sim_15fps.md` | Same at the camera's 15 fps | `python scripts/evaluate.py simulate --fps 15 --out reports/drowsiness_sim_15fps.md` |
| `headpose_aflw2000.md` | Yaw / pitch / roll error against AFLW2000-3D ground truth: canonical 33-point model vs generic 6-point model vs MediaPipe's own matrix | `python scripts/evaluate.py headpose --aflw path/to/AFLW2000 --out reports/headpose_aflw2000.md` (needs `pip install scipy`) |

`pytest tests/test_accuracy.py` runs a smaller version of the simulation and fails if precision drops
below 0.85, recall below 0.95, or the median detection delay goes over 2.5 s (microsleep) / 1 s (head nod).

## Summary

**Drowsiness (simulated drives, 40 x 5 min, 10 fps)**

| Rules | Precision | Recall | False alarms / h | Median delay: microsleep / head nod |
|---|---|---|---|---|
| 2 s EAR rule only (before) | 0.706 | 0.600 | 15.0 | 2.20 s / missed |
| with yawn, nod and fatigue refinements | 0.939 | 1.000 | 3.9 | 2.19 s / 0.61 s |

Fatigue warning (PERCLOS / slow blinks / yawns): 20 of 20 fatigued drivers flagged (median 35 s), 0 of 20 alert drivers.

**Head pose (AFLW2000-3D, 1749 faces, standard ±99° protocol)**

| Method | Yaw MAE | Pitch MAE | Roll MAE |
|---|---|---|---|
| canonical 33-point model (used) | 3.82° | 6.90° | 4.28° |
| generic 6-point model (fallback) | 7.85° | 7.39° | 4.42° |
| MediaPipe transformation matrix | 3.93° | 6.99° | 4.29° |

In the driving range (|yaw|, |pitch| ≤ 45°) the canonical model's yaw error is 3.17° vs 8.08°.

## Limits of this evidence (state these in the report)

* The drowsiness figures are from **simulated** signal traces with known ground truth. They test the
  decision logic (calibration, smoothing, timers, fusion) end to end. They do not test how well the camera
  and face mesh measure the eyes. For that, use `evaluate.py video` on labelled footage
  (NTHU-DDD per-frame label files are read directly; access is by request from NTHU) or on your own
  recordings with a `start,end,label` CSV.
* **MRL Eye** contains cropped eye images with no face, so the face-mesh pipeline cannot run on it. It
  can only validate a separate eye-crop classifier. `evaluate.py eyes` measures the frame-level eye state
  on full-face open/closed images (such as CEW, whose original download link is offline).
* The remaining false alarms after the refinements are long blinks while the driver is already in a
  fatigue warning (by design: fatigue + a 1 s closure is critical) and closures during phone glances (the
  eyelids drop when looking down, which EAR cannot tell apart from closing).
* 245 of the 2000 AFLW faces (mostly extreme poses) were not detected by MediaPipe, so they are
  excluded for all three methods alike.
