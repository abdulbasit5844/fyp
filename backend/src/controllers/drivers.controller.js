const { DriverProfile, Device } = require('../models');
const ApiError = require('../utils/ApiError');
const pick = require('../utils/pick');
const bridge = require('../realtime/mqttBridge');

const FIELDS = ['displayName', 'isPrimary', 'isAuthorized'];

async function findOwned(req) {
  const driver = await DriverProfile.findOne({ _id: req.params.id, owner: req.ownerId }).select('+faceEmbeddings');
  if (!driver) throw ApiError.notFound('Driver not found');
  return driver;
}

async function list(req, res) {
  const drivers = await DriverProfile.find({ owner: req.ownerId }).select('+faceEmbeddings').sort({ createdAt: 1 });
  res.json(drivers);
}

async function create(req, res) {
  const driver = await DriverProfile.create({ ...pick(req.body, FIELDS), owner: req.ownerId });
  res.status(201).json(driver);
}

async function update(req, res) {
  const driver = await findOwned(req);
  driver.set(pick(req.body, FIELDS));
  await driver.save();
  await bridge.publishDriversForOwner(req.ownerId);
  res.json(driver);
}

async function remove(req, res) {
  const driver = await findOwned(req);
  await driver.deleteOne();
  await bridge.publishDriversForOwner(req.ownerId);
  res.status(204).end();
}

const ENROLL_MESSAGES = {
  preview: 'Starting the camera…',
  capture: 'Capturing. Hold still and look at the camera.',
  cancel: 'Enrollment cancelled',
};

// Drives face enrollment on the edge device: 'preview' streams the camera view
// to the app, 'capture' takes the photo and face samples, 'cancel' stops.
// Progress and the result arrive over the WebSocket.
async function enroll(req, res) {
  const action = req.body?.action || 'preview';
  if (!ENROLL_MESSAGES[action]) throw ApiError.badRequest('action must be preview, capture or cancel');
  const driver = await findOwned(req);
  const device = await Device.findOne({ owner: req.ownerId, ...(req.body?.deviceId && { _id: req.body.deviceId }) });
  if (!device) throw ApiError.badRequest('Pair a device before enrolling a driver');
  if (!device.online && action !== 'cancel') throw ApiError.conflict('The vehicle unit is offline');
  bridge.requestEnrollment(device, driver, action);
  res.status(202).json({ message: ENROLL_MESSAGES[action] });
}

async function clearEmbeddings(req, res) {
  const driver = await findOwned(req);
  driver.faceEmbeddings = [];
  driver.photo = null;
  await driver.save();
  await bridge.publishDriversForOwner(req.ownerId);
  res.json(driver);
}

module.exports = { list, create, update, remove, enroll, clearEmbeddings };
