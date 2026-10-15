// Validates sample documents against every schema without a database.
// Run: npm run check:schemas
const mongoose = require('mongoose');
const m = require('../src/models');

const id = () => new mongoose.Types.ObjectId();
const owner = id();
const device = id();
const event = id();

const cases = [
  ['User ok', m.User, { name: 'Muneeb', email: 'Muneeb@Example.com', passwordHash: 'x' }, true],
  ['User bad email', m.User, { name: 'A', email: 'nope', passwordHash: 'x' }, false],
  ['User bad role', m.User, { name: 'A', email: 'a@b.co', passwordHash: 'x', role: 'root' }, false],
  ['Device ok', m.Device, { deviceId: 'pi-vision-01', owner }, true],
  ['Driver ok', m.DriverProfile, { owner, displayName: 'Basit', faceEmbeddings: [{ vector: Array(128).fill(0.1), model: 'mobilefacenet-128' }] }, true],
  ['Driver short embedding', m.DriverProfile, { owner, displayName: 'B', faceEmbeddings: [{ vector: [1, 2], model: 'x' }] }, false],
  ['Contact ok', m.EmergencyContact, { owner, name: 'Dad', phone: '+923001234567' }, true],
  ['Contact bad phone', m.EmergencyContact, { owner, name: 'Dad', phone: '03001234567' }, false],
  ['Event ok', m.SafetyEvent, {
    edgeEventId: 'evt-1', owner, device, eventType: 'drowsiness', severity: 'critical',
    detectedAt: new Date(), signals: { ear: 0.18, sustainedMs: 2300 },
    location: { coordinates: [73.0479, 33.6844] },
  }, true],
  ['Event bad type', m.SafetyEvent, { edgeEventId: 'e', owner, device, eventType: 'sneeze', severity: 'warning', detectedAt: new Date() }, false],
  ['Clip ok', m.VideoClip, { event, owner, device, filePath: '/var/dms/clips/evt-1.mp4', startedAt: new Date() }, true],
  ['Config defaults', m.SystemConfig, { owner }, true],
  ['Config EAR too high', m.SystemConfig, { owner, earThreshold: 0.35 }, false],
  ['Config ack too short', m.SystemConfig, { owner, ackWindowSec: 2 }, false],
  ['AlertLog ok', m.AlertLog, { event, owner, alertType: 'escalation', channel: 'push' }, true],
];

(async () => {
  let failed = 0;
  for (const [name, Model, data, shouldPass] of cases) {
    const doc = new Model(data);
    // The contact-limit hook queries the DB; stub it for the offline check.
    if (Model === m.EmergencyContact) Model.countDocuments = async () => 0;
    let err = null;
    try { await doc.validate(); } catch (e) { err = e; }
    const ok = shouldPass ? !err : Boolean(err);
    if (!ok) failed += 1;
    console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${err && !shouldPass ? `  (${Object.keys(err.errors || {}).join(', ')})` : ''}${err && shouldPass ? `  ${err.message}` : ''}`);
  }

  const cfg = new m.SystemConfig({ owner }).toJSON();
  console.log('\nSystemConfig defaults:', JSON.stringify(cfg, null, 2));
  const u = new m.User({ name: 'A', email: 'a@b.co', passwordHash: 'secret' }).toJSON();
  console.log('User JSON hides passwordHash:', !('passwordHash' in u));

  // Contact limit with a stubbed count of 5.
  m.EmergencyContact.countDocuments = async () => 5;
  try {
    await new m.EmergencyContact({ owner, name: 'Sixth', phone: '+923001111111' }).validate();
    console.log('FAIL  6th contact accepted'); failed += 1;
  } catch { console.log('PASS  6th contact rejected'); }

  console.log(failed ? `\n${failed} check(s) failed` : '\nAll schema checks passed');
  process.exit(failed ? 1 : 0);
})();
