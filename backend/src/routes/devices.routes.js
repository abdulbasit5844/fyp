const express = require('express');
const { requireRole } = require('../middleware/auth');
const devices = require('../controllers/devices.controller');

const router = express.Router();

router.get('/', devices.list);
router.get('/discover', requireRole('owner'), devices.discover);
router.post('/', requireRole('owner'), devices.pair);
router.get('/:id', devices.get);
router.patch('/:id', requireRole('owner'), devices.update);
router.post('/:id/detection', requireRole('owner', 'family'), devices.setDetection);
router.post('/:id/live', requireRole('owner', 'family'), devices.setLive);
router.delete('/:id', requireRole('owner'), devices.unpair);

module.exports = router;
