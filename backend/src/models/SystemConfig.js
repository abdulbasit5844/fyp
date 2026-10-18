const mongoose = require('mongoose');
const toJSON = require('./plugins/toJSON');
const { LIMITS } = require('./constants');

const range = ({ min, max, default: def }) => ({ type: Number, min, max, default: def });

// Per-owner monitoring settings, edited from the app's Settings screen and
// pushed to the edge device (must apply within 5 s, FR7.3).
const systemConfigSchema = new mongoose.Schema(
  {
    owner: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true, unique: true },

    // Drowsiness, FR1.2
    earThreshold: range(LIMITS.earThreshold),
    earSustainSec: range({ ...LIMITS.sustainSec, default: 2 }),
    // Inattention, FR1.4
    headPoseThresholdDeg: range(LIMITS.headPoseDeg), // left / right
    headPitchThresholdDeg: range(LIMITS.headPitchDeg), // up / down
    headPoseSustainSec: range({ ...LIMITS.sustainSec, default: 2 }),
    // Emotion, FR1.3
    emotionSustainSec: range({ ...LIMITS.sustainSec, default: 3 }),
    // Acknowledgment window before escalation, FR3.2
    ackWindowSec: range(LIMITS.ackWindowSec),
    // 1 = least sensitive, 5 = most; scales the fusion module's thresholds.
    alertSensitivity: range(LIMITS.alertSensitivity),

    videoRecordingEnabled: { type: Boolean, default: true },
    notifications: {
      push: { type: Boolean, default: true },
      sound: { type: Boolean, default: true },
      smsFallback: { type: Boolean, default: false },
      whatsapp: { type: Boolean, default: true }, // escalations to every contact by WhatsApp
    },

    // Bumped on every change so the edge can tell whether it has the latest.
    revision: { type: Number, default: 1 },
  },
  { timestamps: true }
);

systemConfigSchema.plugin(toJSON);

systemConfigSchema.pre('save', function bumpRevision() {
  if (!this.isNew && this.isModified()) this.revision += 1;
});

module.exports = mongoose.model('SystemConfig', systemConfigSchema);
