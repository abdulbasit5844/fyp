const express = require('express');
const { User } = require('../models');
const ApiError = require('../utils/ApiError');
const pick = require('../utils/pick');
const { requireRole } = require('../middleware/auth');

const router = express.Router();

async function createUser({ name, email, password, role, owner }) {
  if (!name || !email || !password) throw ApiError.badRequest('name, email and password are required');
  const user = new User({ name, email, role, owner });
  try {
    await user.setPassword(password);
  } catch (e) {
    throw ApiError.badRequest(e.message);
  }
  return user.save();
}

// --- Owner: family members and guests for this vehicle (Module 5 FE-3) ---

router.get('/members', requireRole('owner'), async (req, res) => {
  res.json(await User.find({ owner: req.user._id }).sort({ createdAt: 1 }));
});

router.post('/members', requireRole('owner'), async (req, res) => {
  const role = req.body?.role === 'guest' ? 'guest' : 'family';
  const user = await createUser({ ...pick(req.body, ['name', 'email', 'password']), role, owner: req.user._id });
  res.status(201).json(user);
});

router.patch('/members/:id', requireRole('owner'), async (req, res) => {
  const member = await User.findOne({ _id: req.params.id, owner: req.user._id });
  if (!member) throw ApiError.notFound('Member not found');
  if (['family', 'guest'].includes(req.body?.role)) member.role = req.body.role;
  if (typeof req.body?.isActive === 'boolean') {
    member.isActive = req.body.isActive;
    member.deactivatedAt = req.body.isActive ? null : new Date();
  }
  await member.save();
  res.json(member);
});

router.delete('/members/:id', requireRole('owner'), async (req, res) => {
  const result = await User.deleteOne({ _id: req.params.id, owner: req.user._id });
  if (!result.deletedCount) throw ApiError.notFound('Member not found');
  res.status(204).end();
});

// --- Admin: all accounts (FR8.3) ---

router.get('/', requireRole('admin', 'fleet_manager'), async (req, res) => {
  const filter = {};
  if (req.query.role) filter.role = req.query.role;
  res.json(await User.find(filter).sort({ createdAt: -1 }).limit(500));
});

router.post('/', requireRole('admin'), async (req, res) => {
  const user = await createUser(pick(req.body, ['name', 'email', 'password', 'role']));
  res.status(201).json(user);
});

// Deactivation keeps the data (retained 90 days) but blocks access at once,
// because requireAuth rejects inactive users on every request.
router.patch('/:id', requireRole('admin'), async (req, res) => {
  const user = await User.findById(req.params.id).select('+refreshTokens');
  if (!user) throw ApiError.notFound('User not found');
  user.set(pick(req.body, ['name', 'role']));
  if (typeof req.body?.isActive === 'boolean') {
    user.isActive = req.body.isActive;
    user.deactivatedAt = req.body.isActive ? null : new Date();
    if (!req.body.isActive) user.refreshTokens = [];
  }
  await user.save();
  res.json(user);
});

module.exports = router;
