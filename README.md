# Vision Based Driver Monitoring and Safety Assistance System

| Folder | What it is |
|---|---|
| `backend/` | Node.js + Express + MongoDB API, JWT auth, WebSocket feed, MQTT bridge, FCM/SMS escalation |
| `edge/` | Python pipeline on the Pi: camera → MediaPipe landmarks → EAR, head pose, emotion → fusion → alerts, clips |
| `app/` | Flutter app (Windows/Linux desktop or Android): login, live status, alerts, event logs + video, settings |
| `deploy/` | Pi setup script, install script and systemd user services |
| `docs/mqtt-contract.md` | Topics and payloads between the edge pipeline and the backend |

## Architecture (all on the Raspberry Pi 4)

```
camera ─► edge pipeline (Python) ──MQTT 127.0.0.1:1883──► backend (Node) ──► MongoDB 7 (127.0.0.1)
             │ buzzer / LED / button (GPIO)                   │  REST + WebSocket :3000
             │ GPS (UART)                                     ▼
             └ clips → /var/lib/dms/clips ◄── streamed ── Flutter app (laptop / Pi / phone)
                                                              FCM push / Twilio SMS → emergency contacts
```

## First-time Pi setup

1. Copy the code to the Pi (from the project root, Git Bash): `bash deploy/deploy.sh`
   (first run will fail at the install step until step 2 is done; that is expected).
2. On the Pi, once: `sudo bash ~/dms/deploy/pi-setup.sh` installs Node 22, MongoDB 7.0
   (community Pi 4 build, 256 MB cache, localhost only), Mosquitto, OpenCV, ffmpeg and GPIO libraries.
3. Then `bash deploy/deploy.sh` again. It installs dependencies, downloads models, creates
   `backend/.env` with a random JWT secret, and starts `dms-backend` and `dms-edge`.

Logs: `journalctl --user-unit dms-backend -f` and `journalctl --user-unit dms-edge -f` on the Pi.

## Wiring (BCM pin numbers, change in `deploy/systemd/dms-edge.service` via `DMS_*_PIN`)

| Part | Pin |
|---|---|
| Active buzzer (+) | GPIO 17 |
| LED (+, with 330 Ω resistor) | GPIO 27 |
| Acknowledge button (to GND) | GPIO 22 |
| NEO-6M GPS TX → Pi RX | GPIO 15 (`/dev/serial0`; enable the serial port in `raspi-config`) |

## Running the app

```
cd app
flutter pub get
flutter run -d windows      # or -d linux on the Pi, or an Android device
```
Sign in with the Pi's address, e.g. `http://pi.local:3000`. First use: register → Devices & drivers →
Pair a unit (`pi-vision-01`) → add a driver → Enroll face → add emergency contacts.

## AI models (all pretrained, nothing to train)

`edge/scripts/download_models.py` fetches them; the deploy script runs it on the Pi.

| Task | Model | Source |
|---|---|---|
| Face landmarks → EAR drowsiness, head pose (solvePnP) | MediaPipe Face Landmarker (float16) | Google MediaPipe |
| Driver identity | SFace, INT8, 128-d embeddings | OpenCV Model Zoo |
| Emotion, 7 classes | MobileFaceNet facial expression, INT8 | OpenCV Model Zoo |

### Optional: custom MobileNetV2 emotion model

Not needed. If you later want a model trained yourself, train MobileNetV2 on FER-2013 (GPU or Colab):

```
pip install -r edge/training/requirements.txt
python edge/training/train_emotion.py --data path/to/fer2013 --epochs 30
```
Copy `emotion_mobilenetv2_int8.onnx` and `.json` from `training/output/` to `~/dms/edge/models/` on the Pi;
the pipeline prefers it automatically.

## Optional services

* **Push notifications (FCM)**: create a Firebase project, download a service-account JSON to the Pi and
  set `FIREBASE_SERVICE_ACCOUNT=/path/to/file.json` in `backend/.env`.
* **SMS fallback (Twilio)**: set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM`.
* **Email escalation (free)**: set `EMAIL_USER` (a Gmail address) and `EMAIL_PASS` (a Google app password) in
  `backend/.env`. Every emergency contact with an email address gets an SOS email with the Maps link,
  alongside push/SMS.
* **HTTPS (SEC-1)**: set `TLS_CERT` / `TLS_KEY` and use `https://` in the app.

Without these, escalations are still logged and shown in the app; delivery is recorded as failed with the reason.

## Tests

```
cd backend && npm test                     # API + edge→backend flow, in-memory MongoDB
cd edge && .venv/Scripts/python -m pytest  # EAR, head pose, NMEA, fusion, alerts, recorder
cd app && flutter test
```

## Not built yet

* Web admin dashboard (Module 8): the backend's `/api/users` admin endpoints exist; the React UI does not.
* Unauthorized occupant detection while parked (FR4.1) and key-left-inside (FR4.2) need engine/door
  signals and an object-detection model.
* Mobile push on the Flutter side needs a Firebase project (`firebase_messaging`, Android only).
