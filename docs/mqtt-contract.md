# MQTT contract: edge pipeline ⇄ backend

Broker: Mosquitto on the Pi, `127.0.0.1:1883`, localhost only. Every payload is JSON.
`{id}` is the edge device ID (e.g. `pi-vision-01`). Timestamps are ISO-8601 UTC strings.

## Edge → backend

| Topic | QoS / retain | Payload |
|---|---|---|
| `dms/{id}/status` | 1, retained; also the Last Will with `{"online": false}` | `{online, state: "safe"\|"warning"\|"critical", monitoring, driverId?, location?: {lat, lng, accuracyM}, pipelineVersion, ts}` |
| `dms/{id}/event` | 1 | `{eventId, type, severity: "warning"\|"critical", detectedAt, description?, driverId?, signals?: {ear, emotion, emotionConfidence, yaw, pitch, roll, sustainedMs}, location?}` |
| `dms/{id}/event/ack` | 1 | `{eventId, ts}`: driver pressed the physical button |
| `dms/{id}/event/escalate` | 1 | `{eventId, location?: {lat, lng, accuracyM, capturedAt}, ts}`: acknowledgment window expired |
| `dms/{id}/event/resolve` | 1 | `{eventId, ts}`: condition cleared (warnings only) |
| `dms/{id}/clip` | 1 | `{eventId, filePath, status: "available"\|"deleted", sizeBytes?, durationSec?, preEventSec?, postEventSec?, startedAt?}` |
| `dms/{id}/enrollment` | 1 | Result: `{driverId, status: "done"\|"failed", ok, vector?, model?, error?}`. While capturing, every 0.5 s: `{driverId, status: "progress", samples, needed, faceVisible, secondsLeft, preview}` (`preview` = base64 JPEG, 320 px wide) |

`type` is one of `drowsiness`, `inattention`, `emotional_distress`, `unverified_driver`,
`unauthorized_occupant`, `key_left_inside`.

## Backend → edge

| Topic | QoS / retain | Payload |
|---|---|---|
| `dms/{id}/config` | 1, retained | `{earThreshold, earSustainSec, headPoseThresholdDeg, headPoseSustainSec, emotionSustainSec, ackWindowSec, alertSensitivity, videoRecordingEnabled, notifications, revision}` |
| `dms/{id}/drivers` | 1, retained | `[{id, displayName, isAuthorized, embeddings: [{vector, model}]}]` |
| `dms/{id}/cmd/ack` | 1 | `{eventId}`: acknowledged from the mobile app; the edge stops the alarm and cancels escalation |
| `dms/{id}/cmd/detection` | 1, retained | `{enabled}`: Start/Stop detecting from the app. Stopped: no detection, recording or alerts (enrollment still works); open alerts are resolved |
| `dms/{id}/cmd/enroll` | 1 | `{driverId}`: capture the current face and reply on `dms/{id}/enrollment` |

## Alert lifecycle

```
edge detects sustained condition ─► event (status active) ─► buzzer/LED + app alert
        │                                   │
        │ button press / app ack ◄──────────┤
        ▼                                   ▼ ackWindowSec expires (critical only)
   acknowledged                        escalate ─► backend sends GPS to emergency contacts
```

The edge owns the acknowledgment timer. The backend ignores an escalation for an
event that is already acknowledged, which handles the race between a late app
acknowledgment and the timer firing.
