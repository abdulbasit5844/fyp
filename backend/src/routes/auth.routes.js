const express = require('express');
const { requireAuth } = require('../middleware/auth');
const auth = require('../controllers/auth.controller');

const router = express.Router();

router.post('/register', auth.register);
router.post('/login', auth.login);
router.post('/refresh', auth.refresh);
router.post('/logout', auth.logout);

router.get('/me', requireAuth, auth.me);
router.post('/me/fcm-tokens', requireAuth, auth.addFcmToken);
router.delete('/me/fcm-tokens', requireAuth, auth.removeFcmToken);

module.exports = router;