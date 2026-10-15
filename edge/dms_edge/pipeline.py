"""Main loop: capture → verify driver → landmarks → EAR / head pose / emotion
→ fusion → alerts, events, clips and status over MQTT."""
from __future__ import annotations

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

VERIFY_TIMEOUT = 10.0  # seconds of unrecognised face before an unverified_driver event
REVERIFY_AFTER = 30.0  # face absent this long → possible driver change
ENROLL_SAMPLES = 5


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
        })

        # Identity
        self.driver: dict | None = None  # {"id", "name"} once verified
        self.verified = not verify  # without verification, monitoring starts at once
        self.unverified_since: float | None = None
        self.unverified_reported = False
        self.match_streak: tuple[str | None, int] = (None, 0)
        self.face_last_seen = 0.0
        # Enrollment request in progress
        self.enroll: dict | None = None
        # Open events per condition, to resolve warnings when they clear
        self.open_events: dict[str, tuple[str, str]] = {}  # condition → (eventId, severity)
        self.state = "safe"
        self.last_status = 0.0
        self.last_emotion = (None, None)
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

    def _on_enroll(self, payload: dict):
        self.enroll = {"driverId": payload.get("driverId"), "vectors": [], "deadline": time.monotonic() + 15}
        log.info("enrollment requested for driver %s", payload.get("driverId"))

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

    def _raise_event(self, type_, severity, description, signals=None, sustained_ms=None):
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
            }
            payload["signals"] = {k: (round(v, 3) if isinstance(v, float) else v)
                                  for k, v in payload["signals"].items() if v is not None}
        self.mqtt.publish("event", payload)
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
        aligned = align_112(frame, face.five_points())
        return None if aligned is None else self.embedder.embed(aligned)

    def _handle_enrollment(self, frame, face):
        e = self.enroll
        if time.monotonic() > e["deadline"]:
            self.mqtt.publish("enrollment", {"driverId": e["driverId"], "ok": False,
                                             "error": "No face seen clearly enough. Try again in better light."})
            self.enroll = None
            return
        if face is None:
            return
        vec = self._embedding(frame, face)
        if vec is not None:
            e["vectors"].append(vec)
        if len(e["vectors"]) >= ENROLL_SAMPLES:
            mean = np.mean(e["vectors"], axis=0)
            mean /= np.linalg.norm(mean)
            self.mqtt.publish("enrollment", {"driverId": e["driverId"], "ok": True, "model": MODEL_NAME,
                                             "vector": [round(float(v), 6) for v in mean]})
            log.info("enrollment for %s complete", e["driverId"])
            self.enroll = None
            self.verified = False  # re-verify against the new profile

    def _verify(self, frame, face, now):
        """Returns True once the driver may be monitored."""
        enrolled = [d for d in self.drivers if d.get("embeddings")]
        if not self.verify_enabled or not enrolled:
            self.verified, self.driver = True, None
            return True

        if self.unverified_since is None:
            self.unverified_since = now
        vec = self._embedding(frame, face)
        if vec is None:
            return False
        m = best_match(vec, enrolled, self.s.verify_threshold)
        last_id, streak = self.match_streak
        self.match_streak = (m.driver_id, streak + 1 if m.driver_id == last_id else 1)

        if m.driver_id and m.authorized and self.match_streak[1] >= 3:
            self.verified, self.driver = True, {"id": m.driver_id, "name": m.name}
            self.unverified_since, self.unverified_reported = None, False
            log.info("driver verified: %s (score %.2f)", m.name, m.score)
            return True

        if now - self.unverified_since >= VERIFY_TIMEOUT:
            if not self.unverified_reported:
                reason = "Driver is not authorized" if m.driver_id else "Driver not recognized"
                self._raise_event("unverified_driver", "warning", f"{reason} (match {max(m.score, 0):.2f})")
                self.unverified_reported = True
            # Safety first: keep monitoring an unknown driver rather than not at all.
            self.verified, self.driver = True, None
            return True
        return False

    # --- per-frame work ---

    def _analyse(self, frame, faces, now, frame_no) -> Signals:
        if not faces:
            return Signals(face=False)
        face = faces[0]
        h, w = frame.shape[:2]
        ear = drowsiness.face_ear(face.points)
        pose = head_pose.estimate(face.points, w, h)
        if self.emotion and frame_no % self.s.emotion_every_n == 0:
            pred = self.emotion.predict(frame, face)
            if pred:
                self.last_emotion = pred[:2]
        yaw, pitch, roll = pose if pose else (None, None, None)
        return Signals(True, ear, yaw, pitch, roll, *self.last_emotion)

    def _apply_fusion(self, sig, now):
        result = self.fusion.update(sig, now)
        for t in result.raised:
            previous = self.open_events.get(t.type)
            if previous:  # upgraded warning → critical: the new event supersedes it
                self._resolve_event(previous[0])
            eid = self._raise_event(t.type, t.severity, t.description, sig, t.sustained_ms)
            self.open_events[t.type] = (eid, t.severity)
        for cond in result.cleared:
            eid, sev = self.open_events.pop(cond, (None, None))
            if eid and sev == "warning":
                self._resolve_event(eid)
        self.state = result.state

    def _publish_status(self, now, force=False):
        if not force and now - self.last_status < 2.0:
            return
        self.last_status = now
        self.mqtt.publish("status", {
            "online": True,
            "state": self.state,
            "monitoring": self.verified,
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
                frame, frame_id = self.camera.read(frame_id, timeout=1.0)
                now = time.monotonic()
                if frame is None:
                    self._publish_status(now)
                    continue
                frame_no += 1
                t0 = time.perf_counter()
                self.recorder.push(frame)

                faces = self.landmarks.detect(frame, int(now * 1000))
                face = faces[0] if faces else None
                if face is not None:
                    self.face_last_seen = now
                elif self.verified and self.verify_enabled and now - self.face_last_seen > REVERIFY_AFTER:
                    log.info("face absent %ss: will re-verify the driver", int(REVERIFY_AFTER))
                    self.verified, self.driver, self.unverified_since = False, None, None
                    self.fusion.reset()

                if self.enroll:
                    self._handle_enrollment(frame, face)

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
            log.info("perf: camera %.1f fps, processed %.1f fps, %.0f ms/frame",
                     self.camera.fps, t["frames"] / elapsed, 1000 * t["infer"] / t["frames"])
            self.timing = {"frames": 0, "infer": 0.0, "t0": time.monotonic()}

    def close(self):
        self.camera.stop()
        self.gps.stop()
        self.alerts.close()
        self.landmarks.close()
        self.mqtt.stop()
        if self.show:
            cv2.destroyAllWindows()
