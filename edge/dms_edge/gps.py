"""NEO-6M (or any NMEA) GPS reader over UART/USB.

Only a fix newer than MAX_AGE is reported, so escalations never send a stale,
cached position (FR6.3).
"""
from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger(__name__)
MAX_AGE = 10.0


def _checksum_ok(sentence: str) -> bool:
    if "*" not in sentence:
        return True
    body, _, given = sentence.lstrip("$").partition("*")
    calc = 0
    for ch in body:
        calc ^= ord(ch)
    try:
        return calc == int(given[:2], 16)
    except ValueError:
        return False


def _coord(value: str, hemi: str) -> float | None:
    if not value:
        return None
    dot = value.index(".")
    deg = float(value[: dot - 2])
    minutes = float(value[dot - 2:])
    out = deg + minutes / 60.0
    return -out if hemi in ("S", "W") else out


def parse_nmea(sentence: str) -> dict | None:
    """Parse RMC/GGA sentences into {lat, lng, accuracyM?}. Returns None without a valid fix."""
    sentence = sentence.strip()
    if not sentence.startswith("$") or not _checksum_ok(sentence):
        return None
    parts = sentence.split("*")[0].split(",")
    kind = parts[0][3:]
    try:
        if kind == "RMC" and len(parts) >= 7:
            if parts[2] != "A":
                return None
            return {"lat": _coord(parts[3], parts[4]), "lng": _coord(parts[5], parts[6])}
        if kind == "GGA" and len(parts) >= 9:
            if parts[6] in ("", "0"):
                return None
            fix = {"lat": _coord(parts[2], parts[3]), "lng": _coord(parts[4], parts[5])}
            if parts[8]:
                fix["accuracyM"] = round(float(parts[8]) * 5.0, 1)  # HDOP × ~5 m UERE
            return fix
    except (ValueError, IndexError):
        return None
    return None


class GPS:
    def __init__(self, port: str, baud: int = 9600):
        self.port, self.baud = port, baud
        self._fix: dict | None = None
        self._at = 0.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="gps", daemon=True)

    def start(self):
        self._thread.start()
        return self

    def _run(self):
        try:
            import serial
        except ImportError:
            log.warning("pyserial missing; GPS disabled")
            return
        while not self._stop.is_set():
            try:
                with serial.Serial(self.port, self.baud, timeout=1) as s:
                    log.info("GPS reading %s", self.port)
                    while not self._stop.is_set():
                        line = s.readline().decode("ascii", errors="ignore")
                        fix = parse_nmea(line)
                        if fix and fix["lat"] is not None:
                            self._fix = {**(self._fix or {}), **fix}
                            self._at = time.monotonic()
            except Exception as e:  # noqa: BLE001
                log.debug("GPS unavailable on %s: %s", self.port, e)
                self._stop.wait(10)

    @property
    def position(self) -> dict | None:
        if self._fix and time.monotonic() - self._at <= MAX_AGE:
            return {**self._fix, "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        return None

    def stop(self):
        self._stop.set()
