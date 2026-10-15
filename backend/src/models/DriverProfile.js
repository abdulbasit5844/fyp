const mongoose = require('mongoose');
const toJSON = require('./plugins/toJSON');

// People allowed to drive the vehicle. The edge pipeline compares the face in
// the camera against these embeddings before monitoring starts; anyone who
// does not match is treated as unverified / unauthorized (FR4.1).
const faceEmbeddingSchema = new mongoose.Schema(
  {
    vector: {
      type: [Number],
      required: true,
      validate: {
        validator: (v) => v.length >= 64 && v.length <= 1024,
        message: 'Embedding must have between 64 and 1024 dimensions',
      },
    },
    model: { type: String, required: true }, // e.g. "mobilefacenet-128"
  },
  { _id: true, timestamps: { createdAt: true, updatedAt: false } }
);

const driverProfileSchema = new mongoose.Schema(
  {
    owner: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
    // Set when the driver also has an app account (e.g. a family member).
    user: { type: mongoose.Schema.Types.ObjectId, ref: 'User', default: null },
    displayName: { type: String, required: true, trim: true, maxlength: 100 },
    isPrimary: { type: Boolean, default: false },
    isAuthorized: { type: Boolean, default: true },
    // Biometric data stays on the Pi; never returned by the API.
    faceEmbeddings: { type: [faceEmbeddingSchema], default: [], select: false, private: true },
    lastVerifiedAt: Date,
  },
  { timestamps: true }
);

driverProfileSchema.plugin(toJSON);

driverProfileSchema.virtual('enrolled').get(function enrolled() {
  return this.faceEmbeddings ? this.faceEmbeddings.length > 0 : undefined;
});

driverProfileSchema.index({ owner: 1 });
driverProfileSchema.index(
  { owner: 1, isPrimary: 1 },
  { unique: true, partialFilterExpression: { isPrimary: true } }
);

module.exports = mongoose.model('DriverProfile', driverProfileSchema);
