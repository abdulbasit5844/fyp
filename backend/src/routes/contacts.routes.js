const express = require('express');
const { requireRole } = require('../middleware/auth');
const contacts = require('../controllers/contacts.controller');

const router = express.Router();

router.get('/', contacts.list);
router.post('/', requireRole('owner'), contacts.create);
router.patch('/:id', requireRole('owner'), contacts.update);
router.delete('/:id', requireRole('owner'), contacts.remove);

module.exports = router;
