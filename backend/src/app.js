const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const { requireAuth } = require('./middleware/auth');
const errorHandler = require('./middleware/errorHandler');

function createApp() {
  const app = express();
  app.use(helmet());
  app.use(cors());
  app.use(express.json({ limit: '1mb' }));

  app.get('/api/health', (req, res) => res.json({ ok: true, time: new Date().toISOString() }));

  app.use('/api/auth', require('./routes/auth.routes'));
  app.use('/api/contacts', requireAuth, require('./routes/contacts.routes'));
  app.use('/api/config', requireAuth, require('./routes/config.routes'));
  app.use('/api/events', requireAuth, require('./routes/events.routes'));
  app.use('/api/clips', requireAuth, require('./routes/clips.routes'));
  app.use('/api/devices', requireAuth, require('./routes/devices.routes'));
  app.use('/api/drivers', requireAuth, require('./routes/drivers.routes'));
  app.use('/api/users', requireAuth, require('./routes/users.routes'));
  app.use('/api/whatsapp', requireAuth, require('./routes/whatsapp.routes'));

  app.use('/api', (req, res) => res.status(404).json({ error: 'Not found' }));
  app.use(errorHandler);
  return app;
}

module.exports = createApp;
