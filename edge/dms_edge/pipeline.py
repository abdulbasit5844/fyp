"""Main loop: capture → verify driver → landmarks → EAR / head pose / emotion
→ fusion → alerts, events, clips and status over MQTT."""
from __future__ import annotations

import base64
import logging
import threading
import time
import uuid
from datetime import datetime, timezone

import cv2
import numpy as np

from . import __version__, drowsiness, head_pose
from .alerts import AlertManager
from .align import align_112
from .calibration import DriverBaseline, Median3
from .camera import Camera
from .emotion import EmotionClassifier
from .face_id import MODEL_NAME, FaceEmbedder, best_match
from .fusion import Fusion, Signals
from .gps import GPS
from .landmarks import FaceLandmarks
from .mqtt_link import MqttLink
from .recorder import ClipRecorder
from .settings import DeviceSettings, MonitorConfig

log = logging.getLogger(__name__)

VERIFY_TIMEOUT = 15.0  # face in view this long without being identified → treated as unknown
UNKNOWN_AFTER = 6  # clear looks in a row that match no authorized driver → unknown person (~2 s)
UNSURE_SCORE = 0.30  # just under the match threshold: not a match, but not clearly a stranger either
VERIFY_GAP = 3.0  # face out of view this long while verifying → start counting afresh
REVERIFY_AFTER = 30.0  # face absent this long → possible driver change
LIVE_KEEPALIVE = 45.0  # seconds without a request from the app before the stream stops
ENROLL_SAMPLES = 5
ENROLL_SPACING = 0.15  # seconds between enrollment samples
# Identity frames must be at least this good (enrollment and verification).
MIN_ID_FACE_PX = 60
MAX_ID_YAW, MAX_ID_PITCH = 40.0, 30.0  # generous: the generic head model overestimates turns
MIN_SHARPNESS = 40.0  # variance of the Laplacian on the aligned 112x112 face
EMOTION_SMOOTHING = 0.4  # weight of the newest prediction in the running average
ENROLL_PREVIEW_TIMEOUT = 120.0  # live view stops if the app does not press Capture
ENROLL_CAPTURE_TIMEOUT = 8.0  # seconds to collect the samples after Capture
ENROLL_PROGRESS_EVERY = 0.4  # seconds between live-view frames sent to the app
NO_PERSON = "No person detected in the camera. Sit in the driver's seat facing the camera."


def _jpeg_b64(img, width: int, quality: int) -> str:
    img = cv2.resize(img, (width, int(width * img.shape[0] / img.shape[1])))
    ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(jpg.tobytes()).decode() if ok else ""


def enrollment_preview(frame, face) -> str:
    """Small JPEG (base64) of the camera view, with the detected face boxed."""
    img = frame.copy()
    if face is not None:
        x, y, w, h = face.bbox
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 200, 0), 3)
    return _jpeg_b64(img, 320, 60)


