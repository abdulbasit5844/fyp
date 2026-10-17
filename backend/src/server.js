const fs = require('fs');
const http = require('http');
const https = require('https');
const mongoose = require('mongoose');
const config = require('./config');
const connectDB = require('./config/db');
const createApp = require('./app');
const wsHub = require('./realtime/wsHub');
const bridge = require('./realtime/mqttBridge');
const whatsapp = require('./services/whatsappService');

async function main() {
  await connectDB();
  const app = createApp();

  const useTls = config.tls.cert && config.tls.key;
  const server = useTls
    ? https.createServer({ cert: fs.readFileSync(config.tls.cert), key: fs.readFileSync(config.tls.key) }, app)
    : http.createServer(app);

  wsHub.attach(server);
  bridge.connect();
  whatsapp.init();

  server.listen(config.port, () => {
    console.log(`[server] ${useTls ? 'https' : 'http'}://0.0.0.0:${config.port} (${config.env})`);
  });

  const shutdown = async () => {
    console.log('[server] shutting down');
    server.close();
    await bridge.close();
    await mongoose.disconnect();
    process.exit(0);
  };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

main().catch((err) => {
  console.error('[server] failed to start:', err);
  process.exit(1);
});
