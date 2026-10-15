const mongoose = require('mongoose');
const toJSON = require('./plugins/toJSON');
const { LIMITS } = require('./constants');

const emergencyContactSchema = new mongoose.Schema(
  {
    owner: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
    name: { type: String, required: true, trim: true, maxlength: 100 },
    phone: {
      type: String,
      required: true,
      trim: true,
      match: [/^\+[1-9]\d{7,14}$/, 'Phone must be in international format, e.g. +923001234567'],
    },
    email: {
      type: String,
      lowercase: true,
      trim: true,
      match: [/^[^\s@]+@[^\s@]+\.[^\s@]+$/, 'Invalid email address'],
    },
    relationship: { type: String, trim: true, maxlength: 50 },
    priority: { type: Number, min: 1, max: LIMITS.maxEmergencyContacts, default: 1 },
    // If the contact also uses the app, escalations go to their FCM tokens;
    // otherwise SMS is the fallback (SRS 2.4, <<extend>> Send SMS).
    linkedUser: { type: mongoose.Schema.Types.ObjectId, ref: 'User', default: null },
    notifyBySms: { type: Boolean, default: true },
  },
  { timestamps: true }
);

emergencyContactSchema.plugin(toJSON);

emergencyContactSchema.index({ owner: 1, phone: 1 }, { unique: true });

// FR6.4: at most 5 contacts per owner.
emergencyContactSchema.pre('validate', async function enforceLimit() {
  if (!this.isNew) return;
  const count = await this.constructor.countDocuments({ owner: this.owner });
  if (count >= LIMITS.maxEmergencyContacts) {
    this.invalidate('owner', `A maximum of ${LIMITS.maxEmergencyContacts} emergency contacts is allowed`);
  }
});

module.exports = mongoose.model('EmergencyContact', emergencyContactSchema);
