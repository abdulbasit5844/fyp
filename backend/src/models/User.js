const mongoose = require('mongoose');
const bcrypt = require('bcryptjs');
const toJSON = require('./plugins/toJSON');
const { ROLES, LIMITS } = require('./constants');

const BCRYPT_COST = 12; // SEC-2

const refreshTokenSchema = new mongoose.Schema(
  {
    tokenHash: { type: String, required: true }, // SHA-256 of the token, never the token itself
    expiresAt: { type: Date, required: true }, // 7 days, FR5.3
    userAgent: String,
  },
  { _id: true, timestamps: { createdAt: true, updatedAt: false } }
);

const userSchema = new mongoose.Schema(
  {
    name: { type: String, required: true, trim: true, maxlength: 100 },
    email: {
      type: String,
      required: true,
      unique: true,
      lowercase: true,
      trim: true,
      match: [/^[^\s@]+@[^\s@]+\.[^\s@]+$/, 'Invalid email address'],
    },
    passwordHash: { type: String, required: true, select: false, private: true },
    role: { type: String, enum: ROLES, default: 'owner' },
    // Family members and guests belong to an owner's vehicle (Module 5 FE-3).
    owner: { type: mongoose.Schema.Types.ObjectId, ref: 'User', default: null },

    isActive: { type: Boolean, default: true },
    deactivatedAt: { type: Date, default: null }, // data kept 90 days after this, FR8.3

    failedLoginAttempts: { type: Number, default: 0, select: false, private: true },
    lockUntil: { type: Date, default: null, select: false, private: true },
    refreshTokens: { type: [refreshTokenSchema], default: [], select: false, private: true },

    // Firebase Cloud Messaging registration tokens for this user's devices.
    fcmTokens: { type: [String], default: [], private: true },
    lastLoginAt: Date,
  },
  { timestamps: true }
);

userSchema.plugin(toJSON);

userSchema.virtual('isLocked').get(function isLocked() {
  return Boolean(this.lockUntil && this.lockUntil > Date.now());
});

userSchema.methods.setPassword = async function setPassword(plain) {
  if (typeof plain !== 'string' || plain.length < LIMITS.passwordMinLength) {
    throw new Error(`Password must be at least ${LIMITS.passwordMinLength} characters`);
  }
  this.passwordHash = await bcrypt.hash(plain, BCRYPT_COST);
};

userSchema.methods.comparePassword = function comparePassword(plain) {
  return bcrypt.compare(plain, this.passwordHash);
};

userSchema.methods.registerFailedLogin = function registerFailedLogin() {
  this.failedLoginAttempts += 1;
  if (this.failedLoginAttempts >= LIMITS.maxFailedLogins) {
    this.lockUntil = new Date(Date.now() + LIMITS.lockDurationMs);
    this.failedLoginAttempts = 0;
  }
};

userSchema.methods.registerSuccessfulLogin = function registerSuccessfulLogin() {
  this.failedLoginAttempts = 0;
  this.lockUntil = null;
  this.lastLoginAt = new Date();
};

userSchema.index({ owner: 1 });

module.exports = mongoose.model('User', userSchema);
