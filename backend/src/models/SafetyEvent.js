const mongoose = require('mongoose');
const toJSON = require('./plugins/toJSON');
const { EVENT_TYPES, SEVERITIES, EVENT_STATUSES, EMOTIONS } = require('./constants');

const pointSchema = new mongoose.Schema(
  {
    type: { type: String, enum: ['Point'], default: 'Point' },
    coordinates: {
      type: [Number], // [lng, lat]
      required: true,
      validate: {
        validator: (c) => c.length === 2 && Math.abs(c[0]) <= 180 && Math.abs(c[1]) <= 90,
        message: 'Invalid coordinates',
      },
    },
    accuracyM: Number,
    capturedAt: Date,
  },
  { _id: false }
);

// Snapshot of the signals that caused the fusion module to raise the event.
const signalsSchema = new mongoose.Schema(
  {
    ear: Number,
    emotion: { type: String, enum: EMOTIONS },
    emotionConfidence: { type: Number, min: 0, max: 1 },
    yaw: Number,
    pitch: Number,
    roll: Number,
    sustainedMs: Number, // how long the condition held before triggering
    mouthOpen: Number, // jawOpen blendshape (or mouth aspect ratio)
    perclos: { type: Number, min: 0, max: 1 }, // share of the last minute with eyes closed
    blinkRate: Number, // blinks per minute
    blinkMs: Number, // mean duration of recent blinks
    yawns: Number, // in the last five minutes
  },
  { _id: false }
);

const safetyEventSchema = new mongoose.Schema(
  {
    // ID generated on the edge so duplicate MQTT deliveries are ignored.
    edgeEventId: { type: String, required: true, unique: true },
    owner: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
    device: { type: mongoose.Schema.Types.ObjectId, ref: 'Device', required: true },
    driver: { type: mongoose.Schema.Types.ObjectId, ref: 'DriverProfile', default: null },

    eventType: { type: String, enum: EVENT_TYPES, required: true },
    severity: { type: String, enum: SEVERITIES, required: true },
    status: { type: String, enum: EVENT_STATUSES, default: 'active' },
    description: { type: String, maxlength: 200 },
    signals: signalsSchema,
    location: pointSchema,

    detectedAt: { type: Date, required: true },
    acknowledgedAt: Date,
    acknowledgedVia: { type: String, enum: ['edge_button', 'mobile_app'] },
    acknowledgedBy: { type: mongoose.Schema.Types.ObjectId, ref: 'User' },
    escalatedAt: Date,
    resolvedAt: Date,
  },
  { timestamps: true }
);

safetyEventSchema.plugin(toJSON);

safetyEventSchema.virtual('acknowledged').get(function acknowledged() {
  return Boolean(this.acknowledgedAt);
});
safetyEventSchema.virtual('escalated').get(function escalated() {
  return Boolean(this.escalatedAt);
});
// "Action taken" column in the event log, FR7.1.
safetyEventSchema.virtual('actionTaken').get(function actionTaken() {
  if (this.escalatedAt) return 'Emergency contacts notified';
  if (this.acknowledgedAt) return 'Acknowledged by driver';
  return 'Alert raised';
});
safetyEventSchema.virtual('videoClip', {
  ref: 'VideoClip',
  localField: '_id',
  foreignField: 'event',
  justOne: true,
});

safetyEventSchema.index({ owner: 1, detectedAt: -1 }); // paginated event log
safetyEventSchema.index({ device: 1, status: 1 });
safetyEventSchema.index({ location: '2dsphere' }, { sparse: true });

module.exports = mongoose.model('SafetyEvent', safetyEventSchema);
