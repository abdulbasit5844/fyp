const express = require('express');
const { requireRole } = require('../middleware/auth');
const users = require('../controllers/users.controller');

const router = express.Router();

// Owner: family members and guests for this vehicle
router.get('/members', requireRole('owner'), users.listMembers);
router.post('/members', requireRole('owner'), users.addMember);
router.patch('/members/:id', requireRole('owner'), users.updateMember);
router.delete('/members/:id', requireRole('owner'), users.removeMember);

// Admin: all accounts
router.get('/', requireRole('admin', 'fleet_manager'), users.list);
router.post('/', requireRole('admin'), users.create);
router.patch('/:id', requireRole('admin'), users.update);

module.exports = router;
