const mqtt = require('mqtt');
const config = require('../config');
const { Device, SystemConfig, DriverProfile } = require('../models');

// Topic layout is documented in docs/mqtt-contract.md.
let client = null;
const unpaired = new Map(); // deviceId -> last seen, for the pairing screen

function publish(topic, payload, opts = {}) {
  if (!client) return;
  client.publish(topic, JSON.stringify(payload), { qos: 1, ...opts });
}

const CONFIG_FIELDS = [
  'earThreshold', 'earSustainSec', 'headPoseThresholdDeg', 'headPoseSustainSec', 'emotionSustainSec',
  'ackWindowSec', 'alertSensitivity', 'videoRecordingEnabled', 'notifications', 'revision',
];

async function publishConfig(device) {
  const cfg = (await SystemConfig.findOne({ owner: device.owner })) || (await SystemConfig.create({ owner: device.owner }));
  const json = cfg.toJSON();
  publish(`dms/${device.deviceId}/config`, Object.fromEntries(CONFIG_FIELDS.map((k) => [k, json[k]])), { retain: true });
}

async function publishDrivers(device) {
  const drivers = await DriverProfile.find({ owner: device.owner }).select('+faceEmbeddings');
  publish(`dms/${device.deviceId}/drivers`, drivers.map((d) => ({
    id: d.id,
    displayName: d.displayName,
    isAuthorized: d.isAuthorized,
    embeddings: d.faceEmbeddings.map((e) => ({ vector: e.vector, model: e.model })),
  })), { retain: true });
}

// Retained, so the unit picks up Start/Stop again after a reboot.
function publishDetection(device) {
  publish(`dms/${device.deviceId}/cmd/detection`, { enabled: Boolean(device.detectionEnabled) }, { retain: true });
}

async function forOwner(ownerId, fn) {
  const devices = await Device.find({ owner: ownerId });
  await Promise.all(devices.map(fn));
}

const publishConfigForOwner = (ownerId) => forOwner(ownerId, publishConfig);
const publishDriversForOwner = (ownerId) => forOwner(ownerId, publishDrivers);

function sendAck(device, edgeEventId) {
  publish(`dms/${device.deviceId}/cmd/ack`, { eventId: edgeEventId });
}

// action: 'preview' (stream the camera view), 'capture' (take photo + samples) or 'cancel'.
function requestEnrollment(device, driver, action = 'preview') {
  publish(`dms/${device.deviceId}/cmd/enroll`, { driverId: driver.id, action });
}

const listUnpaired = () => [...unpaired].map(([deviceId, lastSeenAt]) => ({ deviceId, lastSeenAt }));

// Routes an incoming message to the event service. Exported for tests.
async function handleMessage(topic, buf) {
  const events = require('../services/eventService');
  const [, deviceId, ...rest] = topic.split('/');
  const kind = rest.join('/');
  let payload;
  try {
    payload = buf.length ? JSON.parse(buf.toString()) : {};
  } catch {
    console.warn(`[mqtt] bad JSON on ${topic}`);
    return;
  }

  const device = await Device.findOne({ deviceId });
  if (!device) {
    if (kind === 'status' && payload.online !== false) unpaired.set(deviceId, new Date());
    return;
  }
  unpaired.delete(deviceId);

  switch (kind) {
    case 'status': return events.updateDeviceStatus(device, payload);
    case 'event': return events.ingestEvent(device, payload);
    case 'event/ack': return events.edgeAck(device, payload);
    case 'event/escalate': return events.escalate(device, payload);
    case 'event/resolve': return events.resolve(device, payload);
    case 'clip': return events.recordClip(device, payload);
    case 'enrollment': return events.saveEnrollment(device, payload);
    default: return undefined; // our own outbound topics (config, drivers, cmd/*)
  }
}

function connect() {
  if (config.mqttUrl === 'disabled') return null;
  client = mqtt.connect(config.mqttUrl, { clientId: `dms-backend-${process.pid}`, reconnectPeriod: 2000 });

  client.on('connect', async () => {
    console.log(`[mqtt] connected to ${config.mqttUrl}`);
    client.subscribe(['dms/+/status', 'dms/+/event', 'dms/+/event/+', 'dms/+/clip', 'dms/+/enrollment'], { qos: 1 });
    // Make sure every paired device has its current settings and drivers.
    for (const d of await Device.find()) {
      await publishConfig(d);
      await publishDrivers(d);
      publishDetection(d);
    }
  });
  client.on('message', (topic, buf) => {
    handleMessage(topic, buf).catch((e) => console.error(`[mqtt] ${topic}:`, e.message));
  });
  client.on('error', (e) => console.error('[mqtt] error:', e.message));
  return client;
}

async function close() {
  if (client) await client.endAsync();
  client = null;
}

module.exports = {
  connect, close, handleMessage, publishConfig, publishDrivers, publishConfigForOwner,
  publishDriversForOwner, publishDetection, sendAck, requestEnrollment, listUnpaired,
};
