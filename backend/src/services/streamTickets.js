const crypto = require('crypto');

// Short-lived passwords for the live view's RTSP URL. The app's JWT cannot be
// used there: FFmpeg-based players (the app's video player) cut RTSP credentials
// to 127 characters. A ticket is valid for one device and expires TTL after the
// app's last keep-alive. Kept in memory: a backend restart just means the app
// asks again.
const TTL_MS = 2 * 60 * 1000;
const tickets = new Map(); // ticket -> { ownerId, deviceId, expiresAt }

function issue(ownerId, deviceId) {
  const now = Date.now();
  for (const [t, v] of tickets) {
    if (v.expiresAt <= now) tickets.delete(t);
    else if (v.deviceId === deviceId && String(v.ownerId) === String(ownerId)) {
      v.expiresAt = now + TTL_MS; // keep-alive: same ticket, so the player keeps its URL
      return t;
    }
  }
  const ticket = crypto.randomBytes(18).toString('base64url'); // 24 characters
  tickets.set(ticket, { ownerId: String(ownerId), deviceId, expiresAt: now + TTL_MS });
  return ticket;
}

function check(ticket, deviceId) {
  const v = tickets.get(ticket || '');
  return Boolean(v && v.deviceId === deviceId && v.expiresAt > Date.now());
}

function revoke(ownerId, deviceId) {
  for (const [t, v] of tickets) {
    if (v.deviceId === deviceId && v.ownerId === String(ownerId)) tickets.delete(t);
  }
}

module.exports = { issue, check, revoke, TTL_MS };
