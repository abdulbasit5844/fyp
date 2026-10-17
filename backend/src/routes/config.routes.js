const express = require('express');
const { requireRole } = require('../middleware/auth');
const config = require('../controllers/config.controller');

const router = express.Router();

router.get('/', config.get);
router.patch('/', requireRole('owner'), config.update);

module.exports = router;
