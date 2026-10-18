// End-to-end API tests against an in-memory MongoDB. MQTT traffic from the
// edge is simulated by calling the bridge's message handler directly.
process.env.MQTT_URL = 'disabled';
process.env.NODE_ENV = 'test';

const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { MongoMemoryServer } = require('mongodb-memory-server');
const mongoose = require('mongoose');

const clipsDir = fs.mkdtempSync(path.join(os.tmpdir(), 'dms-clips-'));
process.env.CLIPS_DIR = clipsDir;

const createApp = require('../src/app');
const bridge = require('../src/realtime/mqttBridge');
const { User } = require('../src/models');
const notify = require('../src/services/notificationService');
const ws = require('../src/realtime/wsHub');
const whatsapp = require('../src/services/whatsappService');

let mongo; let server; let base;

const api = async (method, url, { token, body, headers } = {}) => {
  const res = await fetch(base + url, {
    method,
    headers: {
      ...(body && { 'Content-Type': 'application/json' }),
      ...(token && { Authorization: `Bearer ${token}` }),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let json; try { json = JSON.parse(text); } catch { json = text; }
  return { status: res.status, body: json, headers: res.headers };
};

const edge = (deviceId, kind, payload) =>
  bridge.handleMessage(`dms/${deviceId}/${kind}`, Buffer.from(JSON.stringify(payload)));

before(async () => {
  mongo = await MongoMemoryServer.create();
  await mongoose.connect(mongo.getUri());
  await mongoose.syncIndexes();
  server = createApp().listen(0);
  base = `http://127.0.0.1:${server.address().port}`;
});

after(async () => {
  server.close();
  await mongoose.disconnect();
  await mongo.stop();
  fs.rmSync(clipsDir, { recursive: true, force: true });
});

const state = {};

test('registration validates input and rejects duplicates', async () => {
  let r = await api('POST', '/api/auth/register', { body: { name: 'A', email: 'bad', password: 'password123' } });
  assert.equal(r.status, 400);
  r = await api('POST', '/api/auth/register', { body: { name: 'A', email: 'a@x.com', password: 'short' } });
  assert.equal(r.status, 400);

  r = await api('POST', '/api/auth/register', { body: { name: 'Muneeb', email: 'Owner@X.com', password: 'password123' } });
  assert.equal(r.status, 201);
  assert.ok(r.body.accessToken && r.body.refreshToken);
  assert.equal(r.body.user.email, 'owner@x.com');
  assert.equal(r.body.user.passwordHash, undefined);
  Object.assign(state, { token: r.body.accessToken, refresh: r.body.refreshToken });

  r = await api('POST', '/api/auth/register', { body: { name: 'B', email: 'owner@x.com', password: 'password123' } });
  assert.equal(r.status, 409);
});

test('login, refresh rotation and lockout', async () => {
  let r = await api('POST', '/api/auth/login', { body: { email: 'owner@x.com', password: 'password123' } });
  assert.equal(r.status, 200);

  r = await api('POST', '/api/auth/refresh', { body: { refreshToken: state.refresh } });
  assert.equal(r.status, 200);
  const reused = await api('POST', '/api/auth/refresh', { body: { refreshToken: state.refresh } });
  assert.equal(reused.status, 401, 'old refresh token must be revoked');
  state.token = r.body.accessToken;

  await api('POST', '/api/auth/register', { body: { name: 'L', email: 'lock@x.com', password: 'password123' } });
  for (let i = 0; i < 4; i += 1) {
    r = await api('POST', '/api/auth/login', { body: { email: 'lock@x.com', password: 'wrong-pass' } });
    assert.equal(r.status, 401);
  }
  r = await api('POST', '/api/auth/login', { body: { email: 'lock@x.com', password: 'wrong-pass' } });
  assert.equal(r.status, 423);
  r = await api('POST', '/api/auth/login', { body: { email: 'lock@x.com', password: 'password123' } });
  assert.equal(r.status, 423, 'correct password still blocked while locked');
});

test('protected routes need a valid token', async () => {
  assert.equal((await api('GET', '/api/contacts')).status, 401);
  assert.equal((await api('GET', '/api/contacts', { token: 'garbage' })).status, 401);
});

test('emergency contacts: CRUD, max 5, min 1', async () => {
  const { token } = state;
  const ids = [];
  for (let i = 1; i <= 5; i += 1) {
    const r = await api('POST', '/api/contacts', { token, body: { name: `C${i}`, phone: `+92300000000${i}`, priority: i, owner: 'hacker' } });
    assert.equal(r.status, 201, JSON.stringify(r.body));
    ids.push(r.body.id);
  }
  let r = await api('POST', '/api/contacts', { token, body: { name: 'C6', phone: '+923000000006' } });
  assert.equal(r.status, 400);

  r = await api('POST', '/api/contacts', { token, body: { name: 'Bad', phone: '0300' } });
  assert.equal(r.status, 400);

  r = await api('PATCH', `/api/contacts/${ids[0]}`, { token, body: { name: 'Dad' } });
  assert.equal(r.body.name, 'Dad');

  for (const id of ids.slice(1)) assert.equal((await api('DELETE', `/api/contacts/${id}`, { token })).status, 204);
  r = await api('DELETE', `/api/contacts/${ids[0]}`, { token });
  assert.equal(r.status, 409, 'last contact cannot be removed');
});

test('system config: defaults, bounds, revision', async () => {
  const { token } = state;
  let r = await api('GET', '/api/config', { token });
  assert.equal(r.body.earThreshold, 0.25);
  assert.equal(r.body.headPitchThresholdDeg, 20);
  assert.equal(r.body.revision, 1);

  r = await api('PATCH', '/api/config', { token, body: { earThreshold: 0.5 } });
  assert.equal(r.status, 400);
  r = await api('PATCH', '/api/config', { token, body: { headPoseThresholdDeg: 15 } });
  assert.equal(r.status, 400, 'head turn limit starts at 20° (FR5.4)');

  r = await api('PATCH', '/api/config', { token, body: { earThreshold: 0.22, ackWindowSec: 10, notifications: { smsFallback: true } } });
  assert.equal(r.status, 200);
  assert.equal(r.body.earThreshold, 0.22);
  assert.equal(r.body.notifications.push, true, 'partial update keeps other flags');
  assert.equal(r.body.notifications.smsFallback, true);
  assert.equal(r.body.revision, 2);
});

test('edge flow: pair, status, event, ack, escalation, clip', async () => {
  const { token } = state;
  await edge('pi-test', 'status', { online: true, state: 'safe' });
  let r = await api('GET', '/api/devices/discover', { token });
  assert.deepEqual(r.body.map((d) => d.deviceId), ['pi-test']);

  r = await api('POST', '/api/devices', { token, body: { deviceId: 'pi-test', name: 'Corolla' } });
  assert.equal(r.status, 201);

  await edge('pi-test', 'status', { online: true, state: 'warning', monitoring: true, location: { lat: 33.68, lng: 73.04 } });
  r = await api('GET', '/api/devices', { token });
  assert.equal(r.body[0].currentState, 'warning');
  assert.equal(r.body[0].online, true);

  // Start / Stop detecting from the app.
  const devId = r.body[0].id;
  assert.equal(r.body[0].detectionEnabled, false, 'stopped until the user presses Start');
  r = await api('POST', `/api/devices/${devId}/detection`, { token, body: { enabled: 'yes' } });
  assert.equal(r.status, 400);
  r = await api('POST', `/api/devices/${devId}/detection`, { token, body: { enabled: true } });
  assert.equal(r.body.detectionEnabled, true);
  r = await api('POST', `/api/devices/${devId}/detection`, { token, body: { enabled: false } });
  assert.equal(r.body.detectionEnabled, false);
  assert.equal(r.body.currentState, 'safe');

  // Live view: the app gets the RTSP URL; MediaMTX asks us who may watch.
  r = await api('POST', `/api/devices/${devId}/live`, { token, body: { enabled: true } });
  assert.equal(r.status, 200);
  const m = /^rtsp:\/\/live:([\w-]+)@127\.0\.0\.1:8554\/pi-test$/.exec(r.body.url);
  assert.ok(m, r.body.url);
  const ticket = m[1];
  assert.ok(`live:${ticket}`.length < 128, 'fits FFmpeg\'s RTSP credential limit');
  assert.equal(r.body.fps, 60);
  assert.deepEqual(r.body.qualities.map((q) => `${q.name}@${q.fps}`), ['480p@60', '720p@46', '1080p@30']);
  r = await api('POST', `/api/devices/${devId}/live`, { token, body: { enabled: true, quality: '720p' } });
  assert.equal(r.body.resolution, '1280x720');
  assert.equal(r.body.fps, 46);
  assert.equal((await api('POST', `/api/devices/${devId}/live`, { token, body: { enabled: true, quality: '4k' } })).status, 400);
  r = await api('POST', `/api/devices/${devId}/live`, { token, body: { enabled: true } }); // keep-alive
  assert.ok(r.body.url.includes(ticket), 'keep-alive keeps the same URL');
  const streamAuth = (body) => api('POST', '/api/stream/auth', { body });
  assert.equal((await streamAuth({ action: 'read', path: 'pi-test', password: ticket })).status, 200);
  assert.equal((await streamAuth({ action: 'read', path: 'pi-test', password: token })).status, 401);
  assert.equal((await streamAuth({ action: 'read', path: 'someone-elses-car', password: ticket })).status, 401);
  await api('POST', `/api/devices/${devId}/live`, { token, body: { enabled: false } });
  assert.equal((await streamAuth({ action: 'read', path: 'pi-test', password: ticket })).status, 401, 'closed: ticket revoked');
  assert.equal((await streamAuth({ action: 'publish', path: 'pi-test', ip: '127.0.0.1' })).status, 200);
  assert.equal((await streamAuth({ action: 'publish', path: 'pi-test', ip: '10.0.0.9' })).status, 401);

  // Event 1: acknowledged from the app.
  const detectedAt = new Date().toISOString();
  await edge('pi-test', 'event', { eventId: 'e1', type: 'drowsiness', severity: 'critical', detectedAt, signals: { ear: 0.18, sustainedMs: 2400 } });
  await edge('pi-test', 'event', { eventId: 'e1', type: 'drowsiness', severity: 'critical', detectedAt }); // duplicate
  r = await api('GET', '/api/events/active', { token });
  assert.equal(r.body.length, 1);
  const e1 = r.body[0].id;

  r = await api('POST', `/api/events/${e1}/acknowledge`, { token });
  assert.equal(r.body.status, 'acknowledged');
  assert.equal(r.body.acknowledgedVia, 'mobile_app');

  // A late escalation for an acknowledged event is ignored.
  await edge('pi-test', 'event/escalate', { eventId: 'e1', location: { lat: 1, lng: 2 } });
  r = await api('GET', `/api/events/${e1}`, { token });
  assert.equal(r.body.status, 'acknowledged');

  // Event 2: escalated with GPS, contacts notified (push/SMS fail: not configured; email is captured).
  const sent = [];
  notify.setMailTransport({ sendMail: async (m) => { sent.push(m); return { messageId: 'mail-1' }; } });
  const waSent = [];
  whatsapp.setTestSender(async (phone, text) => { waSent.push({ phone, text }); return { ok: true, id: 'wa-1' }; });
  const [dad] = (await api('GET', '/api/contacts', { token })).body;
  await api('PATCH', `/api/contacts/${dad.id}`, { token, body: { email: 'dad@example.com' } });
  await edge('pi-test', 'event', { eventId: 'e2', type: 'inattention', severity: 'critical', detectedAt: new Date().toISOString() });
  await edge('pi-test', 'event/escalate', { eventId: 'e2', location: { lat: 33.6844, lng: 73.0479, accuracyM: 5 } });
  await new Promise((res) => setTimeout(res, 300)); // let notification logging finish
  r = await api('GET', '/api/events?limit=10', { token });
  assert.equal(r.body.total, 2);
  const e2 = r.body.items.find((e) => e.status === 'escalated');
  assert.ok(e2);
  assert.deepEqual(e2.location.coordinates, [73.0479, 33.6844]);
  assert.equal(e2.actionTaken, 'Emergency contacts notified');
  r = await api('GET', `/api/events/${e2.id}`, { token });
  assert.ok(r.body.notifications.some((n) => n.alertType === 'escalation' && n.recipientContact?.name === 'Dad'));
  const mailed = r.body.notifications.find((n) => n.channel === 'email');
  assert.equal(mailed.deliveryStatus, 'sent');
  assert.equal(sent.length, 1);
  assert.equal(sent[0].to, 'dad@example.com');
  assert.doesNotMatch(sent[0].html, /maps\.google|Location/, 'no location in the email');
  notify.setMailTransport(null);
  // WhatsApp: one message per contact, to their phone number.
  assert.equal(r.body.notifications.find((n) => n.channel === 'whatsapp').deliveryStatus, 'sent');
  assert.deepEqual(waSent.map((m) => m.phone), [dad.phone]);
  assert.match(waSent[0].text, /EMERGENCY ALERT/);
  assert.doesNotMatch(waSent[0].text, /maps\.google|Location/, 'no location in the WhatsApp message');
  whatsapp.setTestSender(null);

  // The driver recovers: an open critical alert clears to resolved, but a
  // later "resolve" never overwrites an acknowledged alert.
  await edge('pi-test', 'event', { eventId: 'r1', type: 'drowsiness', severity: 'critical', detectedAt: new Date().toISOString() });
  await edge('pi-test', 'event/resolve', { eventId: 'r1' });
  r = await api('GET', '/api/events?type=drowsiness&severity=critical&limit=1', { token });
  assert.equal(r.body.items[0].status, 'resolved');
  await edge('pi-test', 'event/resolve', { eventId: 'e1' });
  r = await api('GET', `/api/events/${e1}`, { token });
  assert.equal(r.body.status, 'acknowledged');

  // Physical button ack on event 3.
  await edge('pi-test', 'event', { eventId: 'e3', type: 'emotional_distress', severity: 'warning', detectedAt: new Date().toISOString() });
  await edge('pi-test', 'event/ack', { eventId: 'e3' });
  r = await api('GET', '/api/events?type=emotional_distress', { token });
  assert.equal(r.body.items[0].acknowledgedVia, 'edge_button');

  // Clip for event 2, then range request.
  const file = path.join(clipsDir, 'e2.mp4');
  fs.writeFileSync(file, Buffer.alloc(1000, 7));
  await edge('pi-test', 'clip', { eventId: 'e2', filePath: file, sizeBytes: 1000, status: 'available' });
  r = await api('GET', `/api/events/${e2.id}`, { token });
  const clipId = r.body.videoClip.id;
  assert.equal(r.body.videoClip.filePath, undefined, 'file path is not exposed');

  r = await api('GET', `/api/clips/${clipId}/stream`, { token, headers: { Range: 'bytes=100-199' } });
  assert.equal(r.status, 206);
  assert.equal(r.headers.get('content-range'), 'bytes 100-199/1000');

  // A clip path outside CLIPS_DIR is refused.
  await edge('pi-test', 'event', { eventId: 'e4', type: 'drowsiness', severity: 'warning', detectedAt: new Date().toISOString() });
  await edge('pi-test', 'clip', { eventId: 'e4', filePath: '/etc/passwd', status: 'available' });
  r = await api('GET', '/api/events?limit=1', { token });
  r = await api('GET', `/api/clips/${r.body.items[0].videoClip.id}/stream`, { token });
  assert.equal(r.status, 403);
});

test('unknown driver: photo to the app, then WhatsApp with the photo to the owner only', async () => {
  const { token } = state;
  const waSent = [];
  whatsapp.setTestSender(async (phone, text, image) => { waSent.push({ phone, text, image }); return { ok: true, id: 'wa-2' }; });
  let r = await api('PATCH', '/api/config', { token, body: { ownerWhatsApp: '12345' } });
  assert.equal(r.status, 400);
  r = await api('PATCH', '/api/config', { token, body: { ownerWhatsApp: '+923001112233' } });
  assert.equal(r.body.ownerWhatsApp, '+923001112233');

  await edge('pi-test', 'status', { online: true, state: 'safe', monitoring: false, identity: 'unknown' });
  r = await api('GET', '/api/devices', { token });
  assert.equal(r.body[0].identity, 'unknown');
  assert.equal(r.body[0].monitoring, false);

  const photo = Buffer.from('fake-jpeg').toString('base64');
  await edge('pi-test', 'event', {
    eventId: 'u1', type: 'unverified_driver', severity: 'critical', detectedAt: new Date().toISOString(),
    description: "Unknown person in the driver's seat (best match 0.05)", photo,
  });
  await new Promise((res) => setTimeout(res, 300)); // let the WhatsApp delivery finish
  r = await api('GET', '/api/events?type=unverified_driver', { token });
  const u1 = r.body.items[0];
  assert.equal(u1.status, 'escalated', 'no acknowledgment window for an unknown driver');
  assert.equal(u1.actionTaken, 'Owner alerted on WhatsApp');
  assert.equal(u1.photo, undefined, 'photos stay out of the event list');
  r = await api('GET', `/api/events/${u1.id}`, { token });
  assert.equal(r.body.photo, photo);
  assert.deepEqual(waSent.map((m) => m.phone), ['+923001112233'], 'the owner only, not the emergency contacts');
  assert.equal(waSent[0].image.toString(), 'fake-jpeg');
  assert.match(waSent[0].text, /UNKNOWN DRIVER/);
  assert.equal(r.body.notifications.find((n) => n.channel === 'whatsapp').deliveryStatus, 'sent');
  whatsapp.setTestSender(null);
});

test('face enrollment: request, live progress, result', async () => {
  const { token } = state;
  const sent = [];
  const realBroadcast = ws.broadcast;
  ws.broadcast = (owner, type, data) => sent.push({ type, data });
  try {
    let r = await api('POST', '/api/drivers', { token, body: { displayName: 'Ali' } });
    const driverId = r.body.id;
    for (const action of ['preview', 'capture', 'cancel']) {
      r = await api('POST', `/api/drivers/${driverId}/enroll`, { token, body: { action } });
      assert.equal(r.status, 202, action);
    }
    r = await api('POST', `/api/drivers/${driverId}/enroll`, { token, body: { action: 'explode' } });
    assert.equal(r.status, 400);

    // The live view is relayed to the app (with the preview) and nothing is stored yet.
    const view = { mode: 'preview', samples: 0, needed: 5, faceVisible: false, secondsLeft: 100, preview: 'abc' };
    await edge('pi-test', 'enrollment', { driverId, status: 'progress', ...view });
    assert.deepEqual(sent.find((m) => m.type === 'enrollment_progress').data, { driverId, ...view });
    r = await api('GET', '/api/drivers', { token });
    assert.equal(r.body.find((d) => d.id === driverId).enrolled, false);

    // A failure is reported without storing anything.
    await edge('pi-test', 'enrollment', { driverId, status: 'failed', ok: false, error: 'No person detected in the camera' });
    assert.deepEqual(sent.at(-1), { type: 'enrollment', data: { driverId, ok: false, error: 'No person detected in the camera' } });

    // Success stores the embedding and the photo.
    await edge('pi-test', 'enrollment', { driverId, status: 'done', ok: true, model: 'sface', vector: Array(128).fill(0.1), photo: 'jpegdata' });
    assert.equal(sent.at(-1).data.ok, true);
    assert.equal(sent.at(-1).data.photo, 'jpegdata');
    r = await api('GET', '/api/drivers', { token });
    const ali = r.body.find((d) => d.id === driverId);
    assert.equal(ali.enrolled, true);
    assert.equal(ali.photo, 'jpegdata');
  } finally {
    ws.broadcast = realBroadcast;
  }
});

test('another owner cannot see or touch this data', async () => {
  const other = await api('POST', '/api/auth/register', { body: { name: 'Eve', email: 'eve@x.com', password: 'password123' } });
  const token = other.body.accessToken;
  const mine = await api('GET', '/api/events', { token: state.token });
  const id = mine.body.items[0].id;
  assert.equal((await api('GET', `/api/events/${id}`, { token })).status, 404);
  assert.equal((await api('GET', '/api/events', { token })).body.total, 0);
  assert.equal((await api('POST', '/api/devices', { token, body: { deviceId: 'pi-test' } })).status, 409);
});

test('family members see owner data but cannot change settings', async () => {
  let r = await api('POST', '/api/users/members', { token: state.token, body: { name: 'Sis', email: 'sis@x.com', password: 'password123' } });
  assert.equal(r.status, 201);
  r = await api('POST', '/api/auth/login', { body: { email: 'sis@x.com', password: 'password123' } });
  const token = r.body.accessToken;
  assert.equal((await api('GET', '/api/events', { token })).body.total, 6); // incl. the unknown-driver event
  assert.equal((await api('PATCH', '/api/config', { token, body: { earThreshold: 0.2 } })).status, 403);
});

test('deactivated users lose access immediately', async () => {
  const admin = new User({ name: 'Admin', email: 'admin@x.com', role: 'admin' });
  await admin.setPassword('password123');
  await admin.save();
  const adminToken = (await api('POST', '/api/auth/login', { body: { email: 'admin@x.com', password: 'password123' } })).body.accessToken;

  const eve = await User.findOne({ email: 'eve@x.com' });
  const eveToken = (await api('POST', '/api/auth/login', { body: { email: 'eve@x.com', password: 'password123' } })).body.accessToken;
  assert.equal((await api('PATCH', `/api/users/${eve.id}`, { token: eveToken, body: { isActive: false } })).status, 403);
  assert.equal((await api('PATCH', `/api/users/${eve.id}`, { token: adminToken, body: { isActive: false } })).status, 200);
  assert.equal((await api('GET', '/api/auth/me', { token: eveToken })).status, 401);
});
