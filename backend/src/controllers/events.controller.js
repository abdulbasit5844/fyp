const { SafetyEvent, AlertLog } = require('../models');
const { EVENT_TYPES, SEVERITIES } = require('../models/constants');
const ApiError = require('../utils/ApiError');
const eventService = require('../services/eventService');

// FR7.1 – paginated log, newest first, with optional filters.
async function list(req, res) {
  const page = Math.max(1, parseInt(req.query.page, 10) || 1);
  const limit = Math.min(100, Math.max(1, parseInt(req.query.limit, 10) || 20));
  const filter = { owner: req.ownerId };
  if (EVENT_TYPES.includes(req.query.type)) filter.eventType = req.query.type;
  if (SEVERITIES.includes(req.query.severity)) filter.severity = req.query.severity;
  if (req.query.from || req.query.to) {
    filter.detectedAt = {};
    if (req.query.from) filter.detectedAt.$gte = new Date(req.query.from);
    if (req.query.to) filter.detectedAt.$lte = new Date(req.query.to);
  }

  const [items, total] = await Promise.all([
    SafetyEvent.find(filter)
      .sort({ detectedAt: -1 })
      .skip((page - 1) * limit)
      .limit(limit)
      .populate({ path: 'videoClip', select: 'status durationSec sizeBytes' })
      .populate({ path: 'driver', select: 'displayName' }),
    SafetyEvent.countDocuments(filter),
  ]);

  res.json({ items, page, limit, total, pages: Math.ceil(total / limit) });
}

// Events still waiting for the driver (drives the alert screen).
async function active(req, res) {
  const items = await SafetyEvent.find({ owner: req.ownerId, status: 'active' }).sort({ detectedAt: -1 });
  res.json(items);
}

async function get(req, res) {
  const event = await SafetyEvent.findOne({ _id: req.params.id, owner: req.ownerId })
    .populate('videoClip')
    .populate({ path: 'driver', select: 'displayName' });
  if (!event) throw ApiError.notFound('Event not found');
  const notifications = await AlertLog.find({ event: event._id })
    .populate({ path: 'recipientContact', select: 'name phone' })
    .sort({ createdAt: 1 });
  res.json({ ...event.toJSON(), notifications });
}

// FR6.2 – acknowledge from the app; cancels the escalation timer on the edge.
async function acknowledge(req, res) {
  const event = await SafetyEvent.findOne({ _id: req.params.id, owner: req.ownerId });
  if (!event) throw ApiError.notFound('Event not found');
  if (event.status !== 'active') throw ApiError.conflict(`Event is already ${event.status}`);
  res.json(await eventService.acknowledge(event, { via: 'mobile_app', userId: req.user._id }));
}

module.exports = { list, active, get, acknowledge };
