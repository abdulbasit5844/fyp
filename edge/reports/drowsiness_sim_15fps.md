### Drowsiness alerts on simulated drives (40 drives x 5 min, 15 fps)

Each drive has 3 microsleeps (eyes shut 2.5-6 s) and 2 head nods (eyes shut 1-1.8 s, head drops 18-30°) that should alert, plus 2 yawns with eyes squeezed shut for 1.5-3 s, 3 phone glances (head down 25-35°, eyelids lowered) and 4 long blinks (0.5-1.2 s) that should not, among normal blinks (15/min), EAR noise, single-frame landmark glitches and missed detections. A long blink can still alert when the driver is already in a fatigue warning (fatigue + 1 s closure = critical); those count as false alarms here.

| Rules | TP | FP | FN | Precision | Recall | F1 | False alarms / h | Delay microsleep (median / p95) | Delay nod (median) |
|---|---|---|---|---|---|---|---|---|---|
| 2 s EAR rule only | 120 | 62 | 80 | 0.659 | 0.600 | 0.628 | 18.6 | 2.13 s / 2.18 s | missed |
| with refinements | 197 | 11 | 3 | 0.947 | 0.985 | 0.966 | 3.3 | 2.12 s / 2.17 s | 0.56 s |

* 2 s EAR rule only: false alarms by cause {'yawn': 59, 'other': 3}; missed {'head nod': 80}
* with refinements: false alarms by cause {'long blink': 8, 'other': 3}; missed {'head nod': 3}

### Fatigue warning (PERCLOS / slow blinks / yawns) per drive

Separate drives without microsleeps: 1 yawn, 3 phone glances and 4 long blinks each.

| Drivers | Drives | Flagged | Rate | Time to first warning (median) |
|---|---|---|---|---|
| fatigued: 20 blinks/min (median 300 ms), 8 closures/min of 0.6-1.6 s | 20 | 20 | 1.00 | 31 s |
| alert: 15 blinks/min (median 150 ms) | 20 | 0 | 0.00 | - |
