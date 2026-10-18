### Head pose error on AFLW2000-3D (1755 of 2000 faces; 245 not detected by MediaPipe)

Mean absolute error in degrees (axis signs aligned to the dataset: yaw -1, pitch -1, roll -1).

**all angles within ±99° (standard protocol)**, 1749 faces

| Method | Yaw MAE | Pitch MAE | Roll MAE | Mean | Yaw error ≤ 10° |
|---|---|---|---|---|---|
| canonical (33 pts) | 3.82 | 6.90 | 4.28 | 5.00 | 93 % |
| generic 6-point | 7.85 | 7.39 | 4.42 | 6.55 | 69 % |
| MediaPipe matrix | 3.93 | 6.99 | 4.29 | 5.07 | 92 % |

**driver range: |yaw| and |pitch| ≤ 45°**, 1489 faces

| Method | Yaw MAE | Pitch MAE | Roll MAE | Mean | Yaw error ≤ 10° |
|---|---|---|---|---|---|
| canonical (33 pts) | 3.17 | 5.21 | 2.58 | 3.65 | 95 % |
| generic 6-point | 8.08 | 5.62 | 2.81 | 5.50 | 67 % |
| MediaPipe matrix | 3.20 | 5.26 | 2.58 | 3.68 | 95 % |

**near frontal: |yaw| and |pitch| ≤ 20°**, 927 faces

| Method | Yaw MAE | Pitch MAE | Roll MAE | Mean | Yaw error ≤ 10° |
|---|---|---|---|---|---|
| canonical (33 pts) | 2.37 | 3.96 | 1.48 | 2.61 | 98 % |
| generic 6-point | 7.10 | 4.23 | 1.69 | 4.34 | 73 % |
| MediaPipe matrix | 2.38 | 3.92 | 1.45 | 2.58 | 98 % |
