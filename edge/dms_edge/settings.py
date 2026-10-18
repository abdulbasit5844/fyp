"""Device settings (fixed per install) and monitoring settings (pushed from the app)."""
from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field, fields
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class DeviceSettings:
    device_id: str = os.getenv("DMS_DEVICE_ID", f"pi-{socket.gethostname()}")
    source: str = os.getenv("DMS_SOURCE", "auto")  # auto | picamera | <index> | <file/url>
    width: int = int(os.getenv("DMS_WIDTH", "640"))
    height: int = int(os.getenv("DMS_HEIGHT", "480"))
    fps: int = int(os.getenv("DMS_FPS", "15"))
    mqtt_host: str = os.getenv("DMS_MQTT_HOST", "127.0.0.1")
    mqtt_port: int = int(os.getenv("DMS_MQTT_PORT", "1883"))
    rtsp_port: int = int(os.getenv("DMS_RTSP_PORT", "8554"))  # local MediaMTX server for live view
    models_dir: Path = Path(os.getenv("DMS_MODELS_DIR", ROOT / "models"))
    clips_dir: Path = Path(os.getenv("DMS_CLIPS_DIR", "/var/lib/dms/clips"))
    storage_limit: float = float(os.getenv("DMS_STORAGE_LIMIT", "0.8"))  # FR4.3: 80 %
    gps_port: str = os.getenv("DMS_GPS_PORT", "/dev/serial0")
    buzzer_pin: int = int(os.getenv("DMS_BUZZER_PIN", "17"))
    led_pin: int = int(os.getenv("DMS_LED_PIN", "27"))
    button_pin: int = int(os.getenv("DMS_BUTTON_PIN", "22"))
    emotion_every_n: int = int(os.getenv("DMS_EMOTION_EVERY_N", "5"))  # CPU budget, FR2.3
    verify_threshold: float = float(os.getenv("DMS_VERIFY_THRESHOLD", "0.363"))  # SFace cosine


@dataclass
class MonitorConfig:
    """Mirror of the backend SystemConfig; replaced whenever dms/{id}/config arrives."""

    earThreshold: float = 0.25
    earSustainSec: float = 2.0
    headPoseThresholdDeg: float = 30.0  # left / right (yaw)
    headPitchThresholdDeg: float = 20.0  # up / down: looking down at a phone is the bigger risk
    headPoseSustainSec: float = 2.0
    emotionSustainSec: float = 3.0
    ackWindowSec: float = 15.0
    alertSensitivity: int = 3
    videoRecordingEnabled: bool = True
    notifications: dict = field(default_factory=lambda: {"push": True, "sound": True, "smsFallback": False})
    revision: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> "MonitorConfig":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})

    @property
    def sensitivity_factor(self) -> float:
        """Higher sensitivity shortens how long a condition must last (1 → x1.5, 5 → x0.6)."""
        return {1: 1.5, 2: 1.25, 3: 1.0, 4: 0.8, 5: 0.6}.get(int(self.alertSensitivity), 1.0)