def face_photo(frame, face) -> str:
    """Square head-and-shoulders crop (base64 JPEG) saved as the driver's photo."""
    x, y, w, h = face.bbox
    side = int(max(w, h) * 1.6)
    cx, cy = x + w // 2, y + h // 2
    H, W = frame.shape[:2]
    x0, y0 = max(0, cx - side // 2), max(0, cy - side // 2)
    crop = frame[y0:min(H, y0 + side), x0:min(W, x0 + side)]
    return _jpeg_b64(crop, 200, 80) if crop.size else ""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Pipeline:
    def __init__(self, s: DeviceSettings, show=False, verify=True):
        self.s, self.show, self.verify_enabled = s, show, verify
        self.cfg = MonitorConfig()
        self.drivers: list[dict] = []
        self.lock = threading.Lock()

        m = s.models_dir
        self.landmarks = FaceLandmarks(m / "face_landmarker.task")
        if not head_pose.use_canonical(m / "face_landmarker.task"):
            log.warning("canonical face model unavailable; head pose uses the 6-point model")
        self.embedder = FaceEmbedder(m / "face_recognition_sface_2021dec_int8.onnx")
        try:
            self.emotion = EmotionClassifier(m)
            log.info("emotion model: %s", self.emotion.name)
        except FileNotFoundError as e:
            log.warning("%s; emotion analysis disabled", e)
            self.emotion = None

        self.fusion = Fusion(self.cfg)
        self.camera = Camera(s.source, s.width, s.height, s.fps)
        self.gps = GPS(s.gps_port)
        self.alerts = AlertManager(self.cfg, on_ack=self._edge_ack, on_escalate=self._escalate,
                                   pins=(s.buzzer_pin, s.led_pin, s.button_pin))
        self.recorder = ClipRecorder(s.clips_dir, on_clip=lambda c: self.mqtt.publish("clip", c), fps=s.fps,
                                     storage_limit=s.storage_limit)
        self.mqtt = MqttLink(s.device_id, s.mqtt_host, s.mqtt_port, {
            "config": self._on_config,
            "drivers": self._on_drivers,
            "cmd/ack": self._app_ack,
            "cmd/enroll": self._on_enroll,
            "cmd/detection": self._on_detection,
            "cmd/live": self._on_live,
        })
        # Live view: streaming runs while the app keeps asking for it.
        self.live_until = 0.0
        # Start/Stop from the app (retained on MQTT). Stopped: no detection or alerts.
        self.detecting = False

        # Identity
        # Monitoring only starts once a registered, authorized driver is recognised.
        # identity: verifying | verified | unknown | none (verification off / nobody enrolled)
        self.unknown_event: str | None = None  # open unverified_driver event
        self._reset_identity()
        self.face_last_seen = 0.0
        # Enrollment request in progress
        self.enroll: dict | None = None
        # Open events per condition, to resolve warnings when they clear
        self.open_events: dict[str, tuple[str, str]] = {}  # condition → (eventId, severity)
        self.state = "safe"
        self.last_status = 0.0
        self.last_emotion = (None, None)
        self.emotion_avg: np.ndarray | None = None
        # Per-driver calibration and per-signal smoothing (see calibration.py)
        self.baseline = DriverBaseline()
        self.smooth = {k: Median3() for k in ("ear", "closure", "mouth", "yaw", "pitch", "roll")}
        self.timing = {"frames": 0, "infer": 0.0, "t0": time.monotonic()}

    # --- MQTT handlers ---

    def _on_config(self, payload: dict):
        with self.lock:
            self.cfg = MonitorConfig.from_dict(payload)
            self.fusion.cfg = self.cfg
            self.alerts.cfg = self.cfg
        log.info("config revision %s applied (EAR %.2f, ack %ss)", self.cfg.revision, self.cfg.earThreshold,
                 self.cfg.ackWindowSec)

    def _on_drivers(self, payload: list):
        self.drivers = payload if isinstance(payload, list) else []
        enrolled = sum(1 for d in self.drivers if d.get("embeddings"))
        log.info("%d driver profiles (%d enrolled)", len(self.drivers), enrolled)

    def _on_detection(self, payload: dict):
        enabled = bool(payload.get("enabled"))
        if enabled == self.detecting:
            return
        with self.lock:
            self.detecting = enabled
            if not enabled:
                # Close whatever is open: no buzzer, no escalation while stopped.
                for eid, _ in self.open_events.values():
                    if self.alerts.is_open(eid):
                        self._resolve_event(eid)
                self.open_events.clear()
                self.fusion.reset()
                self.state = "safe"
            # Verify the driver again on every start.
            self._reset_identity()
            self._reset_driver_model()
        log.info("detection %s from the app", "started" if enabled else "stopped")
        self._publish_status(time.monotonic(), force=True)

    def _on_live(self, payload: dict):
        """{enabled, quality}: the app opened/closed the live view. It repeats the request
        while watching; without it the stream stops after LIVE_KEEPALIVE."""
        if payload.get("enabled"):
            quality = payload.get("quality", "480p")
            if not self.camera.live or self.camera.live_quality != quality:
                log.info("live view requested (%s)", quality)
            self.live_until = time.monotonic() + LIVE_KEEPALIVE
            self.camera.set_live(f"rtsp://127.0.0.1:{self.s.rtsp_port}/{self.s.device_id}", quality)
        else:
            self._stop_live("closed in the app")

    def _stop_live(self, why: str):
        if self.live_until:
            log.info("live view stopped (%s)", why)
        self.live_until = 0.0
        self.camera.set_live(None)

    def _on_enroll(self, payload: dict):
        """preview: stream the camera view to the app; capture: take the photo and
        samples now; cancel: stop."""
        action, driver_id = payload.get("action", "preview"), payload.get("driverId")
        if action == "cancel":
            if self.enroll and self.enroll["driverId"] == driver_id:
                self.enroll = None
            return
        now = time.monotonic()
        timeout = ENROLL_CAPTURE_TIMEOUT if action == "capture" else ENROLL_PREVIEW_TIMEOUT
        self.enroll = {"driverId": driver_id, "mode": action, "vectors": [], "photo": None,
                       "deadline": now + timeout, "last_progress": 0.0}
        log.info("enrollment %s for driver %s", action, driver_id)

    # --- alert callbacks ---

    def _acked(self, event_id):
        with self.lock:
            for cond, (eid, _) in list(self.open_events.items()):
                if eid == event_id:
                    del self.open_events[cond]
                    self.fusion.forget(cond)

    def _edge_ack(self, event_id):
        self._acked(event_id)
        self.mqtt.publish("event/ack", {"eventId": event_id, "ts": utcnow()})

    def _app_ack(self, payload):
        self.alerts.acknowledge(payload.get("eventId"))
        self._acked(payload.get("eventId"))

    def _escalate(self, event_id):
        self.mqtt.publish("event/escalate", {"eventId": event_id, "location": self.gps.position, "ts": utcnow()})

    # --- events ---

    def _raise_event(self, type_, severity, description, signals=None, sustained_ms=None, photo=None,
                     local_alert=True):
        """local_alert=False: no buzzer and no edge escalation timer (the backend
        handles it, e.g. an unknown driver goes straight to the owner)."""
        event_id = uuid.uuid4().hex
        payload = {
            "eventId": event_id,
            "type": type_,
            "severity": severity,
            "detectedAt": utcnow(),
            "description": description,
            "driverId": self.driver["id"] if self.driver else None,
            "location": self.gps.position,
        }
        if signals is not None:
            payload["signals"] = {
                "ear": signals.ear, "yaw": signals.yaw, "pitch": signals.pitch, "roll": signals.roll,
                "emotion": signals.emotion, "emotionConfidence": signals.emotion_conf, "sustainedMs": sustained_ms,
                "mouthOpen": signals.mouth_open, **self.fusion.metrics,
            }
            payload["signals"] = {k: (round(v, 3) if isinstance(v, float) else v)
                                  for k, v in payload["signals"].items() if v is not None}
        if photo:
            payload["photo"] = photo  # base64 JPEG of the person in the driver's seat
        self.mqtt.publish("event", payload)
        if local_alert:
            self.alerts.raise_alert(event_id, type_, severity)
        if self.cfg.videoRecordingEnabled:
            self.recorder.trigger(event_id)
        log.warning("EVENT %s %s: %s", severity.upper(), type_, description)
        return event_id

    def _resolve_event(self, event_id):
        self.alerts.resolve(event_id)
        self.mqtt.publish("event/resolve", {"eventId": event_id, "ts": utcnow()})

    # --- identity ---

    def _embedding(self, frame, face):
        """Face embedding, only from frames good enough to identify someone:
        large enough, roughly frontal and not blurred. Bad frames return None."""
        if face.bbox[2] < MIN_ID_FACE_PX:
            return None
        h, w = frame.shape[:2]
        pose = head_pose.estimate(face.points, w, h)
        if pose is None or abs(pose[0]) > MAX_ID_YAW or abs(pose[1]) > MAX_ID_PITCH:
            return None
        aligned = align_112(frame, face.five_points())
        if aligned is None:
            return None
        if cv2.Laplacian(cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var() < MIN_SHARPNESS:
            return None
        return self.embedder.embed(aligned)

    def _handle_enrollment(self, frame, face):
        e = self.enroll
        now = time.monotonic()
        capturing = e["mode"] == "capture"
        if now > e["deadline"]:
            if not capturing:
                error = "Live view stopped. Press Try again to restart it."
            elif not e["vectors"]:
                error = NO_PERSON
            else:
                error = "Face not seen clearly enough. Hold still in good light and try again."
            self._finish_enrollment(e, ok=False, error=error)
            return

        # Samples at least ENROLL_SPACING apart, so they cover small natural movements.
        if capturing and face is not None and now - e.get("last_sample", 0.0) >= ENROLL_SPACING:
            vec = self._embedding(frame, face)
            if vec is not None:
                e["last_sample"] = now
                e["vectors"].append(vec)
                if e["photo"] is None:
                    e["photo"] = face_photo(frame, face)
            if len(e["vectors"]) >= ENROLL_SAMPLES:
                mean = np.mean(e["vectors"], axis=0)
                mean /= np.linalg.norm(mean)
                self._finish_enrollment(e, ok=True, model=MODEL_NAME, photo=e["photo"],
                                        vector=[round(float(v), 6) for v in mean])
                self.verified = False  # re-verify against the new profile
                return

        if now - e["last_progress"] >= ENROLL_PROGRESS_EVERY:
            e["last_progress"] = now
            self.mqtt.publish("enrollment", {
                "driverId": e["driverId"], "status": "progress", "mode": e["mode"],
                "samples": len(e["vectors"]), "needed": ENROLL_SAMPLES,
                "faceVisible": face is not None,
                "secondsLeft": max(0, round(e["deadline"] - now)),
                "preview": enrollment_preview(frame, face),
            })

    def _finish_enrollment(self, e, ok: bool, **fields):
        self.mqtt.publish("enrollment", {"driverId": e["driverId"], "status": "done" if ok else "failed",
                                         "ok": ok, **fields})
        log.info("enrollment for %s %s", e["driverId"], "complete" if ok else f"failed: {fields.get('error')}")
        self.enroll = None

    def _reset_identity(self):
        """Back to "who is driving?". Closes an open unknown-person event."""
        if self.unknown_event:
            self._resolve_event(self.unknown_event)
        self.verified, self.driver = not self.verify_enabled, None
        self.identity = "verifying" if self.verify_enabled else "none"
        self.unknown_event, self.last_non_match = None, None
        self.unverified_since, self.last_verify_at = None, 0.0
        self.match_streak: tuple[str | None, int] = (None, 0)
        self.non_matches = 0

    def _verify(self, frame, face, now):
        """Returns True once the driver may be monitored: only a recognised,
        authorized driver. Anyone else raises one unverified_driver event with a
        photo, which the backend sends to the owner on WhatsApp; the check keeps
        running, so a registered driver who is recognised later is still monitored."""
        enrolled = [d for d in self.drivers if d.get("embeddings")]
        if not self.verify_enabled or not enrolled:
            # Nobody to compare against: monitor whoever drives.
            self.verified, self.driver, self.identity = True, None, "none"
            return True

        if self.unverified_since is None or now - self.last_verify_at > VERIFY_GAP:
            self.unverified_since, self.non_matches, self.match_streak = now, 0, (None, 0)
        self.last_verify_at = now
        vec = self._embedding(frame, face)
        if vec is not None:
            m = best_match(vec, enrolled, self.s.verify_threshold)
            if m.driver_id and m.authorized:
                last_id, streak = self.match_streak
                self.match_streak = (m.driver_id, streak + 1 if m.driver_id == last_id else 1)
                self.non_matches = 0
                if self.match_streak[1] >= 3:
                    self._verified_as(m, now)
                    return True
                return False
            self.match_streak = (None, 0)
            # A registered but unauthorized driver, or clearly someone else. Scores just
            # under the threshold (a registered driver at a bad angle) count for neither.
            if m.driver_id or m.score < UNSURE_SCORE:
                self.non_matches += 1
                self.last_non_match = m

        if self.unknown_event is None and (self.non_matches >= UNKNOWN_AFTER
                                           or now - self.unverified_since >= VERIFY_TIMEOUT):
            m = self.last_non_match
            if m is not None and m.driver_id:
                why = f"{m.name} is registered but not authorized to drive"
            elif m is not None:
                why = f"Unknown person in the driver's seat (best match {max(m.score, 0):.2f})"
            else:
                why = "Driver could not be identified (face not clearly visible)"
            self.identity = "unknown"
            self.unknown_event = self._raise_event("unverified_driver", "critical", why,
                                                   photo=face_photo(frame, face), local_alert=False)
            self._publish_status(now, force=True)
        return False

    def _verified_as(self, m, now):
        if self.unknown_event:  # an authorized driver after all: close the unknown-person alert
            self._resolve_event(self.unknown_event)
            self.unknown_event = None
        self.verified, self.driver, self.identity = True, {"id": m.driver_id, "name": m.name}, "verified"
        self.unverified_since, self.non_matches = None, 0
        log.info("driver verified: %s (score %.2f)", m.name, m.score)
        self._publish_status(now, force=True)

    # --- per-frame work ---

    def _reset_driver_model(self):
        """New driver or new session: calibrate again and forget smoothed history."""
        self.baseline.reset()
        for f in self.smooth.values():
            f.reset()
        self.emotion_avg = None
        self.last_emotion = (None, None)

    def _analyse(self, frame, faces, now, frame_no) -> Signals:
        if not faces:
            for f in self.smooth.values():
                f.reset()
            return Signals(face=False)
        face = faces[0]
        h, w = frame.shape[:2]
        pose = head_pose.estimate(face.points, w, h)
        yaw, pitch, roll = pose if pose else (None, None, None)
        sm = self.smooth
        ear = sm["ear"](drowsiness.face_ear(face.points))
        closure = sm["closure"](face.eye_closure)
        jaw = face.jaw_open
        mouth = sm["mouth"](jaw if jaw is not None else drowsiness.mouth_aspect_ratio(face.points))
        yaw, pitch, roll = sm["yaw"](yaw), sm["pitch"](pitch), sm["roll"](roll)

        # Learn this driver's normal eyes / head position, then judge relative to it.
        if not self.baseline.ready:
            self.baseline.add(ear, closure, yaw, pitch, roll)
            if self.baseline.ready:
                b = self.baseline
                log.info("calibrated driver: open EAR %.3f, eye closure %s, neutral yaw %.0f° pitch %.0f° roll %.0f°",
                         b.ear_open, "n/a" if b.closure_open is None else f"{b.closure_open:.2f}", b.yaw0, b.pitch0,
                         b.roll0)
        rel_yaw, rel_pitch, rel_roll = self.baseline.relative_pose(yaw, pitch, roll)
        closed = self.baseline.eyes_closed(ear, closure, self.cfg.earThreshold)

        if self.emotion and frame_no % self.s.emotion_every_n == 0 and face.bbox[2] >= MIN_ID_FACE_PX:
            pred = self.emotion.predict(frame, face)
            if pred:
                probs = np.array([pred[2][k] for k in self.emotion.labels], np.float64)
                self.emotion_avg = probs if self.emotion_avg is None else (
                    (1 - EMOTION_SMOOTHING) * self.emotion_avg + EMOTION_SMOOTHING * probs)
                i = int(self.emotion_avg.argmax())
                self.last_emotion = (self.emotion.labels[i], float(self.emotion_avg[i]))
        return Signals(True, ear, rel_yaw, rel_pitch, rel_roll, *self.last_emotion, eyes_closed=closed,
                       mouth_open=mouth)

    def _apply_fusion(self, sig, now):
        result = self.fusion.update(sig, now)
        for t in result.raised:
            previous = self.open_events.get(t.type)
            if previous:  # upgraded warning → critical: the new event supersedes it
                self._resolve_event(previous[0])
            eid = self._raise_event(t.type, t.severity, t.description, sig, t.sustained_ms)
            self.open_events[t.type] = (eid, t.severity)
        # The driver is back to normal: close the alert (stops the buzzer and,
        # for critical alerts, the escalation countdown) so the app shows safe.
        for cond in result.cleared:
            eid, _ = self.open_events.pop(cond, (None, None))
            if eid and self.alerts.is_open(eid):
                self._resolve_event(eid)
        self.state = result.state

    def _publish_status(self, now, force=False):
        if not force and now - self.last_status < 2.0:
            return
        self.last_status = now
        self.mqtt.publish("status", {
            "online": True,
            "state": self.state,
            "detecting": self.detecting,
            "live": self.camera.live,
            "liveQuality": self.camera.live_quality,
            "monitoring": self.detecting and self.verified,
            "identity": self.identity,
            "driverId": self.driver["id"] if self.driver else None,
            "location": self.gps.position,
            "pipelineVersion": __version__,
            "fps": round(self.camera.fps, 1),
            "cameraConnected": self.camera.connected,
            "ts": utcnow(),
        }, retain=True)

    def _overlay(self, frame, sig):
        color = {"safe": (0, 200, 0), "warning": (0, 190, 255), "critical": (0, 0, 255)}[self.state]
        lines = [f"{self.state.upper()}  fps {self.camera.fps:.1f}",
                 f"EAR {sig.ear:.2f}" if sig.ear is not None else "no face"]
        if sig.yaw is not None:
            lines.append(f"yaw {sig.yaw:.0f} pitch {sig.pitch:.0f}")
        if sig.emotion:
            lines.append(f"{sig.emotion} {sig.emotion_conf:.2f}")
        m = self.fusion.metrics
        lines.append("PERCLOS " + ("--" if m["perclos"] is None else f"{100 * m['perclos']:.0f}%")
                     + f"  yawns {m['yawns']}" + ("" if sig.mouth_open is None else f"  mouth {sig.mouth_open:.2f}"))
        lines.append(f"driver: {self.driver['name'] if self.driver else ('?' if not self.verified else 'unknown')}")
        for i, text in enumerate(lines):
            cv2.putText(frame, text, (10, 25 + 24 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
        cv2.imshow("DMS", frame)
        if cv2.waitKey(1) & 0xFF == ord("a"):  # 'a' simulates the acknowledgment button
            self.alerts.button_pressed()

    def run(self):
        log.info("device %s starting (camera %s, %dx%d@%d)", self.s.device_id, self.s.source,
                 self.s.width, self.s.height, self.s.fps)
        self.mqtt.start()
        self.camera.start()
        self.gps.start()
        frame_id, frame_no = 0, 0
        try:
            while True:
                self.alerts.tick()
                if self.live_until and time.monotonic() > self.live_until:
                    self._stop_live("no viewer")
                frame, frame_id = self.camera.read(frame_id, timeout=1.0)
                now = time.monotonic()
                if frame is None:
                    self._publish_status(now)
                    continue
                frame_no += 1
                if not self.detecting and not self.enroll:  # stopped from the app: idle
                    self._publish_status(now)
                    continue
                t0 = time.perf_counter()
                if self.detecting:
                    self.recorder.push(frame)

                faces = self.landmarks.detect(frame, int(now * 1000))
                face = faces[0] if faces else None
                if face is not None:
                    self.face_last_seen = now
                elif self.verify_enabled and self.identity != "verifying" and now - self.face_last_seen > REVERIFY_AFTER:
                    log.info("face absent %ss: will re-verify the driver", int(REVERIFY_AFTER))
                    self._reset_identity()
                    self.fusion.reset()
                    self._reset_driver_model()

                if self.enroll:
                    self._handle_enrollment(frame, face)
                if not self.detecting:  # only here for enrollment
                    self._publish_status(now)
                    continue

                sig = Signals(face=False)
                if not self.verified:
                    if face is not None and frame_no % 3 == 0:
                        self._verify(frame, face, now)
                else:
                    sig = self._analyse(frame, faces, now, frame_no)
                    with self.lock:
                        self._apply_fusion(sig, now)

                self._timing(time.perf_counter() - t0)
                self._publish_status(now, force=False)
                if self.show:
                    self._overlay(frame, sig)
        except KeyboardInterrupt:
            log.info("stopping")
        finally:
            self.close()

    def _timing(self, dt):
        t = self.timing
        t["frames"] += 1
        t["infer"] += dt
        elapsed = time.monotonic() - t["t0"]
        if elapsed >= 10:
            log.info("perf: camera %.1f fps, processed %.1f fps, %.0f ms/frame; fatigue %s",
                     self.camera.fps, t["frames"] / elapsed, 1000 * t["infer"] / t["frames"], self.fusion.metrics)
            self.timing = {"frames": 0, "infer": 0.0, "t0": time.monotonic()}

    def close(self):
        self.camera.stop()
        self.gps.stop()
        self.alerts.close()
        self.landmarks.close()
        self.mqtt.stop()
        if self.show:
            cv2.destroyAllWindows()
