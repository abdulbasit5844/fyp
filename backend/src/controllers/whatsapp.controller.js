const whatsapp = require('../services/whatsappService');
const ApiError = require('../utils/ApiError');

function status(req, res) {
  res.json(whatsapp.getStatus());
}

// Starts linking; the app polls status() for the QR code until connected.
async function link(req, res) {
  try {
    res.json(await whatsapp.link());
  } catch (e) {
    throw ApiError.conflict(e.message);
  }
}

async function unlink(req, res) {
  res.json(await whatsapp.unlink());
}

// Sends a test message so the owner can check a contact's number.
async function test(req, res) {
  const { phone } = req.body || {};
  if (!/^\+[1-9]\d{7,14}$/.test(phone || '')) throw ApiError.badRequest('phone must look like +923001234567');
  const r = await whatsapp.sendText(phone, 'Driver Monitoring System: test message. WhatsApp alerts are working.');
  if (!r.ok) throw ApiError.conflict(r.error);
  res.json({ ok: true });
}

module.exports = { status, link, unlink, test };
