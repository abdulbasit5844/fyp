const { User, SystemConfig } = require('../models');
const ApiError = require('../utils/ApiError');
const { issueSession, parseRefreshToken } = require('../services/tokenService');

// FR5.1 – registration always creates an owner account with default settings.
async function register(req, res) {
  const { name, email, password } = req.body || {};
  if (!name || !email || !password) throw ApiError.badRequest('name, email and password are required');

  const normalized = String(email).toLowerCase().trim();
  if (await User.exists({ email: normalized })) {
    throw ApiError.conflict('An account with this email already exists');
  }

  const user = new User({ name, email: normalized, role: 'owner' });
  try {
    await user.setPassword(password);
  } catch (e) {
    throw ApiError.badRequest(e.message);
  }
  await user.validate();
  await user.save();
  await SystemConfig.create({ owner: user._id });

  const session = await issueSession(user, req.get('user-agent'));
  res.status(201).json(session);
}

// FR5.2 – login with lockout after 5 failures.
async function login(req, res) {
  const { email, password } = req.body || {};
  if (!email || !password) throw ApiError.badRequest('email and password are required');

  const user = await User.findOne({ email: String(email).toLowerCase().trim() }).select(
    '+passwordHash +failedLoginAttempts +lockUntil +refreshTokens'
  );
  if (!user || !user.isActive) throw ApiError.unauthorized('Invalid email or password');
  if (user.isLocked) {
    const mins = Math.ceil((user.lockUntil - Date.now()) / 60000);
    throw ApiError.locked(`Account locked after too many failed attempts. Try again in ${mins} min.`);
  }

  if (!(await user.comparePassword(password))) {
    user.registerFailedLogin();
    await user.save();
    if (user.isLocked) throw ApiError.locked('Account locked for 15 minutes after 5 failed attempts.');
    throw ApiError.unauthorized('Invalid email or password');
  }

  user.registerSuccessfulLogin();
  res.json(await issueSession(user, req.get('user-agent')));
}

// FR5.3 – exchange a refresh token for a new pair (the old one is revoked).
async function refresh(req, res) {
  const parsed = parseRefreshToken(req.body?.refreshToken);
  if (!parsed) throw ApiError.unauthorized('Invalid refresh token');

  const user = await User.findById(parsed.userId).select('+refreshTokens').catch(() => null);
  const stored = user?.refreshTokens.find(
    (t) => t.tokenHash === parsed.tokenHash && t.expiresAt > Date.now()
  );
  if (!user || !user.isActive || !stored) throw ApiError.unauthorized('Invalid or expired refresh token');

  user.refreshTokens.pull(stored._id);
  res.json(await issueSession(user, req.get('user-agent')));
}

async function logout(req, res) {
  const parsed = parseRefreshToken(req.body?.refreshToken);
  if (parsed) {
    await User.updateOne(
      { _id: parsed.userId },
      { $pull: { refreshTokens: { tokenHash: parsed.tokenHash } } }
    ).catch(() => {});
  }
  res.status(204).end();
}

function me(req, res) {
  res.json(req.user);
}

// Register / remove this phone's Firebase token for push alerts.
async function addFcmToken(req, res) {
  const { token } = req.body || {};
  if (!token) throw ApiError.badRequest('token is required');
  await User.updateOne({ _id: req.user._id }, { $addToSet: { fcmTokens: token } });
  res.status(204).end();
}

async function removeFcmToken(req, res) {
  await User.updateOne({ _id: req.user._id }, { $pull: { fcmTokens: req.body?.token } });
  res.status(204).end();
}

module.exports = { register, login, refresh, logout, me, addFcmToken, removeFcmToken };
