const mongoose = require('mongoose');
const toJSON = require('./plugins/toJSON');

// One row per notification attempt (SRS 3.5 AlertLog), so the escalation
// screen can show who was notified and whether delivery succeeded.
const alertLogSchema = new mongoose.Schema(
  {
    event: { type: mongoose.Schema.Types.ObjectId, ref: 'SafetyEvent', required: true },
    owner: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
    alertType: { type: String, enum: ['alert', 'escalation'], required: true },
    channel: { type: String, enum: ['push', 'sms', 'email'], required: true },

    recipientUser: { type: mongoose.Schema.Types.ObjectId, ref: 'User' },
    recipientContact: { type: mongoose.Schema.Types.ObjectId, ref: 'EmergencyContact' },

    deliveryStatus: { type: String, enum: ['pending', 'sent', 'failed'], default: 'pending' },
    providerMessageId: String,
    error: String,
    attempts: { type: Number, default: 0 },
    sentAt: Date,
  },
  { timestamps: true }
);

alertLogSchema.plugin(toJSON);
alertLogSchema.index({ event: 1 });

module.exports = mongoose.model('AlertLog', alertLogSchema);
