"""Event-triggered clips: 15 s before + 15 s after the trigger (FR4.3).

Frames are kept JPEG-compressed in a ring buffer (~10 MB at 640x480, 15 fps).
When storage use passes the limit (80 %), the oldest clips are deleted.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

log = logging.getLogger(__name__)


class _Pending:
    def __init__(self, event_id, frames, until, mono_now):
        self.event_id, self.frames, self.until = event_id, frames, until
        self._mono, self._wall = mono_now, time.time()

    def started_at(self, mono_ts: float) -> str:
        """Wall-clock ISO time of a monotonic frame timestamp."""
        wall = self._wall - (self._mono - mono_ts)
        return datetime.fromtimestamp(wall, timezone.utc).isoformat().replace("+00:00", "Z")


class ClipRecorder:
    def __init__(self, clips_dir: Path, on_clip: Callable[[dict], None], fps=15, pre_sec=15, post_sec=15,
                 storage_limit=0.8, clock=time.monotonic):
        self.dir = Path(clips_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.on_clip, self.fps, self.pre, self.post = on_clip, fps, pre_sec, post_sec
        self.limit, self.clock = storage_limit, clock
        self.buffer: deque[tuple[float, bytes]] = deque()
        self.pending: list[_Pending] = []
        self._ffmpeg = shutil.which("ffmpeg")

    def push(self, frame: np.ndarray):
        now = self.clock()
        ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            return
        item = (now, jpg.tobytes())
        self.buffer.append(item)
        while self.buffer and now - self.buffer[0][0] > self.pre:
            self.buffer.popleft()

        for p in list(self.pending):
            p.frames.append(item)
            if now >= p.until:
                self.pending.remove(p)
                threading.Thread(target=self._write, args=(p,), name=f"clip-{p.event_id}", daemon=True).start()

    def trigger(self, event_id: str):
        if any(p.event_id == event_id for p in self.pending):
            return
        now = self.clock()
        self.pending.append(_Pending(event_id, list(self.buffer), now + self.post, now))

    def _write(self, p: _Pending):
        if not p.frames:
            return
        path = self.dir / f"{p.event_id}.mp4"
        duration = p.frames[-1][0] - p.frames[0][0]
        fps = max(1.0, (len(p.frames) - 1) / duration) if duration > 0 else float(self.fps)
        try:
            self._encode(path, p.frames, fps)
        except Exception as e:  # noqa: BLE001
            log.error("clip %s failed: %s", path.name, e)
            return
        log.info("clip saved %s (%.1fs, %d frames)", path.name, duration, len(p.frames))
        self.on_clip({
            "eventId": p.event_id,
            "filePath": str(path.resolve()),
            "status": "available",
            "sizeBytes": path.stat().st_size,
            "durationSec": round(duration, 1),
            "preEventSec": self.pre,
            "postEventSec": self.post,
            "startedAt": p.started_at(p.frames[0][0]),
        })
        self.enforce_storage()

    def _encode(self, path: Path, frames, fps):
        if self._ffmpeg:  # H.264 plays everywhere, including Android/Flutter
            cmd = [self._ffmpeg, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", f"{fps:.2f}",
                   "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                   "-movflags", "+faststart", str(path)]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            for _, jpg in frames:
                proc.stdin.write(jpg)
            proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError("ffmpeg exited with an error")
            return
        first = cv2.imdecode(np.frombuffer(frames[0][1], np.uint8), cv2.IMREAD_COLOR)
        h, w = first.shape[:2]
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        for _, jpg in frames:
            writer.write(cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR))
        writer.release()

    def enforce_storage(self):
        def usage():
            u = shutil.disk_usage(self.dir)
            return u.used / u.total

        clips = sorted(self.dir.glob("*.mp4"), key=lambda f: f.stat().st_mtime)
        while clips and usage() > self.limit:
            old = clips.pop(0)
            old.unlink(missing_ok=True)
            log.info("storage over %.0f%%: deleted %s", self.limit * 100, old.name)
            self.on_clip({"eventId": old.stem, "filePath": str(old.resolve()), "status": "deleted"})
