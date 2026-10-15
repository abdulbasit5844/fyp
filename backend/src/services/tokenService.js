const crypto = require('crypto');
const jwt = require('jsonwebtoken');
const config = require('../config');

const sha256 = (s) => crypto.createHash('sha256').update(s).digest('hex');

function signAccessToken(user) {
  return jwt.sign({ sub: user.id, role: user.role }, config.jwt.secret, {
    expiresIn: config.jwt.accessTtl,
  });
}

function verifyAccessToken(token) {
  return jwt.verify(token, config.jwt.secret);
}

// Refresh tokens are opaque random strings; only their hash is stored so a
// database leak does not hand out working sessions.
function issueRefreshToken(user, userAgent) {
  const token = crypto.randomBytes(48).toString('base64url');
  const now = Date.now();
  user.refreshTokens = user.refreshTokens.filter((t) => t.expiresAt > now);
  user.refreshTokens.push({
    tokenHash: sha256(token),
    expiresAt: new Date(now + config.jwt.refreshTtlMs),
    userAgent,
  });
  return `${user.id}.${token}`;
}

function parseRefreshToken(raw) {
  const [userId, token] = String(raw || '').split('.');
  if (!userId || !token) return null;
  return { userId, tokenHash: sha256(token) };
}

async function issueSession(user, userAgent) {
  const refreshToken = issueRefreshToken(user, userAgent);
  await user.save();
  return { accessToken: signAccessToken(user), refreshToken, user };
}

module.exports = { signAccessToken, verifyAccessToken, parseRefreshToken, issueSession };
