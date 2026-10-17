const express = require('express');
const { requireRole } = require('../middleware/auth');
const whatsapp = require('../controllers/whatsapp.controller');

const router = express.Router();

router.get('/', whatsapp.status);
router.post('/link', requireRole('owner'), whatsapp.link);
router.post('/unlink', requireRole('owner'), whatsapp.unlink);
router.post('/test', requireRole('owner'), whatsapp.test);

module.exports = router;
