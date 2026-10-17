"""Threaded frame capture from the Pi camera (picamera2) or any OpenCV source.

A background thread always holds the newest frame, so slow inference never
builds a backlog. If the feed drops, the source is reopened (REL-2: < 5 s).
"""
from __future__ import annotations

import logging
import threading
import time

import cv2
import numpy as np

log = logging.getLogger(__name__)


# Live view qualities: stream size, frame rate (the OV5647's limit for that size)
# and H.264 bitrate. The AI always reads a ~640-wide copy (the "lores" stream),
# so a bigger stream does not slow detection down.
LIVE_QUALITIES = {
    # "sensor" pins the OV5647 mode; left alone, libcamera picks the 1080p mode
    # (32.8 fps max) for 720p because it is 16:9.
    "480p": {"size": (640, 480), "fps": 60, "bitrate": 4_000_000, "ai": None, "sensor": (640, 480)},  # 62.5 max
    "720p": {"size": (1280, 720), "fps": 46, "bitrate": 10_000_000, "ai": (640, 360), "sensor": (1296, 972)},  # 46.3
    "1080p": {"size": (1920, 1080), "fps": 30, "bitrate": 15_000_000, "ai": (640, 360), "sensor": (1920, 1080)},  # 32.8
}
DEFAULT_QUALITY = "480p"


class _OpenCVSource:
    supports_live = False

    def __init__(self, src, width, height, fps):
        self.cap = cv2.VideoCapture(int(src) if str(src).isdigit() else src)
        self.is_file = not str(src).isdigit() and not str(src).startswith(("rtsp:", "http:"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        if not self.cap.isOpened():
            raise RuntimeError(f"cannot open video source {src!r}")
        self.period = 1.0 / fps if self.is_file else 0.0

    def read(self):
        ok, frame = self.cap.read()
        if not ok and self.is_file:  # loop test videos
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.cap.read()
        if self.period:
            time.sleep(self.period)
        return frame if ok else None

    def close(self):
        self.cap.release()


class _PiCameraSource:
    """Pi camera. In live mode it also streams: 640x480 at LIVE_FPS through the
    Pi's hardware H.264 encoder to the local MediaMTX server (RTSP), and the AI
    keeps reading the same frames."""

    supports_live = True

    def __init__(self, width, height, fps, live: tuple[str, str] | None = None):
        from picamera2 import Picamera2  # only on the Pi

        self.live = live  # (rtsp url, quality) or None
        self.cam = Picamera2()
        if live is None:
            cfg = self.cam.create_video_configuration(
                main={"size": (width, height), "format": "RGB888"},  # RGB888 is BGR in memory
                controls={"FrameRate": fps},
            )
            self.cam.configure(cfg)
            self.cam.start()
            return

        from picamera2.encoders import H264Encoder
        from picamera2.outputs import FfmpegOutput

        url, quality = live
        q = LIVE_QUALITIES[quality]
        self.ai_stream = "lores" if q["ai"] else "main"
        cfg = self.cam.create_video_configuration(
            main={"size": q["size"], "format": "YUV420"},  # the encoder's native input
            lores={"size": q["ai"], "format": "YUV420"} if q["ai"] else None,
            sensor={"output_size": q["sensor"], "bit_depth": 10},
            # A little more sharpness/contrast than the defaults for a clearer picture.
            controls={"FrameRate": q["fps"], "Sharpness": 1.5, "Contrast": 1.1},
            buffer_count=6,
        )
        self.cam.configure(cfg)
        # Key frame every second so a viewer can join quickly; repeat SPS/PPS for late joiners.
        # High profile: better quality per bit than the default baseline profile.
        encoder = H264Encoder(bitrate=q["bitrate"], repeat=True, iperiod=q["fps"], profile="high")
        self.cam.start_recording(encoder, FfmpegOutput(f"-f rtsp -rtsp_transport tcp {url}"), name="main")

    def read(self):
        if self.live is None:
            return self.cam.capture_array("main")
        return cv2.cvtColor(self.cam.capture_array(self.ai_stream), cv2.COLOR_YUV2BGR_I420)

    def close(self):
        if self.live is not None:
            self.cam.stop_recording()
        else:
            self.cam.stop()
        self.cam.close()


def _open(source, width, height, fps, live=None):
    if source in ("auto", "picamera"):
        try:
            return _PiCameraSource(width, height, fps, live)
        except Exception as e:  # noqa: BLE001 - fall back to USB camera
            if source == "picamera":
                raise
            log.info("picamera2 unavailable (%s); trying USB camera 0", e)
            source = "0"
    return _OpenCVSource(source, width, height, fps)


class Camera:
    def __init__(self, source="auto", width=640, height=480, fps=15):
        self.args = (source, width, height, fps)
        self._src = None
        self._frame: np.ndarray | None = None
        self._frame_id = 0
        self._lock = threading.Condition()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="camera", daemon=True)
        self.fps = 0.0
        self.connected = False
        self._live: tuple[str, str] | None = None  # (rtsp url, quality): stream there

    @property
    def live(self) -> bool:
        return bool(self._src is not None and getattr(self._src, "live", None))

    @property
    def live_quality(self) -> str | None:
        live = getattr(self._src, "live", None) if self._src is not None else None
        return live[1] if live else None

    def set_live(self, url: str | None, quality: str = DEFAULT_QUALITY):
        """Start (url) or stop (None) live streaming, or change its quality;
        applied by the camera thread."""
        if quality not in LIVE_QUALITIES:
            quality = DEFAULT_QUALITY
        self._live = (url, quality) if url else None

    def start(self):
        self._thread.start()
        return self

    def _run(self):
        t0, n = time.monotonic(), 0
        while not self._stop.is_set():
            want = self._live
            if self._src is not None and want != getattr(self._src, "live", None):
                if getattr(self._src, "supports_live", False) or want is None:
                    log.info("camera switching to %s", "live %s (%d fps)" % (want[1], LIVE_QUALITIES[want[1]]["fps"])
                             if want else "normal mode")
                    self._src.close()
                    self._src = None
            if self._src is None:
                try:
                    self._src = _open(*self.args, live=self._live)
                    self.connected = True
                    log.info("camera opened: %s%s", self.args[0], " (live)" if self.live else "")
                except Exception as e:  # noqa: BLE001
                    self.connected = False
                    log.warning("camera unavailable: %s (retrying)", e)
                    self._stop.wait(2.0)
                    continue

            frame = self._src.read()
            if frame is None:
                log.warning("camera feed lost; reopening")
                self.connected = False
                try:
                    self._src.close()
                finally:
                    self._src = None
                continue

            with self._lock:
                self._frame = frame
                self._frame_id += 1
                self._lock.notify_all()
            n += 1
            if (dt := time.monotonic() - t0) >= 2.0:
                self.fps, t0, n = n / dt, time.monotonic(), 0

    def read(self, last_id=0, timeout=1.0):
        """Block until a frame newer than last_id exists. Returns (frame, id) or (None, last_id)."""
        with self._lock:
            self._lock.wait_for(lambda: self._frame_id != last_id or self._stop.is_set(), timeout)
            if self._frame_id == last_id:
                return None, last_id
            return self._frame, self._frame_id

    def stop(self):
        self._stop.set()
        with self._lock:
            self._lock.notify_all()
        self._thread.join(timeout=3)
        if self._src:
            self._src.close()
