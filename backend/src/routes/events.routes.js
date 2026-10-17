const express = require('express');
const events = require('../controllers/events.controller');

const router = express.Router();

router.get('/', events.list);
router.get('/active', events.active);
router.get('/:id', events.get);
router.post('/:id/acknowledge', events.acknowledge);

module.exports = router;
