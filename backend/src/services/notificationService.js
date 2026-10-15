const fs = require('fs');
const config = require('../config');
const { User, EmergencyContact, AlertLog, SystemConfig } = require('../models');

// --- Providers (both optional; missing credentials are logged, not fatal) ---

let messaging = null;
function fcm() {
  if (messaging !== null) return messaging;
  messaging = false;
  if (!config.firebaseServiceAccount) {
    console.warn('[notify] FIREBASE_SERVICE_ACCOUNT not set; push notifications disabled');
    return messaging;
  }
  try {
    const admin = require('firebase-admin');
    const creds = JSON.parse(fs.readFileSync(config.firebaseServiceAccount, 'utf8'));
    admin.initializeApp({ credential: admin.credential.cert(creds) });
    messaging = admin.messaging();
  } catch (e) {
    console.error('[notify] Firebase init failed:', e.message);
  }
  return messaging;
}

async function sendPush(tokens, { title, body, data }) {
  const m = fcm();
  if (!m) return { ok: false, error: 'Push not configured' };
  if (!tokens.length) return { ok: false, error: 'Recipient has no registered device' };
  const res = await m.sendEachForMulticast({
    tokens,
    notification: { title, body },
    data: Object.fromEntries(Object.entries(data || {}).map(([k, v]) => [k, String(v)])),
    android: { priority: 'high', notification: { channelId: 'dms_alerts', sound: 'default' } },
  });
  // Forget tokens Firebase says are dead.
  const dead = res.responses
    .map((r, i) => (!r.success && /registration-token-not-registered|invalid-argument/.test(r.error?.code) ? tokens[i] : null))
    .filter(Boolean);
  if (dead.length) await User.updateMany({}, { $pull: { fcmTokens: { $in: dead } } });
  return res.successCount > 0
    ? { ok: true, id: res.responses.find((r) => r.success)?.messageId }
    : { ok: false, error: res.responses[0]?.error?.message || 'All sends failed' };
}

async function sendSms(to, body) {
  const { accountSid, authToken, from } = config.twilio;
  if (!accountSid || !authToken || !from) return { ok: false, error: 'SMS not configured' };
  const res = await fetch(`https://api.twilio.com/2010-04-01/Accounts/${accountSid}/Messages.json`, {
    method: 'POST',
    headers: {
      Authorization: `Basic ${Buffer.from(`${accountSid}:${authToken}`).toString('base64')}`,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({ To: to, From: from, Body: body }),
  });
  const json = await res.json().catch(() => ({}));
  return res.ok ? { ok: true, id: json.sid } : { ok: false, error: json.message || `HTTP ${res.status}` };
}

// --- Delivery with retry and an AlertLog row per attempt (REL-3) ---

async function deliver(log, sendFn) {
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    log.attempts = attempt;
    try {
      const r = await sendFn();
      if (r.ok) {
        Object.assign(log, { deliveryStatus: 'sent', sentAt: new Date(), providerMessageId: r.id, error: undefined });
        break;
      }
      Object.assign(log, { deliveryStatus: 'failed', error: r.error });
      if (/not configured|no registered device/i.test(r.error)) break; // retrying won't help
    } catch (e) {
      Object.assign(log, { deliveryStatus: 'failed', error: e.message });
    }
    if (attempt === 1) await new Promise((r) => setTimeout(r, 2000));
  }
  await log.save();
  return log;
}

const LABELS = {
  drowsiness: 'Drowsiness detected',
  inattention: 'Driver not watching the road',
  emotional_distress: 'Driver appears distressed',
  unverified_driver: 'Unrecognized driver',
  unauthorized_occupant: 'Unknown person in vehicle',
  key_left_inside: 'Key left inside vehicle',
};

const mapsLink = (event) => {
  const c = event.location?.coordinates;
  return c ? `https://maps.google.com/?q=${c[1]},${c[0]}` : null;
};

// Owner + family members get every alert on their phones (FR6.1).
async function notifyOwnerAlert(event) {
  const cfg = await SystemConfig.findOne({ owner: event.owner });
  if (cfg && !cfg.notifications.push) return [];
  const users = await User.find({
    $or: [{ _id: event.owner }, { owner: event.owner, role: 'family' }],
    isActive: true,
  }).select('+fcmTokens');

  return Promise.all(users.map((u) => deliver(
    new AlertLog({ event: event._id, owner: event.owner, alertType: 'alert', channel: 'push', recipientUser: u._id }),
    () => sendPush(u.fcmTokens, {
      title: `${event.severity === 'critical' ? 'CRITICAL' : 'Warning'}: ${LABELS[event.eventType]}`,
      body: 'Tap to acknowledge.',
      data: { kind: 'alert', eventId: event.id, severity: event.severity },
    })
  )));
}

// FR6.3 – every emergency contact gets the live location, by push if they use
// the app, otherwise by SMS when the owner has SMS fallback switched on.
async function notifyEscalation(event, ownerName) {
  const [contacts, cfg] = await Promise.all([
    EmergencyContact.find({ owner: event.owner }).sort({ priority: 1 }).populate({ path: 'linkedUser', select: '+fcmTokens' }),
    SystemConfig.findOne({ owner: event.owner }),
  ]);
  const link = mapsLink(event);
  const text = `EMERGENCY: ${ownerName} is not responding to a ${LABELS[event.eventType].toLowerCase()} alert.`
    + (link ? ` Location: ${link}` : ' Location unavailable.');

  const jobs = contacts.map((c) => {
    const base = { event: event._id, owner: event.owner, alertType: 'escalation', recipientContact: c._id };
    if (c.linkedUser?.fcmTokens?.length) {
      return deliver(new AlertLog({ ...base, channel: 'push', recipientUser: c.linkedUser._id }), () => sendPush(c.linkedUser.fcmTokens, {
        title: 'Emergency alert',
        body: text,
        data: { kind: 'escalation', eventId: event.id, mapsUrl: link || '' },
      }));
    }
    if (c.notifyBySms && cfg?.notifications.smsFallback) {
      return deliver(new AlertLog({ ...base, channel: 'sms' }), () => sendSms(c.phone, text));
    }
    return deliver(new AlertLog({ ...base, channel: 'sms' }), async () => ({
      ok: false,
      error: 'Contact has no app and SMS fallback is off',
    }));
  });

  // The owner's own phones also show the escalation.
  const owner = await User.findById(event.owner).select('+fcmTokens');
  if (owner) {
    jobs.push(deliver(
      new AlertLog({ event: event._id, owner: event.owner, alertType: 'escalation', channel: 'push', recipientUser: owner._id }),
      () => sendPush(owner.fcmTokens, { title: 'Emergency contacts notified', body: text, data: { kind: 'escalation', eventId: event.id } })
    ));
  }
  return Promise.all(jobs);
}

module.exports = { notifyOwnerAlert, notifyEscalation, sendPush, sendSms };
