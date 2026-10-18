const fs = require('fs');
const config = require('../config');
const { User, EmergencyContact, AlertLog, SystemConfig } = require('../models');
const whatsapp = require('./whatsappService');

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

let mailer = null;
function mail() {
  if (mailer !== null) return mailer;
  const { user, pass, host, port } = config.email;
  mailer = user && pass
    ? require('nodemailer').createTransport({ host, port, secure: port === 465, auth: { user, pass } })
    : false;
  return mailer;
}

// Tests swap in nodemailer's jsonTransport so nothing leaves the machine.
function setMailTransport(transport) { mailer = transport; }

const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (ch) => `&#${ch.charCodeAt(0)};`);

async function sendEmail(to, { subject, text, html }) {
  const m = mail();
  if (!m) return { ok: false, error: 'Email not configured' };
  const info = await m.sendMail({ from: `"Driver Monitor" <${config.email.user}>`, to, subject, text, html });
  return { ok: true, id: info.messageId };
}

function escalationEmail(event, ownerName) {
  const label = LABELS[event.eventType];
  const time = (event.escalatedAt || event.detectedAt || new Date()).toLocaleString('en-PK', { timeZone: 'Asia/Karachi' });
  const rows = [
    ['Driver', ownerName],
    ['Alert', `${event.severity.toUpperCase()}: ${label}`],
    ['Time', time],
  ].map(([k, v], i) => `<tr${i % 2 ? '' : ' style="background:#f6f6f6"'}><td style="padding:10px;border:1px solid #ddd;font-weight:bold">${k}</td>`
    + `<td style="padding:10px;border:1px solid #ddd">${escapeHtml(v)}</td></tr>`).join('');
  return {
    subject: `EMERGENCY: ${ownerName} is not responding`,
    html: `<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
  <div style="background:#c00;color:#fff;padding:20px;text-align:center;border-radius:8px 8px 0 0"><h1 style="margin:0">Emergency alert</h1></div>
  <div style="padding:24px;border:1px solid #ddd;border-radius:0 0 8px 8px">
    <p>The Driver Monitoring System raised an alert and the driver did not acknowledge it. Please check on them now.</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0">${rows}</table>
    <p style="color:#888;font-size:12px">Sent automatically by the Driver Monitoring System. Do not reply.</p>
  </div>
</div>`,
  };
}

function escalationWhatsApp(event, ownerName) {
  const time = (event.escalatedAt || event.detectedAt || new Date())
    .toLocaleTimeString('en-PK', { timeZone: 'Asia/Karachi', hour: '2-digit', minute: '2-digit' });
  return [
    `🚨 *EMERGENCY ALERT*`,
    `${ownerName} is not responding to a ${LABELS[event.eventType].toLowerCase()} alert (${event.severity}) at ${time}.`,
    'Please check on them now. (Driver Monitoring System)',
  ].join('\n');
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
  yawning: 'Driver is yawning',
  fatigue: 'Driver showing signs of fatigue',
  inattention: 'Driver not watching the road',
  looking_down: 'Driver looking down (phone?)',
  emotional_distress: 'Driver appears distressed',
  unverified_driver: 'Unrecognized driver',
  unauthorized_occupant: 'Unknown person in vehicle',
  key_left_inside: 'Key left inside vehicle',
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
// the app, otherwise by SMS when the owner has SMS fallback switched on, and
// by email whenever the contact has an address.
async function notifyEscalation(event, ownerName) {
  const [contacts, cfg] = await Promise.all([
    EmergencyContact.find({ owner: event.owner }).sort({ priority: 1 }).populate({ path: 'linkedUser', select: '+fcmTokens' }),
    SystemConfig.findOne({ owner: event.owner }),
  ]);
  const text = `EMERGENCY: ${ownerName} is not responding to a ${LABELS[event.eventType].toLowerCase()} alert.`
    + ' Please check on them now.';

  const email = escalationEmail(event, ownerName);
  const whatsappOn = cfg?.notifications?.whatsapp !== false;
  const waText = escalationWhatsApp(event, ownerName);

  const pushOrSms = (c, base) => {
    if (c.linkedUser?.fcmTokens?.length) {
      return deliver(new AlertLog({ ...base, channel: 'push', recipientUser: c.linkedUser._id }), () => sendPush(c.linkedUser.fcmTokens, {
        title: 'Emergency alert',
        body: text,
        data: { kind: 'escalation', eventId: event.id },
      }));
    }
    if (c.notifyBySms && cfg?.notifications.smsFallback) {
      return deliver(new AlertLog({ ...base, channel: 'sms' }), () => sendSms(c.phone, text));
    }
    if (c.email || whatsappOn) return null; // email / WhatsApp reach this contact instead
    return deliver(new AlertLog({ ...base, channel: 'sms' }), async () => ({
      ok: false,
      error: 'Contact has no app, no email and SMS fallback is off',
    }));
  };

  const jobs = contacts.flatMap((c) => {
    const base = { event: event._id, owner: event.owner, alertType: 'escalation', recipientContact: c._id };
    // Email and WhatsApp go out alongside push/SMS: they need no app or SMS credit on the contact's side.
    const byEmail = c.email
      ? deliver(new AlertLog({ ...base, channel: 'email' }), () => sendEmail(c.email, { ...email, text }))
      : null;
    const byWhatsApp = whatsappOn
      ? deliver(new AlertLog({ ...base, channel: 'whatsapp' }), () => whatsapp.sendText(c.phone, waText))
      : null;
    return [byEmail, byWhatsApp, pushOrSms(c, base)].filter(Boolean);
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

module.exports = { notifyOwnerAlert, notifyEscalation, sendPush, sendSms, sendEmail, setMailTransport };
