const { SafetyEvent, Device, DriverProfile, VideoClip, User } = require('../models');
const ws = require('../realtime/wsHub');
const notify = require('./notificationService');
const pick = require('../utils/pick');

// Late-bound to avoid a require cycle with the MQTT bridge.
const bridge = () => require('../realtime/mqttBridge');

const toPoint = (loc) =>
  loc && Number.isFinite(loc.lat) && Number.isFinite(loc.lng)
    ? {
      type: 'Point',
      coordinates: [loc.lng, loc.lat],
      accuracyM: loc.accuracyM,
      capturedAt: loc.capturedAt ? new Date(loc.capturedAt) : new Date(),
    }
    : undefined;

const background = (p, what) => p.catch((e) => console.error(`[events] ${what} failed:`, e.message));

async function updateDeviceStatus(device, s) {
  device.online = s.online !== false;
  device.lastSeenAt = new Date();
  if (s.state) {
    if (s.state !== device.currentState) device.stateUpdatedAt = new Date();
    device.currentState = s.state;
  }
  if (typeof s.monitoring === 'boolean') device.monitoring = s.monitoring;
  if (s.driverId !== undefined) {
    device.activeDriver = s.driverId && (await DriverProfile.exists({ _id: s.driverId, owner: device.owner }))
      ? s.driverId
      : null;
  }
  const point = toPoint(s.location);
  if (point) device.lastLocation = { type: 'Point', coordinates: point.coordinates };
  if (s.pipelineVersion) device.pipelineVersion = s.pipelineVersion;
  if (!device.online) {
    device.monitoring = false;
    device.currentState = 'safe';
  }
  await device.save();
  ws.broadcast(device.owner, 'device', device.toJSON());
  return device;
}

async function ingestEvent(device, p) {
  // Duplicate MQTT deliveries hit the unique edgeEventId and are ignored.
  const existing = await SafetyEvent.findOne({ edgeEventId: p.eventId });
  if (existing) return existing;

  const driverOk = p.driverId && (await DriverProfile.exists({ _id: p.driverId, owner: device.owner }).catch(() => null));
  const event = await SafetyEvent.create({
    edgeEventId: p.eventId,
    owner: device.owner,
    device: device._id,
    driver: driverOk ? p.driverId : null,
    eventType: p.type,
    severity: p.severity,
    description: p.description,
    signals: p.signals,
    location: toPoint(p.location),
    detectedAt: p.detectedAt ? new Date(p.detectedAt) : new Date(),
    status: 'active',
  });

  ws.broadcast(device.owner, 'event', event.toJSON());
  background(notify.notifyOwnerAlert(event), 'owner alert');
  return event;
}

// Atomic status change so an acknowledgment and an escalation that arrive
// together cannot both win.
async function transition(eventId, from, update) {
  return SafetyEvent.findOneAndUpdate({ _id: eventId, status: from }, update, { new: true });
}

async function acknowledge(event, { via, userId }) {
  const updated = await transition(event._id, 'active', {
    status: 'acknowledged',
    acknowledgedAt: new Date(),
    acknowledgedVia: via,
    ...(userId && { acknowledgedBy: userId }),
  });
  if (!updated) return SafetyEvent.findById(event._id);

  if (via === 'mobile_app') {
    const device = await Device.findById(updated.device);
    if (device) bridge().sendAck(device, updated.edgeEventId);
  }
  ws.broadcast(updated.owner, 'event_update', updated.toJSON());
  return updated;
}

async function escalate(device, p) {
  const event = await SafetyEvent.findOne({ edgeEventId: p.eventId, device: device._id });
  if (!event) return null;

  const location = toPoint(p.location) || event.location;
  const updated = await transition(event._id, 'active', { status: 'escalated', escalatedAt: new Date(), location });
  if (!updated) {
    console.log(`[events] escalation for ${p.eventId} ignored: already ${event.status}`);
    return null;
  }

  ws.broadcast(updated.owner, 'escalation', updated.toJSON());
  const owner = await User.findById(updated.owner);
  background(
    notify.notifyEscalation(updated, owner?.name || 'The driver').then((logs) =>
      ws.broadcast(updated.owner, 'escalation_delivery', { eventId: updated.id, notifications: logs.map((l) => l.toJSON()) })),
    'escalation'
  );
  return updated;
}

async function edgeAck(device, p) {
  const event = await SafetyEvent.findOne({ edgeEventId: p.eventId, device: device._id });
  return event ? acknowledge(event, { via: 'edge_button' }) : null;
}

async function resolve(device, p) {
  const event = await SafetyEvent.findOne({ edgeEventId: p.eventId, device: device._id });
  // Only an open alert can clear; acknowledged/escalated ones keep that status.
  if (!event || event.status !== 'active') return event;
  event.status = 'resolved';
  event.resolvedAt = new Date();
  await event.save();
  ws.broadcast(event.owner, 'event_update', event.toJSON());
  return event;
}

async function recordClip(device, p) {
  const event = await SafetyEvent.findOne({ edgeEventId: p.eventId, device: device._id });
  if (!event) return null;
  const update = {
    owner: event.owner,
    device: device._id,
    filePath: p.filePath,
    status: p.status || 'available',
    ...(p.sizeBytes != null && { sizeBytes: p.sizeBytes }),
    ...(p.durationSec != null && { durationSec: p.durationSec }),
    ...(p.preEventSec != null && { preEventSec: p.preEventSec }),
    ...(p.postEventSec != null && { postEventSec: p.postEventSec }),
    startedAt: p.startedAt ? new Date(p.startedAt) : event.detectedAt,
    ...(p.status === 'deleted' && { deletedAt: new Date() }),
  };
  const clip = await VideoClip.findOneAndUpdate({ event: event._id }, update, {
    upsert: true, new: true, runValidators: true, setDefaultsOnInsert: true,
  });
  ws.broadcast(event.owner, 'clip', clip.toJSON());
  return clip;
}

const PROGRESS_FIELDS = ['mode', 'samples', 'needed', 'faceVisible', 'secondsLeft', 'preview'];

async function saveEnrollment(device, p) {
  // Live progress (with a small camera preview) goes straight to the owner's app.
  if (p.status === 'progress') {
    ws.broadcast(device.owner, 'enrollment_progress', { driverId: String(p.driverId), ...pick(p, PROGRESS_FIELDS) });
    return null;
  }
  const driver = await DriverProfile.findOne({ _id: p.driverId, owner: device.owner }).select('+faceEmbeddings');
  if (!driver) return null;
  if (p.ok && Array.isArray(p.vector)) {
    driver.faceEmbeddings.push({ vector: p.vector, model: p.model || 'unknown' });
    driver.faceEmbeddings = driver.faceEmbeddings.slice(-5); // keep the 5 most recent samples
    if (typeof p.photo === 'string' && p.photo) driver.photo = p.photo;
    await driver.save();
    await bridge().publishDriversForOwner(device.owner);
  }
  console.log(`[enroll] ${driver.displayName}: ${p.ok ? 'face enrolled' : `failed (${p.error})`}`);
  ws.broadcast(device.owner, 'enrollment', {
    driverId: driver.id, ok: Boolean(p.ok), error: p.error, ...(p.ok && { photo: driver.photo }),
  });
  return driver;
}

module.exports = {
  updateDeviceStatus, ingestEvent, acknowledge, escalate, edgeAck, resolve, recordClip, saveEnrollment,
};
