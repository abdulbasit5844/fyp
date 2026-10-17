const { Device } = require('../models');
const ApiError = require('../utils/ApiError');
const pick = require('../utils/pick');
const bridge = require('../realtime/mqttBridge');
const ws = require('../realtime/wsHub');

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

module.exports = { list, discover, pair, get, update, unpair, setDetection };
