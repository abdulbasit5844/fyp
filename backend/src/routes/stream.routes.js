const express = require('express');
const stream = require('../controllers/stream.controller');

const router = express.Router();

// MediaMTX's auth callback (localhost only)
router.post('/auth', stream.auth);

module.exports = router;
