const mongoose = require('mongoose');
const toJSON = require('./plugins/toJSON');
const { DRIVER_STATES } = require('./constants');

// A paired Raspberry Pi edge unit and the latest driver state for the home
// dashboard. The edge pipeline identifies itself by deviceId on MQTT, which
// only listens on localhost.
const deviceSchema = new mongoose.Schema(
  {
    deviceId: { type: String, required: true, unique: true, trim: true }, // e.g. "pi-vision-01"
    name: { type: String, trim: true, default: 'My Vehicle' },
    owner: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },

    online: { type: Boolean, default: false },
    lastSeenAt: Date,

    currentState: { type: String, enum: DRIVER_STATES, default: 'safe' },
    stateUpdatedAt: Date,
    activeDriver: { type: mongoose.Schema.Types.ObjectId, ref: 'DriverProfile', default: null },
    monitoring: { type: Boolean, default: false }, // true once the driver is verified

    lastLocation: {
      type: { type: String, enum: ['Point'] },
      coordinates: { type: [Number], default: undefined }, // [lng, lat]
    },
    pipelineVersion: String,
  },
  { timestamps: true }
);

deviceSchema.plugin(toJSON);
deviceSchema.index({ owner: 1 });

module.exports = mongoose.model('Device', deviceSchema);
