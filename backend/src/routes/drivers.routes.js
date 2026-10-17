const express = require('express');
const { requireRole } = require('../middleware/auth');
const drivers = require('../controllers/drivers.controller');

const router = express.Router();

router.get('/', drivers.list);
router.post('/', requireRole('owner'), drivers.create);
router.patch('/:id', requireRole('owner'), drivers.update);
router.delete('/:id', requireRole('owner'), drivers.remove);
router.post('/:id/enroll', requireRole('owner'), drivers.enroll);
router.delete('/:id/embeddings', requireRole('owner'), drivers.clearEmbeddings);

module.exports = router;
