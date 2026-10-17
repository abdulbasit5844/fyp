const mongoose = require('mongoose');
const toJSON = require('./plugins/toJSON');

// Metadata for a 30-second clip (15 s before + 15 s after) recorded on the Pi
// for a confirmed safety event, FR4.3. The file itself stays on local disk.
const videoClipSchema = new mongoose.Schema(
  {
    event: { type: mongoose.Schema.Types.ObjectId, ref: 'SafetyEvent', required: true, unique: true },
    owner: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
    device: { type: mongoose.Schema.Types.ObjectId, ref: 'Device', required: true },

    filePath: { type: String, required: true, private: true }, // absolute path on the Pi
    mimeType: { type: String, default: 'video/mp4' },
    sizeBytes: { type: Number, min: 0 },
    durationSec: { type: Number, default: 30 },
    preEventSec: { type: Number, default: 15 },
    postEventSec: { type: Number, default: 15 },
    startedAt: { type: Date, required: true },

    // Old clips are removed when storage passes 80%; the record is kept so
    // the event log can still say a clip existed.
    status: { type: String, enum: ['recording', 'available', 'deleted'], default: 'recording' },
    deletedAt: Date,
  },
  { timestamps: true }
);

videoClipSchema.plugin(toJSON);
videoClipSchema.index({ owner: 1, createdAt: -1 });
videoClipSchema.index({ status: 1, createdAt: 1 }); // oldest-first cleanup

module.exports = mongoose.model('VideoClip', videoClipSchema);
