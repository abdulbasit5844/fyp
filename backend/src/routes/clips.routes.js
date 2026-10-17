const express = require('express');
const clips = require('../controllers/clips.controller');

const router = express.Router();

router.get('/:id', clips.get);
router.get('/:id/stream', clips.stream);

module.exports = router;
