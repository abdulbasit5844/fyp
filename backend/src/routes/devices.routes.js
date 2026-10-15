const express = require('express');
const { Device } = require('../models');
const ApiError = require('../utils/ApiError');
const pick = require('../utils/pick');
const { requireRole } = require('../middleware/auth');
const bridge = require('../realtime/mqttBridge');

const router = express.Router();

router.get('/', async (req, res) => {
  const devices = await Device.find({ owner: req.ownerId })
    .populate({ path: 'activeDriver', select: 'displayName' })
    .sort({ createdAt: 1 });
  res.json(devices);
});

// Edge devices publishing on MQTT that nobody has paired yet.
router.get('/discover', requireRole('owner'), (req, res) => {
  res.json(bridge.listUnpaired());
});

// Pair the Pi with this owner, using the device ID printed by the edge pipeline.
router.post('/', requireRole('owner'), async (req, res) => {
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
  res.status(existing ? 200 : 201).json(device);
});

router.get('/:id', async (req, res) => {
  const device = await Device.findOne({ _id: req.params.id, owner: req.ownerId })
    .populate({ path: 'activeDriver', select: 'displayName' });
  if (!device) throw ApiError.notFound('Device not found');
  res.json(device);
});

router.patch('/:id', requireRole('owner'), async (req, res) => {
  const device = await Device.findOne({ _id: req.params.id, owner: req.ownerId });
  if (!device) throw ApiError.notFound('Device not found');
  device.set(pick(req.body, ['name']));
  await device.save();
  res.json(device);
});

router.delete('/:id', requireRole('owner'), async (req, res) => {
  const device = await Device.findOneAndDelete({ _id: req.params.id, owner: req.ownerId });
  if (!device) throw ApiError.notFound('Device not found');
  res.status(204).end();
});

module.exports = router;
