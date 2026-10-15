// Shared enums and limits, taken from the SRS so the API, MQTT handlers and
// validation all agree on the same values.

// SRS FR5.4 (Owner > Family Member > Guest) plus the web-dashboard actors in 2.1.
const ROLES = ['owner', 'family', 'guest', 'admin', 'fleet_manager'];

const EVENT_TYPES = [
  'drowsiness', // FR1.2
  'inattention', // FR1.4 head pose deviation
  'emotional_distress', // FR1.3 angry / fear sustained
  'unverified_driver', // face embedding did not match a known driver
  'unauthorized_occupant', // FR4.1
  'key_left_inside', // FR4.2
];

const SEVERITIES = ['warning', 'critical'];

// Overall driver state shown on the home dashboard.
const DRIVER_STATES = ['safe', 'warning', 'critical'];

// SafetyAlert lifecycle, SRS 3.4.4: Detected -> Active -> Acknowledged / Escalated -> Resolved.
const EVENT_STATUSES = ['detected', 'active', 'acknowledged', 'escalated', 'resolved'];

const EMOTIONS = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise'];

const LIMITS = {
  passwordMinLength: 8, // FR5.1
  maxFailedLogins: 5, // FR5.2
  lockDurationMs: 15 * 60 * 1000, // FR5.2
  maxEmergencyContacts: 5, // FR6.4
  earThreshold: { min: 0.2, max: 0.3, default: 0.25 }, // FR1.2
  ackWindowSec: { min: 5, max: 30, default: 15 }, // FR3.2
  headPoseDeg: { min: 15, max: 45, default: 30 }, // FR1.4
  sustainSec: { min: 1, max: 10 },
  alertSensitivity: { min: 1, max: 5, default: 3 },
};

module.exports = {
  ROLES,
  EVENT_TYPES,
  SEVERITIES,
  DRIVER_STATES,
  EVENT_STATUSES,
  EMOTIONS,
  LIMITS,
};
