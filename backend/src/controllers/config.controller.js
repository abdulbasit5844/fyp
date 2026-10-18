const { SystemConfig } = require('../models');
const pick = require('../utils/pick');
const bridge = require('../realtime/mqttBridge');
const ws = require('../realtime/wsHub');

const FIELDS = [
  'earThreshold',
  'earSustainSec',
  'headPoseThresholdDeg',
  'headPitchThresholdDeg',
  'headPoseSustainSec',
  'emotionSustainSec',
  'ackWindowSec',
  'alertSensitivity',
  'videoRecordingEnabled',
  'notifications',
];

async function getOrCreate(owner) {
  return (await SystemConfig.findOne({ owner })) || SystemConfig.create({ owner });
}

async function get(req, res) {
  res.json(await getOrCreate(req.ownerId));
}

// FR7.3 – saved settings are pushed to the owner's edge devices immediately.
async function update(req, res) {
  const cfg = await getOrCreate(req.ownerId);
  const updates = pick(req.body, FIELDS);
  if (updates.notifications) {
    updates.notifications = { ...cfg.notifications.toObject(), ...updates.notifications };
  }
  cfg.set(updates);
  await cfg.save();
  await bridge.publishConfigForOwner(req.ownerId);
  ws.broadcast(req.ownerId, 'config', cfg.toJSON());
  res.json(cfg);
}

module.exports = { get, update };
