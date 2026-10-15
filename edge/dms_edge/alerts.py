"""Buzzer/LED alerts, the acknowledgment button and the escalation timer.

Critical alerts sound until the driver acknowledges (GPIO button or mobile
app) or ackWindowSec passes, which triggers escalation (FR3.1-FR3.3).
Warnings give a short beep and clear on their own when the condition ends.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger(__name__)


class _ConsoleOutput:
    """Stand-in when GPIO is unavailable (laptop / no hardware wired)."""

    def __init__(self, name):
        self.name, self.state = name, "off"

    def _set(self, state):
        if state != self.state:
            log.info("[%s] %s", self.name, state)
            self.state = state

    def on(self): self._set("on")
    def off(self): self._set("off")
    def blink(self, on_time=0.5, off_time=0.5, n=None, background=True): self._set(f"blink {on_time}/{off_time}" + (f" x{n}" if n else ""))
    def beep(self, on_time=0.5, off_time=0.5, n=None, background=True): self.blink(on_time, off_time, n)
    def close(self): pass


def _hardware(buzzer_pin, led_pin, button_pin, on_press):
    try:
        from gpiozero import LED, Button, Buzzer

        buzzer, led, button = Buzzer(buzzer_pin), LED(led_pin), Button(button_pin, bounce_time=0.05)
        button.when_pressed = on_press
        log.info("GPIO ready: buzzer=%s led=%s button=%s", buzzer_pin, led_pin, button_pin)
        return buzzer, led, button
    except Exception as e:  # noqa: BLE001
        log.warning("GPIO unavailable (%s); alerts go to the log", e)
        return _ConsoleOutput("buzzer"), _ConsoleOutput("led"), None


@dataclass
class OpenAlert:
    event_id: str
    type: str
    severity: str
    raised_at: float
    deadline: float | None  # escalation time for critical alerts


class AlertManager:
    def __init__(self, cfg, on_ack: Callable[[str], None], on_escalate: Callable[[str], None],
                 pins=(17, 27, 22), clock=time.monotonic, hardware=True):
        self.cfg = cfg
        self.on_ack, self.on_escalate, self.clock = on_ack, on_escalate, clock
        self.open: dict[str, OpenAlert] = {}
        self._lock = threading.RLock()
        self._retry_at: float | None = None
        if hardware:
            self.buzzer, self.led, self.button = _hardware(*pins, on_press=self.button_pressed)
        else:
            self.buzzer, self.led, self.button = _ConsoleOutput("buzzer"), _ConsoleOutput("led"), None

    # --- outputs (REL-3: failures are logged and retried within 2 s) ---

    def _drive_outputs(self):
        try:
            critical = any(a.severity == "critical" for a in self.open.values())
            if critical:
                if self.cfg.notifications.get("sound", True):
                    self.buzzer.beep(0.3, 0.2, background=True)
                else:
                    self.buzzer.off()
                self.led.blink(0.2, 0.2, background=True)
            elif self.open:
                self.buzzer.off()
                self.led.blink(0.6, 0.6, background=True)
            else:
                self.buzzer.off()
                self.led.off()
            self._retry_at = None
        except Exception as e:  # noqa: BLE001
            log.error("alert output failed: %s; retrying", e)
            self._retry_at = self.clock() + 2.0

    # --- public API ---

    def raise_alert(self, event_id, type_, severity):
        with self._lock:
            now = self.clock()
            deadline = now + float(self.cfg.ackWindowSec) if severity == "critical" else None
            self.open[event_id] = OpenAlert(event_id, type_, severity, now, deadline)
            if severity == "warning" and self.cfg.notifications.get("sound", True):
                try:
                    self.buzzer.beep(0.15, 0.15, n=2, background=True)
                except Exception as e:  # noqa: BLE001
                    log.error("buzzer failed: %s", e)
            self._drive_outputs()

    def button_pressed(self):
        """Physical button acknowledges every open alert."""
        with self._lock:
            ids = list(self.open)
            for eid in ids:
                self.open.pop(eid)
            self._drive_outputs()
        for eid in ids:
            log.info("alert %s acknowledged by button", eid)
            self.on_ack(eid)

    def acknowledge(self, event_id):
        """Acknowledged from the mobile app (cmd/ack); no need to report back."""
        with self._lock:
            if self.open.pop(event_id, None):
                log.info("alert %s acknowledged from app", event_id)
                self._drive_outputs()

    def resolve(self, event_id):
        with self._lock:
            if self.open.pop(event_id, None):
                self._drive_outputs()

    def tick(self):
        """Call regularly; fires escalations whose window has expired."""
        expired = []
        with self._lock:
            now = self.clock()
            for a in list(self.open.values()):
                if a.deadline is not None and now >= a.deadline:
                    expired.append(a.event_id)
                    self.open.pop(a.event_id)
            if expired or (self._retry_at and now >= self._retry_at):
                self._drive_outputs()
        for eid in expired:
            log.warning("alert %s not acknowledged in %ss: escalating", eid, self.cfg.ackWindowSec)
            self.on_escalate(eid)

    def close(self):
        for dev in (self.buzzer, self.led, self.button):
            try:
                if dev:
                    dev.close()
            except Exception:  # noqa: BLE001
                pass
