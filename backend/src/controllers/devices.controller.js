const { Device } = require('../models');
const ApiError = require('../utils/ApiError');
const pick = require('../utils/pick');
const bridge = require('../realtime/mqttBridge');
const ws = require('../realtime/wsHub');
const config = require('../config');
const tickets = require('../services/streamTickets');

async function list(req, res) {
  const devices = await Device.find({ owner: req.ownerId })
    .populate({ path: 'activeDriver', select: 'displayName' })
    .sort({ createdAt: 1 });
  res.json(devices);
}

// Edge devices publishing on MQTT that nobody has paired yet.
function discover(req, res) {
  res.json(bridge.listUnpaired());
}

// Pair the Pi with this owner, using the device ID printed by the edge pipeline.
async function pair(req, res) {
  const { deviceId, name } = req.body || {};
  if (!deviceId) throw ApiError.badRequest('deviceId is required');

  const existing = await Device.findOne({ deviceId });
  if (existing && !existing.owner.equals(req.ownerId)) {
    throw ApiError.conflict('This device is already paired with another account');
  }
  const device = existing || new Device({ deviceId, owner: req.ownerId });
  if (name) device.name = name;
  await device.save();

  await bridge.publishConfig(device);
  await bridge.publishDrivers(device);
  bridge.publishDetection(device);
  res.status(existing ? 200 : 201).json(device);
}

// Start / Stop detecting the driver (from the app's home screen).
async function setDetection(req, res) {
  if (typeof req.body?.enabled !== 'boolean') throw ApiError.badRequest('enabled must be true or false');
  const device = await Device.findOne({ _id: req.params.id, owner: req.ownerId })
    .populate({ path: 'activeDriver', select: 'displayName' });
  if (!device) throw ApiError.notFound('Device not found');
  if (req.body.enabled && !device.online) throw ApiError.conflict('The vehicle unit is offline');
  device.detectionEnabled = req.body.enabled;
  if (!device.detectionEnabled) {
    device.monitoring = false;
    device.currentState = 'safe';
  }
  await device.save();
  bridge.publishDetection(device);
  ws.broadcast(req.ownerId, 'device', device.toJSON());
  res.json(device);
}

async function get(req, res) {
  const device = await Device.findOne({ _id: req.params.id, owner: req.ownerId })
    .populate({ path: 'activeDriver', select: 'displayName' });
  if (!device) throw ApiError.notFound('Device not found');
  res.json(device);
}

async function update(req, res) {
  const device = await Device.findOne({ _id: req.params.id, owner: req.ownerId });
  if (!device) throw ApiError.notFound('Device not found');
  device.set(pick(req.body, ['name']));
  await device.save();
  res.json(device);
}

async function unpair(req, res) {
  const device = await Device.findOneAndDelete({ _id: req.params.id, owner: req.ownerId });
  if (!device) throw ApiError.notFound('Device not found');
  res.status(204).end();
}

// What the OV5647 camera can do at each size (see edge/dms_edge/camera.py).
const LIVE_QUALITIES = {
  '480p': { resolution: '640x480', fps: 60 },
  '720p': { resolution: '1280x720', fps: 46 },
  '1080p': { resolution: '1920x1080', fps: 30 },
};

// Live view: asks the unit to stream (H.264 over RTSP through MediaMTX on the
// Pi) at the chosen quality. The returned URL carries a short-lived ticket as
// the RTSP password; MediaMTX checks it with /api/stream/auth. The app repeats
// this call as a keep-alive while watching.
async function setLive(req, res) {
  if (typeof req.body?.enabled !== 'boolean') throw ApiError.badRequest('enabled must be true or false');
  const quality = req.body.quality ?? '480p';
  if (!LIVE_QUALITIES[quality]) throw ApiError.badRequest(`quality must be one of ${Object.keys(LIVE_QUALITIES).join(', ')}`);
  const device = await Device.findOne({ _id: req.params.id, owner: req.ownerId });
  if (!device) throw ApiError.notFound('Device not found');
  if (req.body.enabled && !device.online) throw ApiError.conflict('The vehicle unit is offline');
  bridge.requestLive(device, req.body.enabled, quality);
  if (!req.body.enabled) {
    tickets.revoke(req.ownerId, device.deviceId);
    return res.json({ enabled: false });
  }
  const ticket = tickets.issue(req.ownerId, device.deviceId);
  res.json({
    enabled: true,
    url: `rtsp://live:${ticket}@${req.hostname}:${config.rtspPort}/${encodeURIComponent(device.deviceId)}`,
    quality,
    ...LIVE_QUALITIES[quality],
    qualities: Object.entries(LIVE_QUALITIES).map(([name, q]) => ({ name, ...q })),
  });
}

module.exports = { list, discover, pair, get, update, unpair, setDetection, setLive };
