const { EmergencyContact } = require('../models');
const ApiError = require('../utils/ApiError');
const pick = require('../utils/pick');

const FIELDS = ['name', 'phone', 'email', 'relationship', 'priority', 'notifyBySms'];

async function findOwned(req) {
  const contact = await EmergencyContact.findOne({ _id: req.params.id, owner: req.ownerId });
  if (!contact) throw ApiError.notFound('Contact not found');
  return contact;
}

async function list(req, res) {
  const contacts = await EmergencyContact.find({ owner: req.ownerId }).sort({ priority: 1, createdAt: 1 });
  res.json(contacts);
}

async function create(req, res) {
  const contact = await EmergencyContact.create({ ...pick(req.body, FIELDS), owner: req.ownerId });
  res.status(201).json(contact);
}

async function update(req, res) {
  const contact = await findOwned(req);
  contact.set(pick(req.body, FIELDS));
  await contact.save();
  res.json(contact);
}

// FR6.4 – at least one contact must remain for escalation to work.
async function remove(req, res) {
  const contact = await findOwned(req);
  if ((await EmergencyContact.countDocuments({ owner: req.ownerId })) <= 1) {
    throw ApiError.conflict('At least one emergency contact is required. Add another before removing this one.');
  }
  await contact.deleteOne();
  res.status(204).end();
}

module.exports = { list, create, update, remove };
