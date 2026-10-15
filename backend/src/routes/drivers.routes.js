const express = require('express');
const { DriverProfile, Device } = require('../models');
const ApiError = require('../utils/ApiError');
const pick = require('../utils/pick');
const { requireRole } = require('../middleware/auth');
const bridge = require('../realtime/mqttBridge');

const FIELDS = ['displayName', 'isPrimary', 'isAuthorized'];
const router = express.Router();

async function findOwned(req) {
  const driver = await DriverProfile.findOne({ _id: req.params.id, owner: req.ownerId }).select('+faceEmbeddings');
  if (!driver) throw ApiError.notFound('Driver not found');
  return driver;
}

router.get('/', async (req, res) => {
  const drivers = await DriverProfile.find({ owner: req.ownerId }).select('+faceEmbeddings').sort({ createdAt: 1 });
  res.json(drivers);
});

router.post('/', requireRole('owner'), async (req, res) => {
  const driver = await DriverProfile.create({ ...pick(req.body, FIELDS), owner: req.ownerId });
  res.status(201).json(driver);
});

router.patch('/:id', requireRole('owner'), async (req, res) => {
  const driver = await findOwned(req);
  driver.set(pick(req.body, FIELDS));
  await driver.save();
  await bridge.publishDriversForOwner(req.ownerId);
  res.json(driver);
});

router.delete('/:id', requireRole('owner'), async (req, res) => {
  const driver = await findOwned(req);
  await driver.deleteOne();
  await bridge.publishDriversForOwner(req.ownerId);
  res.status(204).end();
});

// Ask the edge device to capture this driver's face and send back an embedding.
router.post('/:id/enroll', requireRole('owner'), async (req, res) => {
  const driver = await findOwned(req);
  const device = await Device.findOne({ owner: req.ownerId, ...(req.body?.deviceId && { _id: req.body.deviceId }) });
  if (!device) throw ApiError.badRequest('Pair a device before enrolling a driver');
  if (!device.online) throw ApiError.conflict('The device is offline');
  bridge.requestEnrollment(device, driver);
  res.status(202).json({ message: 'Look at the camera. Enrollment takes a few seconds.' });
});

router.delete('/:id/embeddings', requireRole('owner'), async (req, res) => {
  const driver = await findOwned(req);
  driver.faceEmbeddings = [];
  await driver.save();
  await bridge.publishDriversForOwner(req.ownerId);
  res.json(driver);
});

module.exports = router;
