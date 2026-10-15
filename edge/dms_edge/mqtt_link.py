"""MQTT connection to the local broker (topics: docs/mqtt-contract.md)."""
from __future__ import annotations

import json
import logging
import threading
from collections import deque
from typing import Callable

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)


class MqttLink:
    def __init__(self, device_id: str, host: str, port: int, handlers: dict[str, Callable[[dict | list], None]]):
        """handlers keys: 'config', 'drivers', 'cmd/ack', 'cmd/enroll'."""
        self.base = f"dms/{device_id}"
        self.handlers = handlers
        self.connected = False
        self._pending: deque[tuple[str, str, bool]] = deque(maxlen=500)  # REL-4 style offline queue
        self._lock = threading.Lock()

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"dms-edge-{device_id}")
        self.client.will_set(f"{self.base}/status", json.dumps({"online": False}), qos=1, retain=True)
        self.client.reconnect_delay_set(1, 10)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.host, self.port = host, port

    def start(self):
        self.client.connect_async(self.host, self.port, keepalive=15)
        self.client.loop_start()
        return self

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log.error("MQTT connect refused: %s", reason_code)
            return
        self.connected = True
        log.info("MQTT connected to %s:%s as %s", self.host, self.port, self.base)
        client.subscribe([(f"{self.base}/config", 1), (f"{self.base}/drivers", 1), (f"{self.base}/cmd/#", 1)])
        with self._lock:
            while self._pending:
                topic, payload, retain = self._pending.popleft()
                client.publish(topic, payload, qos=1, retain=retain)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        log.warning("MQTT disconnected (%s); reconnecting", reason_code)

    def _on_message(self, client, userdata, msg):
        kind = msg.topic[len(self.base) + 1:]
        handler = self.handlers.get(kind)
        if not handler:
            return
        try:
            handler(json.loads(msg.payload or b"{}"))
        except Exception:  # noqa: BLE001
            log.exception("handler for %s failed", kind)

    def publish(self, kind: str, payload: dict, retain: bool = False):
        topic, body = f"{self.base}/{kind}", json.dumps(payload, default=str)
        with self._lock:
            if not self.connected:
                self._pending.append((topic, body, retain))
                return
        self.client.publish(topic, body, qos=1, retain=retain)

    def stop(self):
        self.publish("status", {"online": False}, retain=True)
        self.client.loop_stop()
        self.client.disconnect()
