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


class _OpenCVSource:
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
    def __init__(self, width, height, fps):
        from picamera2 import Picamera2  # only on the Pi

        self.cam = Picamera2()
        cfg = self.cam.create_video_configuration(
            main={"size": (width, height), "format": "RGB888"},  # RGB888 is BGR in memory
            controls={"FrameRate": fps},
        )
        self.cam.configure(cfg)
        self.cam.start()

    def read(self):
        return self.cam.capture_array("main")

    def close(self):
        self.cam.stop()
        self.cam.close()


def _open(source, width, height, fps):
    if source in ("auto", "picamera"):
        try:
            return _PiCameraSource(width, height, fps)
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

    def start(self):
        self._thread.start()
        return self

    def _run(self):
        t0, n = time.monotonic(), 0
        while not self._stop.is_set():
            if self._src is None:
                try:
                    self._src = _open(*self.args)
                    self.connected = True
                    log.info("camera opened: %s", self.args[0])
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
